"""Self-contained regression tests: no private vault, token, or network needed.

Synthetic evidence and mocked embeddings test software contracts, not the truth
of model-written claims or the usefulness of a user's private knowledge.
"""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import markdown_model as md
import durable_provenance as dp
import knowledgeos as kos
import research_gate as gate


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class StubRun:
    """Protocol double for guard/storage tests; never an alternative verifier."""
    def __init__(self, root, run_id="unit"):
        self.run_id = run_id
        self.dir = root / ".knowledgeos/runs" / run_id
        self.dir.mkdir(parents=True)
        for attribute, name in {
            "run_json": "run.json", "history_path": "state-history.jsonl", "manifest": "evidence-manifest.json",
            "coverage_plan_path": "coverage-plan.json", "facts_path": "facts.jsonl", "facts_verify": "facts.verify.jsonl",
            "claims_path": "claims.jsonl", "claims_verify": "claims.verify.jsonl", "mechanisms_path": "mechanisms.jsonl",
            "mechanisms_verify": "mechanisms.verify.jsonl", "evidence_bindings_path": "evidence-bindings.jsonl",
            "gate_path": "gate.json", "draft_path": "draft.md", "draft_trace_path": "draft-trace.json",
            "draft_verify_path": "draft.verify.json", "report_path": "report.json",
        }.items(): setattr(self, attribute, self.dir / name)
        self.bad_history = []
        self.save(state="INIT")
    def data(self): return dp.load_json(self.run_json)
    def state(self): return self.data()["state"]
    def exists(self): return self.run_json.is_file()
    def save(self, **fields):
        old = dp.load_json(self.run_json) if self.run_json.exists() else {}
        old.update(fields); dp.atomic_json(self.run_json, old); return old
    def validate_state_history(self): return self.bad_history
    def revoke_gate(self, reason):
        self.save(state="FACTS_READY")
        dp.atomic_json(self.gate_path, {"write_allowed": False, "reason": reason})
    def fail(self, stage, errors): return {"ok": False, "stage": stage, "errors": errors}
    def advance(self, stage, state, extra=None):
        self.save(state=state, **(extra or {})); return {"ok": True, "state": state}


class MarkdownTest(unittest.TestCase):
    def test_inline_aliases_with_commas(self):
        props, _, _ = md.frontmatter('---\naliases: ["alpha, beta", "中文"]\n---\n')
        self.assertEqual(props["aliases"], ["alpha, beta", "中文"])
    def test_block_lists_and_single_quotes(self):
        props, body, offset = md.frontmatter("---\norigin: 'codex' # comment\naliases:\n  - '甲'\n  - 'it''s'\n---\nBody")
        self.assertEqual(props["aliases"], ["甲", "it's"])
        self.assertEqual(props["origin"], "codex")
        self.assertEqual(body, "Body"); self.assertEqual(offset, 6)
    def test_unquoted_apostrophe(self):
        self.assertEqual(md.frontmatter("---\ntitle: Don't overfit\n---\n")[0]["title"], "Don't overfit")
    def test_duplicate_ownership_rejected(self):
        with self.assertRaises(md.FrontmatterError): md.frontmatter("---\norigin: human\norigin: codex\n---\n")
    def test_unclosed_frontmatter_rejected(self):
        with self.assertRaises(md.FrontmatterError): md.frontmatter("---\norigin: codex\n")
    def test_unsupported_yaml_rejected(self):
        with self.assertRaises(md.FrontmatterError): md.frontmatter("---\norigin: &owner codex\n---\n")
    def test_crlf_body_preserved(self):
        _, body, _ = md.frontmatter("---\r\norigin: codex\r\n---\r\nHuman\r\n")
        self.assertEqual(body, "Human\r\n")
    def test_code_links_are_not_relationships(self):
        links = md.body_links('[[Actual#Heading|label]]\n```md\n[[Example]]\n```\n`[[Inline]]`\n![[Embedded]]')
        self.assertEqual([x["note"] for x in links], ["Actual", "Embedded"])
        self.assertTrue(links[-1]["embedded"])
    def test_nested_heading_paths(self):
        parts = md.sections("# Root\n## A\n### Mechanism\none\n## B\n### Mechanism\ntwo\n")
        self.assertEqual([x["anchor"] for x in parts if x["heading"] == "Mechanism"], ["Root#A#Mechanism", "Root#B#Mechanism"])
    def test_repeated_headings_have_ordinals(self):
        parts = md.sections("## Repeated\none\n## Repeated\ntwo\n")
        self.assertEqual([x["occurrence"] for x in parts], [1, 2])
    def test_fenced_headings_ignored(self):
        self.assertEqual([x["heading"] for x in md.sections("# Real\n```\n## Fake\n```\n")], ["Real"])
    def test_csharp_heading_not_mutilated(self):
        self.assertEqual(md.sections("## C#\ntext\n")[0]["heading"], "C#")
    def test_project_roles_not_exact_titles(self):
        text = "\n".join("## " + heading + "\ncontent" for heading in ["Overview", "Task", "Evaluation", "Challenges", "Solution Landscape", "Compressed Conclusions", "Evidence Map"])
        self.assertEqual(md.missing_project_roles(text), [])


class RetrievalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.old = {key: getattr(kos, key) for key in ["ROOT", "VAULT", "DERIVED", "CONFIG", "VECTOR_INDEX", "VECTOR_META"]}
        kos.ROOT = self.root; kos.VAULT = self.root / "vault"; kos.DERIVED = self.root / ".knowledgeos"
        kos.CONFIG = self.root / "knowledge-config.yaml"; kos.VECTOR_INDEX = kos.DERIVED / "vector-index.npz"; kos.VECTOR_META = kos.DERIVED / "vector-meta.json"
        write(kos.CONFIG, "vector: false\nprovider: sentence-transformers\nmodel: mock\ndimension: 2\n")
        self.note("projects/A/A", "project", "# A\n", extra='parents: []\n')
        self.note("projects/B/B", "project", "# B\n", extra='parents: []\n')
        self.note("projects/A/details", "project-doc", "# Details\n## Scheduler\nunique_scheduler configuration and scheduling limitations.\n## Applications\nApplied [[Mechanism#Boundary]] as a diagnosis; result remains unverified.\n", extra='projects: ["[[A]]", "[[B]]"]\n')
        self.note("learning/Project Learning", "learning", "# Project Learning\n## Reconstruction\nunique_project_method preserves the complete project context.\n", extra='learning_kind: project\nprojects: ["[[A]]"]\n')
        self.note("learning/Mechanism", "learning", "# Mechanism\n## Diagnosis\nunique_candidate_oracle separates candidate coverage from selector error.\n## Boundary\nunique_failure_boundary: an oracle is not evidence of learnability.\n", extra='learning_kind: mechanism\naliases: ["候选上限", "Oracle separation"]\nprojects: ["[[A]]", "[[B]]"]\n')
    def tearDown(self):
        for key, value in self.old.items(): setattr(kos, key, value)
        self.tmp.cleanup()
    def note(self, identity, kind, body, extra=""):
        return write(kos.VAULT / (identity + ".md"), f"---\ntype: {kind}\norigin: codex\n{extra}---\n{body}")
    def test_both_learning_units_retrievable(self):
        self.assertEqual(kos.bm25("unique_project_method")[0]["learning_kind"], "project")
        self.assertEqual(kos.bm25("unique_candidate_oracle")[0]["learning_kind"], "mechanism")
    def test_legacy_learning_not_retyped(self):
        self.note("learning/Legacy", "learning", "legacy_unique_body")
        self.assertIsNone(kos.bm25("legacy_unique_body")[0]["learning_kind"])
    def test_alias_search_and_link_resolution(self):
        results = kos.bm25("候选上限")
        self.assertEqual(results[0]["id"], "learning/Mechanism")
        aliases = kos.note_aliases(kos.build_graph()["nodes"])
        self.assertEqual(kos.resolve_note_link("候选上限#Boundary", aliases), "learning/Mechanism")
    def test_duplicate_aliases_deduplicated(self):
        note = kos.parse_note(kos.VAULT / "learning/Mechanism.md")
        note["properties"]["aliases"] = ["Mechanism", "Mechanism"]
        self.assertEqual(kos.note_aliases([note])["Mechanism"], ["learning/Mechanism"])
    def test_qualified_missing_path_never_falls_back(self):
        aliases = kos.note_aliases(kos.build_graph()["nodes"])
        self.assertIsNone(kos.resolve_note_link("projects/Wrong/Mechanism", aliases))
    def test_ambiguous_alias_not_guessed(self):
        self.note("learning/Other", "learning", "other", extra='aliases: ["候选上限"]\n')
        self.assertIsNone(kos.resolve_note_link("候选上限", kos.note_aliases(kos.build_graph()["nodes"])))
    def test_precise_anchor_in_graph(self):
        edge = next(e for e in kos.build_graph()["edges"] if e.get("anchor") == "Boundary")
        self.assertEqual(edge["target"], "learning/Mechanism")
        self.assertIn("diagnosis", edge["context"])
    def test_missing_anchor_reported_by_lint(self):
        self.note("learning/Broken", "learning", "[[Mechanism#Not a heading]]")
        self.assertTrue(any(x.get("reason") == "missing_anchor" for x in kos.lint()["issues"]))
    def test_same_note_and_block_anchors(self):
        self.note("learning/Self", "learning", "# Self\n## Here\nA block ^stable\n[[#Here]]\n[[#^stable]]\n")
        self.assertFalse([x for x in kos.build_graph()["wanted_links"] if x["source"] == "learning/Self"])
    def test_projects_many_to_many_without_duplicate_wikilinks(self):
        edges = [e for e in kos.build_graph()["edges"] if e["source"] == "learning/Mechanism"]
        self.assertEqual(len([e for e in edges if e["kind"] == "projects"]), 2)
        self.assertFalse([e for e in edges if e["kind"] == "wikilink"])
    def test_multi_parent_dag(self):
        self.note("projects/C/C", "project", "# C", extra='parents: ["[[A]]", "[[B]]"]\n')
        graph = kos.project_graph()
        self.assertIn("projects/C/C", graph["multi_parent"]); self.assertFalse(graph["cycles"])
    def test_cycle_terminates(self):
        self.note("projects/A/A", "project", "# A", extra='parents: ["[[B]]"]\n')
        self.note("projects/B/B", "project", "# B", extra='parents: ["[[A]]"]\n')
        self.assertTrue(kos.project_graph()["cycles"])
    def test_chunk_ids_collision_free(self):
        self.note("learning/Repeated", "learning", "# Repeated\n## A\n### Why\none\n## B\n### Why\ntwo\n### Why\nthree\n")
        chunks = kos.semantic_chunks()
        self.assertEqual(len(chunks), len({x["chunk_id"] for x in chunks}))
    def test_search_returns_correct_section(self):
        result = kos.bm25("unique_failure_boundary")[0]
        self.assertEqual(result["heading"], "Boundary")
        self.assertIn("not evidence", result["snippet"])
        self.assertGreater(result["start_line"], 1)
    def test_hybrid_uses_best_not_last_rank(self):
        with patch.object(kos, "bm25", return_value=[]), patch.object(kos, "vector_search", return_value=([
            {"id": "learning/Mechanism", "rank": 1}, {"id": "learning/Project Learning", "rank": 2}, {"id": "learning/Mechanism", "rank": 9}], None)):
            results = kos.hybrid_search("anything")
        self.assertEqual(results[0]["id"], "learning/Mechanism")
        self.assertEqual(results[0]["vector_rank"], 1)
    def test_hybrid_preserves_snippet(self):
        lexical = [{"id": "learning/Mechanism", "path": "vault/learning/Mechanism.md", "type": "learning", "snippet": "correct bound snippet", "heading": "Boundary"}]
        with patch.object(kos, "bm25", return_value=lexical), patch.object(kos, "vector_search", return_value=([{"id": "learning/Mechanism", "rank": 1}], None)):
            self.assertEqual(kos.hybrid_search("x")[0]["snippet"], "correct bound snippet")
    def test_fallback_is_visible_and_usable(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), patch.object(kos, "vector_search", return_value=([], "stale vector index")):
            results = kos.hybrid_search("unique_candidate_oracle")
        self.assertTrue(results); self.assertIn("stale", stderr.getvalue())
    def test_zero_limit_no_retrieval(self):
        with patch.object(kos, "vector_search", side_effect=AssertionError("should not run")):
            self.assertEqual(kos.hybrid_search("x", 0), [])
    def test_reuse_only_explicit_application_sections(self):
        report = kos.reuse_report()
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["declared_applications"][0]["verification"], "declared-use-not-validated-effect")
    def test_invalid_learning_kind_is_diagnostic(self):
        self.note("learning/Invalid", "learning", "# Bad", extra='learning_kind: [project, mechanism]\n')
        self.assertTrue(any(x["kind"] == "invalid_learning_kind" for x in kos.lint()["issues"]))
    def test_fixed_twelve_query_fixture(self):
        cases = []
        entries = [("unique_scheduler", "projects/A/details"), ("unique_project_method", "learning/Project Learning"), ("unique_candidate_oracle", "learning/Mechanism"), ("unique_failure_boundary", "learning/Mechanism")]
        for repeat in range(3):
            for query, expected in entries:
                cases.append({"id": f"{repeat}-{query}", "query": query + ["", " diagnosis", " context"][repeat], "expected_ids": [expected]})
        suite = self.root / "eval.json"; suite.write_text(json.dumps({"top_k": 3, "cases": cases}))
        result = kos.retrieval_eval(str(suite))
        self.assertEqual(result["passed"], 12)
    def test_graph_and_provenance_commands_registered(self):
        for command in ("graph", "provenance", "reuse"):
            with patch.object(sys, "argv", ["knowledgeos.py", command]), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(kos.main(), 0)
            self.assertIsInstance(json.loads(out.getvalue()), dict)

    def _mock_embeddings(self):
        try: import numpy as np
        except ImportError: self.skipTest("optional numpy not installed")
        class Model:
            def __init__(self, name): pass
            def encode(self, text, **kwargs): return [[1., float(i + 1)] for i in range(len(text))]
            encode_document = encode
            def encode_query(self, text, **kwargs): return [[1., 1.] for _ in text]
        return patch.dict(sys.modules, {"sentence_transformers": types.SimpleNamespace(SentenceTransformer=Model)})
    def test_vector_build_no_undefined_dimension(self):
        with self._mock_embeddings():
            result = kos.build_vector_index()
            self.assertEqual(result["status"], "built")
            values, warning = kos.vector_search("diagnosis")
            self.assertIsNone(warning); self.assertTrue(values)
            self.assertEqual(len(values), len({x["id"] for x in values}))
    def test_vector_cache_invalidated_by_content(self):
        with self._mock_embeddings():
            self.assertEqual(kos.build_vector_index()["status"], "built")
            path = kos.VAULT / "learning/Mechanism.md"; path.write_text(path.read_text() + "\nNew condition")
            values, warning = kos.vector_search("anything")
            self.assertFalse(values); self.assertIn("stale", warning)
    def test_vector_cache_invalidated_by_alias(self):
        with self._mock_embeddings():
            kos.build_vector_index()
            path = kos.VAULT / "learning/Mechanism.md"; path.write_text(path.read_text().replace("候选上限", "新别名"))
            self.assertIn("stale", kos.vector_search("anything")[1])
    def test_vector_integrity_checksum(self):
        with self._mock_embeddings():
            kos.build_vector_index(); kos.VECTOR_INDEX.write_bytes(b"wrong")
            self.assertIn("checksum", kos.vector_search("anything")[1])
    def test_empty_vector_corpus_safe(self):
        with self._mock_embeddings():
            shutil.rmtree(kos.VAULT)
            self.assertEqual(kos.build_vector_index()["status"], "empty")


class ProtectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.run = StubRun(self.root)
        self.oldroot = gate.ROOT; gate.ROOT = self.root
    def tearDown(self):
        gate.ROOT = self.oldroot; self.tmp.cleanup()
    def target(self, text, name="note"):
        return write(self.root / "vault" / (name + ".md"), text)
    def ready(self, target="vault/note.md", text="---\norigin: codex\ntype: learning\n---\n# Result\n<!-- KOS:refs=F-X-001 -->\nEvidence-backed synthetic example.\n", region=None):
        dp.bind_target(self.root, self.run, target, region)
        for path, rows in ((self.run.facts_path, [{"fact_id": "F-X-001", "statement": "synthetic example"}]), (self.run.claims_path, [{"claim_id": "C-X", "durable": True}]), (self.run.mechanisms_path, [{"mechanism_id": "M-X"}])):
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        for path in (self.run.facts_verify, self.run.claims_verify, self.run.mechanisms_verify): path.write_text('{}\n')
        self.run.coverage_plan_path.write_text('{}')
        self.run.manifest.write_text('{}')
        self.run.evidence_bindings_path.write_text(json.dumps({"evidence_id": "E-X", "excerpt": "synthetic example", "source_id": "source:fixture"}) + "\n")
        self.run.draft_path.write_text(text)
        self.run.save(state="FINAL_VERIFIED", draft_sha256=dp.digest(text.encode()))
        dp.atomic_json(self.run.gate_path, {"write_allowed": True})
        dp.atomic_json(self.run.draft_verify_path, {"ok": True, "draft_sha256": dp.digest(text.encode())})
        dp.atomic_json(self.run.draft_trace_path, {"blocks": [{"refs": ["F-X-001"], "text": "synthetic example"}]})
    def test_missing_origin_protected(self):
        self.target("# Human note\n")
        with self.assertRaisesRegex(ValueError, "human-owned"): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_explicit_human_protected(self):
        self.target("---\norigin: human\n---\n# Human\n")
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_quoted_human_protected(self):
        self.target("---\norigin: 'human'\n---\n")
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_ambiguous_origin_fail_closed(self):
        self.target("---\norigin: [codex, human]\n---\n")
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_mixed_requires_region(self):
        self.target("---\norigin: mixed\n---\n# Human\n")
        with self.assertRaisesRegex(ValueError, "managed region"): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_mixed_preserves_outside_bytes(self):
        prefix = "---\norigin: mixed\n---\n人工内容，不得覆盖。\n<!-- KOS:managed:summary:start -->"
        suffix = "<!-- KOS:managed:summary:end -->\n人工尾注。\n"
        path = self.target(prefix + "\nold\n" + suffix)
        self.ready(text="## Result\nNew supported detail.\n", region="summary")
        result = gate.finalize_run(self.run, "vault/note.md")
        self.assertTrue(result["ok"], result)
        content = path.read_text()
        self.assertTrue(content.startswith(prefix)); self.assertTrue(content.endswith(suffix))
        self.assertIn("New supported", content)
    def test_stale_target_rejected(self):
        path = self.target("---\norigin: codex\n---\nOld\n")
        self.ready(); path.write_text(path.read_text() + "Human changed it\n")
        result = gate.finalize_run(self.run, "vault/note.md")
        self.assertFalse(result["ok"]); self.assertIn("STALE_TARGET", result["error"])
        self.assertIn("Human changed", path.read_text())
    def test_missing_binding_rejected(self):
        self.ready(); (self.run.dir / "target-binding.json").unlink()
        result = gate.finalize_run(self.run, "vault/note.md")
        self.assertFalse(result["ok"]); self.assertIn("TARGET_NOT_BOUND", result["error"])
    def test_binding_tampering_rejected(self):
        self.ready(); path = self.run.dir / "target-binding.json"; content = dp.load_json(path); content["owner"] = "anything"; dp.atomic_json(path, content)
        self.assertIn("TARGET_BINDING_DRIFT", gate.finalize_run(self.run, "vault/note.md")["error"])
    def test_late_bind_rejected(self):
        self.run.save(state="FACTS_FROZEN")
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_bind_cannot_be_silently_rebased(self):
        dp.bind_target(self.root, self.run, "vault/note.md")
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/other.md")
    def test_target_changed_during_archive_preparation(self):
        path = self.target("---\norigin: codex\n---\nOld")
        self.ready()
        real = gate.prepare_archive
        def concurrent(*args, **kwargs):
            staged = real(*args, **kwargs); path.write_text("---\norigin: codex\n---\nConcurrent edit"); return staged
        with patch.object(gate, "prepare_archive", side_effect=concurrent):
            result = gate.finalize_run(self.run, "vault/note.md")
        self.assertFalse(result["ok"]); self.assertIn("Concurrent edit", path.read_text())
    def test_run_and_region_path_traversal_rejected(self):
        for value in ("../bad", "a/b", "..", "a..b"):
            with self.assertRaises(ValueError): dp.safe_id(value)
        with self.assertRaises(ValueError): dp.target_path(self.root, "vault/../outside.md")
    def test_symlink_target_rejected(self):
        outside = self.root / "outside.md"; outside.write_text("protected")
        (self.root / "vault").mkdir(); (self.root / "vault/note.md").symlink_to(outside)
        with self.assertRaises(ValueError): dp.bind_target(self.root, self.run, "vault/note.md")
    def test_duplicate_managed_markers_rejected(self):
        with self.assertRaises(ValueError): dp.region_span("<!-- KOS:managed:x:start --><!-- KOS:managed:x:start --><!-- KOS:managed:x:end -->", "x")
    def test_nested_managed_markers_rejected(self):
        with self.assertRaises(ValueError): dp.region_span("<!-- KOS:managed:y:start --><!-- KOS:managed:x:start -->body<!-- KOS:managed:x:end --><!-- KOS:managed:y:end -->", "x")
    def test_region_frontmatter_injection_rejected(self):
        with self.assertRaises(ValueError): dp.final_text({"region": "x"}, "<!-- KOS:managed:x:start --><!-- KOS:managed:x:end -->", "---\norigin: codex\n---")
    def test_generated_note_requires_codex_ownership(self):
        self.ready(text="# Missing origin\n")
        self.assertFalse(gate.finalize_run(self.run, "vault/note.md")["ok"])
    def test_draft_mutation_rejected(self):
        self.ready(); self.run.draft_path.write_text("changed")
        self.assertFalse(gate.finalize_run(self.run, "vault/note.md")["ok"])
    def test_invalid_journal_blocks_write(self):
        self.ready(); self.run.bad_history = ["STATE_HISTORY_HASH_INVALID"]
        self.assertFalse(gate.finalize_run(self.run, "vault/note.md")["ok"])
    def test_cooperative_writer_lock(self):
        self.ready()
        with dp.target_lock(self.root, "vault/note.md"):
            self.assertIn("TARGET_LOCKED", gate.finalize_run(self.run, "vault/note.md")["error"])
    def test_acceptance_survives_cache_deletion(self):
        self.ready(); result = gate.finalize_run(self.run, "vault/note.md")
        self.assertTrue(result["ok"], result)
        shutil.rmtree(self.root / ".knowledgeos")
        self.assertTrue(dp.rebuild_finalizations(self.root)["ok"])
        self.assertEqual(dp.archive_audit(self.root)["issue_count"], 0)
        proof = dp.provenance_for(self.root, {"vault/note.md"})
        self.assertEqual(proof[0]["evidence"][0]["excerpt"], "synthetic example")
    def test_archive_drift_not_silently_reindexed(self):
        self.ready(); self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        write(self.root / "sources/research/unit/facts.jsonl", '{}\n')
        self.assertFalse(dp.rebuild_finalizations(self.root)["ok"])
        self.assertTrue(dp.archive_audit(self.root)["issues"])
    def test_finalized_output_drift_detected(self):
        self.ready(); self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        write(self.root / "vault/note.md", "edited")
        self.assertTrue(any(x["kind"] == "FINALIZATION_HASH_DRIFT" for x in dp.archive_audit(self.root)["issues"]))
    def test_mixed_outside_edit_not_falsely_reported(self):
        path = self.target("---\norigin: mixed\n---\nHuman\n<!-- KOS:managed:x:start -->\nold\n<!-- KOS:managed:x:end -->\n")
        self.ready(text="new", region="x"); self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        path.write_text(path.read_text().replace("Human", "Human revised"))
        self.assertEqual(dp.archive_audit(self.root)["issue_count"], 0)
    def test_fact_change_between_verification_and_freeze(self):
        rows = [{"fact_id": "F-X-1", "statement": "original"}]
        self.run.facts_path.write_text(json.dumps(rows[0]))
        self.run.facts_verify.write_text('{}')
        self.run.save(facts_sha256_pending=gate.jsonl_sha256(rows), facts_verdicts_sha256=dp.digest(b'{}'))
        self.run.facts_path.write_text(json.dumps({**rows[0], "statement": "changed"}))
        self.assertFalse(gate.freeze_facts(self.run)["ok"])
    def test_verdict_change_before_freeze(self):
        rows = [{"fact_id": "F-X-1", "statement": "original"}]
        self.run.facts_path.write_text(json.dumps(rows[0])); self.run.facts_verify.write_text('{}')
        self.run.save(facts_sha256_pending=gate.jsonl_sha256(rows), facts_verdicts_sha256=dp.digest(b'{}'))
        self.run.facts_verify.write_text('{"tampered":true}')
        self.assertFalse(gate.freeze_facts(self.run)["ok"])


    def test_new_region_supersedes_old_whole_file_hash(self):
        body = "---\norigin: codex\n---\n# Result\n<!-- KOS:managed:x:start -->\nold\n<!-- KOS:managed:x:end -->\n"
        self.ready(text=body)
        self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        self.run = StubRun(self.root, "second")
        self.ready(text="new section", region="x")
        self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        self.assertEqual(dp.archive_audit(self.root)["issue_count"], 0)
    def test_new_whole_note_supersedes_prior_region(self):
        self.target("---\norigin: codex\n---\n<!-- KOS:managed:x:start -->\nold\n<!-- KOS:managed:x:end -->\n")
        self.ready(text="section", region="x")
        self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        self.run = StubRun(self.root, "second"); self.ready()
        self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        self.assertEqual(dp.archive_audit(self.root)["issue_count"], 0)
    def test_corrupt_proof_not_returned_by_trace(self):
        self.ready(); self.assertTrue(gate.finalize_run(self.run, "vault/note.md")["ok"])
        write(self.root / "sources/research/unit/facts.jsonl", '{}\n')
        self.assertEqual(dp.provenance_for(self.root, {"vault/note.md"}), [])
    def test_evidence_metadata_change_before_freeze(self):
        rows = [{"fact_id": "F-X-1", "statement": "original"}]
        self.run.facts_path.write_text(json.dumps(rows[0])); self.run.facts_verify.write_text('{}')
        self.run.manifest.write_text('{}')
        self.run.save(facts_sha256_pending=gate.jsonl_sha256(rows), facts_verdicts_sha256=dp.digest(b'{}'), manifest_sha256=dp.digest(b'{}'))
        self.run.manifest.write_text('{"changed":true}')
        self.assertFalse(gate.freeze_facts(self.run)["ok"])
    def test_interrupted_seal_reports_already_written_output(self):
        self.ready()
        with patch.object(gate, "commit_archive", side_effect=OSError("synthetic seal failure")):
            result = gate.finalize_run(self.run, "vault/note.md")
        self.assertFalse(result["ok"]); self.assertTrue(result["output_written"])
        self.assertTrue((self.root / "vault/note.md").is_file())
        self.assertIn("after Markdown was written", result["error"])


if __name__ == "__main__": unittest.main()
