import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("knowledgeos_research_gate", ROOT / "tools/research_gate.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def j(obj):
    return json.dumps(obj, ensure_ascii=False)


def write_jsonl(path: Path, records):
    path.write_text("\n".join(j(r) for r in records), encoding="utf-8")


class GateSandbox:
    """Patch module paths into a temp dir and build runs with minimal valid artifacts."""

    def __init__(self, tmp: str):
        self.root = Path(tmp)
        self.runs = self.root / ".knowledgeos" / "runs"
        self.finalizations = self.root / ".knowledgeos" / "finalizations.json"
        self.vault = self.root / "vault"
        self.old = (MODULE.ROOT, MODULE.RUNS_DIR, MODULE.FINALIZATIONS_PATH)
        MODULE.ROOT = self.root
        MODULE.RUNS_DIR = self.runs
        MODULE.FINALIZATIONS_PATH = self.finalizations

    def restore(self):
        MODULE.ROOT, MODULE.RUNS_DIR, MODULE.FINALIZATIONS_PATH = self.old

    def run(self, run_id="t"):
        return MODULE.Run(run_id)

    def build(self, run_id="t", facts=None, fact_verdicts=None, claims=None,
              claim_verdicts=None, mechanisms=None, mech_verdicts=None, to="FACTS_FROZEN", coverage_plan=None):
        """Create a run and advance it. `to` = FACTS_READY stops before fact
        verification (for fact-level failure tests); otherwise advances through
        FACTS_FROZEN. Claims/mechanisms are written but not verified by build()."""
        run = self.run(run_id)
        MODULE.init_run(run_id, "Demo", "test")
        sources = [
            {"source_id": "src-r1", "solution_id": "R1", "available": ["writeup", "repository"]},
            {"source_id": "src-r2", "solution_id": "R2", "available": ["writeup"]},
            {"source_id": "src-r6", "solution_id": "R6", "available": ["writeup", "repository"]},
            {"source_id": "src-r8", "solution_id": "R8", "available": ["writeup", "repository"]},
        ]
        (run.manifest).write_text(j({"project": "Demo", "scope": "test", "sources": sources}), encoding="utf-8")
        facts = facts if facts is not None else [
            {"fact_id": "F-R1-001", "solution_id": "R1", "subject": "s", "statement": "Base entropy 0.01.",
             "source_id": "src-r1", "source_anchor": "writeup:t", "evidence_type": "author_stated"},
            {"fact_id": "F-R8-001", "solution_id": "R8", "subject": "s", "statement": "Halt head uses behavioral-prior KL.",
             "source_id": "src-r8", "source_anchor": "writeup:t", "evidence_type": "author_stated"},
        ]
        write_jsonl(run.facts_path, facts)
        entities = sorted({str(f.get("solution_id")) for f in facts if f.get("solution_id")})
        plan = coverage_plan or {
            "document_kind": "test",
            "expected_entities": entities,
            "required_axes_by_entity": {},
            "min_facts_per_entity": 1,
            "output_contract": {"required_sections": [], "required_entity_labels": [], "min_chars_warning": 0},
        }
        run.coverage_plan_path.write_text(j(plan), encoding="utf-8")
        fact_verdicts = fact_verdicts if fact_verdicts is not None else [
            {"kind": "fact", "fact_id": f["fact_id"], "status": "PASS", "reason": None} for f in facts]
        write_jsonl(run.facts_verify, fact_verdicts)
        result = MODULE.run_verify(run_id)              # INIT -> EVIDENCE_READY
        assert result["ok"], result
        if to != "FACTS_READY":
            while run.state() != "FACTS_FROZEN":
                result = MODULE.run_verify(run_id)
                assert result["ok"], result
        elif run.state() == "EVIDENCE_READY":
            result = MODULE.run_verify(run_id)          # -> FACTS_READY
            assert result["ok"], result
        if claims is not None:
            write_jsonl(run.claims_path, claims)
            write_jsonl(run.claims_verify, claim_verdicts or [])
        if mechanisms is not None:
            write_jsonl(run.mechanisms_path, mechanisms)
            write_jsonl(run.mechanisms_verify, mech_verdicts or [])
        return run


VALID_CLAIM = {
    "claim_id": "C-T-01", "claim_type": "convergence",
    "statement": "Behavioral-prior KL appears as one route among several.",
    "support_fact_ids": ["F-R1-001", "F-R8-001"], "counter_fact_ids": [],
    "eligible_entities": ["R1", "R8"], "boundary": "Two adopters only.",
}
VALID_MECH = {
    "mechanism_id": "M-T-01", "intervention": "behavioral-prior KL",
    "changed_variable": "exploration behavior prior",
    "expected_effect": "bias exploration toward meaningful actions",
    "support_claim_ids": ["C-T-01"], "boundary": "Strong priors may need decay.",
}


class ResearchGateSyntheticTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sandbox = GateSandbox(self._tmp.name)

    def tearDown(self):
        self.sandbox.restore()
        self._tmp.cleanup()

    # --- Stage: facts -----------------------------------------------------
    def test_duplicate_fact_id_fails(self):
        fact = {"fact_id": "F-R1-001", "solution_id": "R1", "subject": "s", "statement": "x",
                "source_id": "src-r1", "source_anchor": "a", "evidence_type": "author_stated"}
        self.sandbox.build(facts=[fact, fact], to="FACTS_READY")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("duplicate fact_id" in e for e in result["errors"]))

    def test_invalid_source_fails(self):
        fact = {"fact_id": "F-R1-001", "solution_id": "R1", "subject": "s", "statement": "x",
                "source_id": "nonexistent", "source_anchor": "a", "evidence_type": "author_stated"}
        self.sandbox.build(facts=[fact], to="FACTS_READY")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("not present in evidence-manifest" in e for e in result["errors"]))

    def test_cross_solution_attribution_fails(self):
        # flg/Ender regression shape: an R6 fact backed only by an R8 source.
        fact = {"fact_id": "F-R6-001", "solution_id": "R6", "subject": "s", "statement": "x",
                "source_id": "src-r8", "source_anchor": "a", "evidence_type": "author_stated"}
        self.sandbox.build(facts=[fact], to="FACTS_READY")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("FACT_ATTRIBUTION_ERROR" in e for e in result["errors"]))

    def test_writeup_only_fact_cannot_be_code_verified(self):
        fact = {"fact_id": "F-R2-001", "solution_id": "R2", "subject": "s", "statement": "x",
                "source_id": "src-r2", "source_anchor": "a", "evidence_type": "code_demonstrated"}
        self.sandbox.build(facts=[fact], to="FACTS_READY")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("writeup-only" in e for e in result["errors"]))

    def test_semantically_unsupported_fact_blocks(self):
        fact = {"fact_id": "F-R1-001", "solution_id": "R1", "subject": "s", "statement": "x",
                "source_id": "src-r1", "source_anchor": "a", "evidence_type": "author_stated"}
        self.sandbox.build(facts=[fact], fact_verdicts=[
            {"kind": "fact", "fact_id": "F-R1-001", "status": "FAIL",
             "reason": "The cited source does not support this statement."}], to="FACTS_READY")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("semantic verification FAIL" in e for e in result["errors"]))

    def test_evidence_binding_hash_is_required(self):
        run = self.sandbox.run("bound")
        MODULE.init_run("bound", "Demo", "test")
        run.coverage_plan_path.write_text(j({"document_kind":"test","expected_entities":["R1"],"required_axes_by_entity":{},"min_facts_per_entity":1,"output_contract":{"required_sections":[],"required_entity_labels":[],"min_chars_warning":0}}), encoding="utf-8")
        source = self.sandbox.root / "evidence.md"; source.write_text("Supported line\n", encoding="utf-8")
        run.manifest.write_text(j({"project":"Demo","scope":"test","sources":[{"source_id":"src-r1","solution_id":"R1","available":["writeup"]}]}), encoding="utf-8")
        fact = {"fact_id":"F-R1-001","solution_id":"R1","subject":"s","statement":"Supported line","source_id":"src-r1","source_anchor":{"kind":"file_lines","path":"evidence.md","start_line":1,"end_line":1},"evidence_ids":["EV-1"],"evidence_type":"author_stated"}
        write_jsonl(run.facts_path, [fact]); write_jsonl(run.facts_verify, [{"fact_id":"F-R1-001","status":"PASS","statement_sha256":hashlib.sha256(b"Supported line").hexdigest(),"evidence":[{"evidence_id":"EV-1","excerpt_sha256":"wrong"}]}])
        MODULE.run_verify("bound"); MODULE.run_verify("bound"); result = MODULE.run_verify("bound")
        self.assertFalse(result["ok"]); self.assertTrue(any("SEMANTIC_VERDICT_STALE" in e for e in result["errors"]))

    def test_structured_coverage_is_computed(self):
        claim = dict(VALID_CLAIM, coverage_mode="exact_count", eligible_entities=["R1", "R8"])
        run = self.sandbox.build(claims=[claim], claim_verdicts=[{"claim_id":"C-T-01","status":"PASS"}])
        result = MODULE.run_verify("t")
        self.assertTrue(result["ok"]); self.assertEqual(run.data()["claim_counts"]["C-T-01"]["support_count"], 2)

    def test_evidence_source_mismatch_is_blocked(self):
        run = self.sandbox.run("owner")
        MODULE.init_run("owner", "Demo", "test")
        run.coverage_plan_path.write_text(j({"document_kind":"test","expected_entities":["R1"],"required_axes_by_entity":{},"min_facts_per_entity":1,"output_contract":{"required_sections":[],"required_entity_labels":[],"min_chars_warning":0}}), encoding="utf-8")
        writeup = self.sandbox.root / "writeup.md"; writeup.write_text("claim\n", encoding="utf-8")
        run.manifest.write_text(j({"project":"Demo","scope":"test","sources":[{"source_id":"repo-source","solution_id":"R1","kind":"repository","path":"sources/repos/demo","available":["repository"]}]}), encoding="utf-8")
        fact = {"fact_id":"F-R1-001","solution_id":"R1","subject":"s","statement":"claim","source_id":"repo-source","source_anchor":{"kind":"file_lines","path":"writeup.md","start_line":1,"end_line":1},"evidence_ids":["EV-1"],"evidence_type":"code_demonstrated"}
        write_jsonl(run.facts_path, [fact]); write_jsonl(run.facts_verify, [])
        MODULE.run_verify("owner"); MODULE.run_verify("owner"); result = MODULE.run_verify("owner")
        self.assertFalse(result["ok"]); self.assertTrue(any("EVIDENCE_SOURCE_MISMATCH" in e for e in result["errors"]))

    def test_superseded_finalization_is_not_reported_as_drift(self):
        out = self.sandbox.root / "vault" / "x.md"; out.parent.mkdir(parents=True); out.write_text("new", encoding="utf-8")
        old_hash = hashlib.sha256(b"old").hexdigest(); new_hash = hashlib.sha256(b"new").hexdigest()
        self.sandbox.finalizations.parent.mkdir(parents=True, exist_ok=True)
        self.sandbox.finalizations.write_text(j({"entries":[{"run_id":"a","output":"vault/x.md","output_sha256":old_hash},{"run_id":"b","output":"vault/x.md","output_sha256":new_hash}]}), encoding="utf-8")
        self.assertFalse(any(i["kind"] == "UNVERIFIED_GENERATED_UPDATE" for i in MODULE.research_report()["issues"]))

    def test_missing_entity_coverage_blocks_fact_verification(self):
        run = self.sandbox.build(to="FACTS_READY")
        plan = json.loads(run.coverage_plan_path.read_text(encoding="utf-8"))
        plan["expected_entities"].append("R6")
        run.coverage_plan_path.write_text(j(plan), encoding="utf-8")
        # Re-establish the plan hash at the evidence-ready stage to test fact coverage itself.
        run.save(coverage_plan_sha256=MODULE.json_sha256_obj(plan))
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("KNOWLEDGE_COVERAGE_FAIL" in e for e in result["errors"]))

    def test_missing_required_axis_blocks_fact_verification(self):
        facts = [{"fact_id":"F-R1-001","solution_id":"R1","subject":"s","statement":"x","source_id":"src-r1","source_anchor":"a","evidence_type":"author_stated","axis":"model"}]
        run = self.sandbox.build(facts=facts, to="FACTS_READY")
        plan = json.loads(run.coverage_plan_path.read_text(encoding="utf-8"))
        plan["required_axes_by_entity"] = {"R1":["model","training"]}
        run.coverage_plan_path.write_text(j(plan), encoding="utf-8")
        run.save(coverage_plan_sha256=MODULE.json_sha256_obj(plan))
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("missing required axis 'training'" in e for e in result["errors"]))

    # --- Stage: claims ----------------------------------------------------
    def test_claim_with_unknown_fact_id_fails(self):
        claim = dict(VALID_CLAIM, support_fact_ids=["F-R1-999"])
        self.sandbox.build(claims=[claim])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("does not exist" in e for e in result["errors"]))

    def test_claim_with_failing_support_fact_fails(self):
        # AMBIGUOUS/FAIL facts may not back claims.
        fact = {"fact_id": "F-R1-001", "solution_id": "R1", "subject": "s", "statement": "x",
                "source_id": "src-r1", "source_anchor": "a", "evidence_type": "author_stated"}
        self.sandbox.build(facts=[fact], fact_verdicts=[
            {"kind": "fact", "fact_id": "F-R1-001", "status": "AMBIGUOUS", "reason": "unclear"}],
            claims=[dict(VALID_CLAIM, support_fact_ids=["F-R1-001"], eligible_entities=["R1"])])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("CLAIM_SUPPORT_FAIL" in e for e in result["errors"]))

    def test_universal_quantifier_coverage_enforced(self):
        claim = dict(VALID_CLAIM, statement="All solutions use behavioral-prior KL.",
                     eligible_entities=["R1", "R2", "R6", "R8"])
        self.sandbox.build(claims=[claim],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("UNIVERSAL_QUANTIFIER_FAIL" in e for e in result["errors"]))

    def test_claims_cannot_reference_raw_evidence(self):
        claim = dict(VALID_CLAIM, statement="See repo://demo@abc/model.py for details.")
        self.sandbox.build(claims=[claim])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("CLAIM_RAW_SOURCE_REF" in e for e in result["errors"]))

    def test_counterexample_field_is_required(self):
        claim = {k: v for k, v in VALID_CLAIM.items() if k != "counter_fact_ids"}
        self.sandbox.build(claims=[claim])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("counter_fact_ids is a required field" in e for e in result["errors"]))

    def test_claim_contradiction_blocks(self):
        self.sandbox.build(claims=[VALID_CLAIM], claim_verdicts=[
            {"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None},
            {"kind": "contradiction", "claims": ["C-T-01", "C-T-02"], "status": "FAIL", "resolution": None}])
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("CLAIM_CONTRADICTION" in e for e in result["errors"]))

    # --- Stage: mechanisms ------------------------------------------------
    def test_mechanism_conflation_blocks(self):
        self.sandbox.build(claims=[VALID_CLAIM],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
                           mechanisms=[VALID_MECH], mech_verdicts=[
                               {"kind": "mechanism", "mechanism_id": "M-T-01", "status": "PASS", "reason": None},
                               {"kind": "conflation", "mechanisms": ["M-T-01"], "status": "FAIL",
                                "reason": "teacher transfer merged into behavior-prior KL"}])
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        result = MODULE.run_verify("t")  # verify mechanisms
        self.assertFalse(result["ok"])
        self.assertTrue(any("MECHANISM_CONFLATION" in e for e in result["errors"]))

    def test_mechanism_duplicate_variable_blocks(self):
        mech = dict(VALID_MECH, mechanism_id="M-T-02")
        self.sandbox.build(claims=[VALID_CLAIM],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
                           mechanisms=[VALID_MECH, mech])
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("MECHANISM_DUPLICATE" in e for e in result["errors"]))

    # --- Stage: gate / draft / finalize -----------------------------------
    def gate_open(self, coverage_plan=None):
        self.sandbox.build(
            coverage_plan=coverage_plan,
            claims=[VALID_CLAIM],
            claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
            mechanisms=[VALID_MECH],
            mech_verdicts=[{"kind": "mechanism", "mechanism_id": "M-T-01", "status": "PASS", "reason": None}])
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        MODULE.run_verify("t")  # -> MECHANISMS_VERIFIED
        MODULE.run_verify("t")  # -> WRITE_ALLOWED
        run = self.sandbox.run("t")
        self.assertEqual(run.state(), "WRITE_ALLOWED")
        self.assertTrue((run.gate_path).is_file())

    def test_write_before_pass_is_blocked(self):
        self.sandbox.build(claims=[VALID_CLAIM])  # claims not verified yet
        result = MODULE.finalize_run(self.sandbox.run("t"), "vault/x.md")
        self.assertFalse(result["ok"])
        self.assertIn("blocked by research gate", result["error"])

    def test_finalize_without_final_verified_blocked(self):
        self.sandbox.build(claims=[VALID_CLAIM],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
                           mechanisms=[VALID_MECH], mech_verdicts=[
                               {"kind": "mechanism", "mechanism_id": "M-T-01", "status": "PASS", "reason": None}])
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        result = MODULE.finalize_run(self.sandbox.run("t"), "vault/x.md")
        self.assertFalse(result["ok"])
        self.assertIn("blocked by research gate", result["error"])

    def test_draft_with_stale_hashes_rejected(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Draft\n", encoding="utf-8")
        # Mutate a frozen fact after the gate opened.
        data = run.facts_path.read_text(encoding="utf-8").replace("Base entropy 0.01.", "Base entropy 0.02.")
        run.facts_path.write_text(data, encoding="utf-8")
        MODULE.verify_draft(run)  # WRITE_ALLOWED -> DRAFT_READY (structure only)
        result = MODULE.verify_draft(run)  # full final verification
        self.assertFalse(result["ok"])
        self.assertTrue(any("STALE_HASHES" in e for e in result["errors"]))

    def test_gate_is_revoked_when_frozen_facts_change(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.facts_path.write_text(run.facts_path.read_text(encoding="utf-8").replace("Base entropy 0.01.", "Base entropy changed."), encoding="utf-8")
        result = MODULE.status_run(run)
        self.assertFalse(result["write_allowed"])
        self.assertEqual(run.state(), "FACTS_READY")
        self.assertFalse((MODULE.read_json(run.gate_path) or {}).get("write_allowed"))

    def test_draft_trace_is_created_and_draft_mutation_blocks_finalize(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Draft\n", encoding="utf-8")
        MODULE.verify_draft(run)
        self.assertTrue(run.draft_trace_path.is_file())
        self.assertTrue(MODULE.verify_draft(run)["ok"])
        run.draft_path.write_text("# Mutated\n", encoding="utf-8")
        result = MODULE.finalize_run(run, "vault/x.md")
        self.assertFalse(result["ok"])
        self.assertIn("blocked by research gate", result["error"])

    def test_draft_with_unknown_ref_and_machine_path_rejected(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Draft\n\n<!-- KOS:refs=F-R9-999 -->\nSee repo://demo@abc/x.py.\n", encoding="utf-8")
        MODULE.verify_draft(run)  # -> DRAFT_READY
        result = MODULE.verify_draft(run)
        self.assertFalse(result["ok"])
        kinds = " ".join(result["errors"])
        self.assertIn("not found in verified artifacts", kinds)
        self.assertIn("MACHINE_PATH_LEAK", kinds)

    def test_universal_wording_in_traced_block_requires_full_coverage_claim(self):
        claim = dict(VALID_CLAIM, statement="Behavioral-prior KL appears.", eligible_entities=["R1", "R8"])
        self.sandbox.build(claims=[claim],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
                           mechanisms=[VALID_MECH], mech_verdicts=[
                               {"kind": "mechanism", "mechanism_id": "M-T-01", "status": "PASS", "reason": None}])
        run = self.sandbox.run("t")
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        self.assertTrue(MODULE.run_verify("t")["ok"])  # -> MECHANISMS_VERIFIED
        self.assertTrue(MODULE.run_verify("t")["ok"])  # -> WRITE_ALLOWED
        run.draft_path.write_text(
            "# Draft\n\n<!-- KOS:refs=C-T-01 -->\nAll eight solutions adopted this mechanism.\n", encoding="utf-8")
        self.assertTrue(MODULE.verify_draft(run)["ok"])  # WRITE_ALLOWED -> DRAFT_READY
        result = MODULE.verify_draft(run)                # full final verification
        self.assertFalse(result["ok"])
        self.assertTrue(any("UNIVERSAL_WORDING_UNVERIFIED" in e for e in result["errors"]))
        self.assertEqual(run.state(), "DRAFT_READY")  # stays; never advances on failure

    def test_finalize_strips_markers_atomically_and_records_manifest(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.draft_path.write_text(
            "---\ntype: project-doc\n---\n# Demo\n\n<!-- KOS:refs=F-R1-001,C-T-01 -->\nEntropy is 0.01.\n", encoding="utf-8")
        MODULE.verify_draft(run)  # WRITE_ALLOWED -> DRAFT_READY
        self.assertTrue(MODULE.verify_draft(run)["ok"])  # -> FINAL_VERIFIED
        target = self.sandbox.vault / "projects" / "Demo" / "Demo.md"
        result = MODULE.finalize_run(run, str(target))
        self.assertTrue(result["ok"])
        final_text = target.read_text(encoding="utf-8")
        self.assertNotIn("KOS:", final_text)
        self.assertIn("Entropy is 0.01.", final_text)
        manifest = json.loads(MODULE.FINALIZATIONS_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["entries"][0]["run_id"], "t")
        self.assertEqual(run.state(), "COMMITTED")

    def test_finalize_refuses_human_owned_target(self):
        self.gate_open()
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Demo\n", encoding="utf-8")
        MODULE.verify_draft(run)  # -> DRAFT_READY
        MODULE.verify_draft(run)  # -> FINAL_VERIFIED
        target = self.sandbox.vault / "human.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\norigin: human\n---\n# Mine\n", encoding="utf-8")
        result = MODULE.finalize_run(run, str(target))
        self.assertFalse(result["ok"])
        self.assertIn("human-owned", result["error"])

    # --- State machine ----------------------------------------------------
    def test_state_machine_cannot_skip_stages(self):
        run = self.sandbox.build()
        self.assertEqual(run.state(), "FACTS_FROZEN")
        # FACTS_FROZEN without claims cannot reach CLAIMS_VERIFIED.
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertEqual(run.state(), "FACTS_FROZEN")
        # INIT of a fresh run cannot jump to WRITE_ALLOWED.
        MODULE.init_run("t2", "Demo", "test")
        self.sandbox.run("t2").coverage_plan_path.write_text(j({"document_kind":"test","expected_entities":["R1"],"required_axes_by_entity":{},"min_facts_per_entity":1,"output_contract":{"required_sections":[],"required_entity_labels":[],"min_chars_warning":0}}), encoding="utf-8")
        result = MODULE.run_verify("t2")
        self.assertFalse(result["ok"])
        self.assertEqual(MODULE.Run("t2").state(), "INIT")

    def test_direct_state_edit_is_rejected_by_transition_journal(self):
        self.sandbox.build()
        run = self.sandbox.run("t")
        payload = MODULE.read_json(run.run_json)
        payload["state"] = "FINAL_VERIFIED"
        run.run_json.write_text(json.dumps(payload), encoding="utf-8")
        result = MODULE.run_verify("t")
        self.assertFalse(result["ok"])
        self.assertTrue(any("STATE_HISTORY_STATE_MISMATCH" in e for e in result["errors"]))
        result = MODULE.finalize_run(run, "vault/x.md")
        self.assertFalse(result["ok"])
        self.assertIn("blocked by research gate", result["error"])

    def test_failed_mechanism_blocks_write_allowed(self):
        self.sandbox.build(claims=[VALID_CLAIM],
                           claim_verdicts=[{"kind": "claim", "claim_id": "C-T-01", "status": "PASS", "reason": None}],
                           mechanisms=[VALID_MECH], mech_verdicts=[
                               {"kind": "mechanism", "mechanism_id": "M-T-01", "status": "FAIL",
                                "reason": "changed_variable not supported"}])
        MODULE.run_verify("t")  # -> CLAIMS_VERIFIED
        result = MODULE.run_verify("t")  # mechanism verification must fail
        self.assertFalse(result["ok"])
        self.assertNotEqual(self.sandbox.run("t").state(), "WRITE_ALLOWED")
        self.assertFalse((MODULE.read_json(self.sandbox.run("t").gate_path) or {}).get("write_allowed"))

    def test_draft_completeness_contract_blocks_missing_sections_and_entities(self):
        plan = {"document_kind":"solutions","expected_entities":["R1","R8"],"required_axes_by_entity":{},"min_facts_per_entity":1,
                "output_contract":{"required_sections":["Problem","Evidence Map"],"required_entity_labels":["R1","R8"],"min_chars_warning":0}}
        self.gate_open(coverage_plan=plan)
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Draft\n## Problem\nR1 only\n", encoding="utf-8")
        MODULE.verify_draft(run)
        result = MODULE.verify_draft(run)
        self.assertFalse(result["ok"])
        self.assertTrue(any("DOCUMENT_COMPLETENESS_FAIL" in e for e in result["errors"]))

    def test_thin_output_emits_warning(self):
        plan = {"document_kind":"solutions","expected_entities":["R1","R8"],"required_axes_by_entity":{},"min_facts_per_entity":1,
                "output_contract":{"required_sections":[],"required_entity_labels":[],"min_chars_warning":100}}
        self.gate_open(coverage_plan=plan)
        run = self.sandbox.run("t")
        run.draft_path.write_text("# Tiny\n", encoding="utf-8")
        MODULE.verify_draft(run)
        result = MODULE.verify_draft(run)
        self.assertTrue(result["ok"])
        self.assertTrue(any("SUSPICIOUSLY_THIN_OUTPUT" in w for w in result.get("warnings", [])))

    # --- maintain integration --------------------------------------------
    def test_maintain_reports_frozen_fact_drift(self):
        self.gate_open()
        run = self.sandbox.run("t")
        records = [json.loads(x) for x in run.facts_path.read_text(encoding="utf-8").splitlines()]
        records[0]["statement"] = "tampered"
        write_jsonl(run.facts_path, records)
        report = MODULE.research_report()
        kinds = [x["kind"] for x in report["issues"]]
        self.assertIn("FACT_MATRIX_STALE", kinds)

    def test_maintain_reports_claim_support_drift(self):
        self.gate_open()
        run = self.sandbox.run("t")
        records = [json.loads(x) for x in run.facts_path.read_text(encoding="utf-8").splitlines()]
        write_jsonl(run.facts_path, records[1:])  # drop F-R1-001, still supporting C-T-01
        kinds = [x["kind"] for x in MODULE.research_report()["issues"]]
        self.assertIn("CLAIM_SUPPORT_DRIFT", kinds)


class OrbitWarsRegressionTest(unittest.TestCase):
    """Spec §39: the five fixed regression cases against real OrbitWars facts."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.sandbox = GateSandbox(self._tmp.name)

    def tearDown(self):
        self.sandbox.restore()
        self._tmp.cleanup()

    ENTITIES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"]

    def manifest_sources(self):
        out = []
        for rank, sid in enumerate(self.ENTITIES, 1):
            out.append({"source_id": f"ow-r{sid}", "solution_id": sid,
                        "available": ["writeup"] + (["repository"] if sid in {"R1", "R2", "R5", "R6", "R8"} else [])})
        return out

    def build_ow(self, facts, claims=None, claim_verdicts=None, to="FACTS_FROZEN"):
        run = self.sandbox.run("ow")
        MODULE.init_run("ow", "OrbitWars", "solution-space")
        run.manifest.write_text(j({"project": "OrbitWars", "scope": "solution-space",
                                   "sources": self.manifest_sources()}), encoding="utf-8")
        write_jsonl(run.facts_path, facts)
        entities = sorted({str(f.get("solution_id")) for f in facts if f.get("solution_id")})
        run.coverage_plan_path.write_text(j({"document_kind":"solution-space","expected_entities":entities,"required_axes_by_entity":{},"min_facts_per_entity":1,"output_contract":{"required_sections":[],"required_entity_labels":[],"min_chars_warning":0}}), encoding="utf-8")
        write_jsonl(run.facts_verify, [{"kind": "fact", "fact_id": f["fact_id"], "status": "PASS", "reason": None}
                                       for f in facts])
        assert MODULE.run_verify("ow")["ok"]          # -> EVIDENCE_READY
        if to != "FACTS_READY":
            while run.state() != "FACTS_FROZEN":
                assert MODULE.run_verify("ow")["ok"]
        elif run.state() == "EVIDENCE_READY":
            assert MODULE.run_verify("ow")["ok"]      # -> FACTS_READY
        if claims is not None:
            write_jsonl(run.claims_path, claims)
            write_jsonl(run.claims_verify, claim_verdicts or [])
        return run

    def fact(self, entity, statement, code=False):
        sid = self.ENTITIES[int(entity[1:]) - 1]
        return {"fact_id": f"F-{entity}-001", "solution_id": entity, "subject": "s", "statement": statement,
                "source_id": f"ow-r{entity}", "source_anchor": "writeup:sol",
                "evidence_type": "author_stated"}

    def regression1(self):
        return [self.fact("R6", "Ender-style behavioral-prior KL on halt/fraction heads.")]

    def test_regression_1_flg_ender_attribution(self):
        # The Ender mechanism must not be attributed to flg: an R6 fact whose only
        # available source is R8's must fail attribution.
        fact = self.fact("R6", "Behavioral-prior KL on halt/fraction heads.")
        fact["source_id"] = "ow-rR8"  # Ender's source, misattributed to an R6 fact
        run = self.build_ow([fact], to="FACTS_READY")
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        self.assertTrue(any("FACT_ATTRIBUTION_ERROR" in e for e in result["errors"]))
        self.assertEqual(run.state(), "FACTS_READY")  # stays; never advances
        # Fixing the attribution (fact belongs to R8/Ender) lets verification pass.
        fixed = dict(fact, fact_id="F-R8-002", solution_id="R8")
        write_jsonl(run.facts_path, [fixed])
        plan = json.loads(run.coverage_plan_path.read_text(encoding="utf-8")); plan["expected_entities"] = ["R8"]
        run.coverage_plan_path.write_text(j(plan), encoding="utf-8"); run.save(coverage_plan_sha256=MODULE.json_sha256_obj(plan))
        write_jsonl(run.facts_verify, [{"kind": "fact", "fact_id": "F-R8-002", "status": "PASS", "reason": None}])
        self.assertTrue(MODULE.run_verify("ow")["ok"])

    def test_regression_2_simjeg_regret_claim_fails(self):
        facts = [self.fact("R1", "Isaiah regretted pure self-play."),
                 self.fact("R2", "SimJeg removed frozen checkpoints from final training.")]
        claim = {"claim_id": "C-REG-01", "claim_type": "convergence",
                 "statement": "Isaiah and SimJeg both explicitly regretted not using historical opponents.",
                 "support_fact_ids": ["F-R1-001"], "counter_fact_ids": [],
                 "eligible_entities": ["R1", "R2"], "boundary": ""}
        run = self.build_ow(facts, [claim])
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        self.assertTrue(any("UNIVERSAL_QUANTIFIER_FAIL" in e for e in result["errors"]),
                        "SimJeg fact does not state regret; 'both' requires it from every covered entity")
        # Even citing the SimJeg fact cannot help: it never states regret, so the
        # semantic verifier must FAIL the claim.
        write_jsonl(run.claims_path, [dict(claim, support_fact_ids=["F-R1-001", "F-R2-001"])])
        write_jsonl(run.claims_verify, [
            {"kind": "claim", "claim_id": "C-REG-01", "status": "FAIL",
             "reason": "The SimJeg fact reports removal of frozen checkpoints, not regret."}])
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        self.assertTrue(any("CLAIM_VERIFY_FAIL" in e for e in result["errors"]))

    def test_regression_3_reward_shaping_universal_fails(self):
        facts = [self.fact("R7", "Audun dense shaping experiments failed (34.6%)."),
                 self.fact("R6", "flg dense reward scaffolded teacher transfer."),
                 self.fact("R1", "Isaiah used terminal rewards only.")]
        claim = {"claim_id": "C-REW-01", "claim_type": "convergence",
                 "statement": "Dense shaping was rejected by all top solutions.",
                 "support_fact_ids": ["F-R7-001"], "counter_fact_ids": ["F-R6-001"],
                 "eligible_entities": self.ENTITIES, "boundary": ""}
        run = self.build_ow(facts, [claim])
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        errors = " ".join(result["errors"])
        self.assertIn("UNIVERSAL_QUANTIFIER_FAIL", errors)

    def test_regression_4_future_horizon_universal_fails(self):
        facts = [self.fact("R2", "Hober future horizon is about 19 steps."),
                 self.fact("R8", "Ender future projection horizon is about 24 steps."),
                 self.fact("R7", "Audun auxiliary prediction targets are 2/8/32/64 steps.")]
        claim = {"claim_id": "C-HOR-01", "claim_type": "convergence",
                 "statement": "All future-state interfaces use 16-24 turns.",
                 "support_fact_ids": ["F-R2-001", "F-R8-001"], "counter_fact_ids": ["F-R7-001"],
                 "eligible_entities": self.ENTITIES, "boundary": ""}
        run = self.build_ow(facts, [claim])
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        self.assertTrue(any("UNIVERSAL_QUANTIFIER_FAIL" in e for e in result["errors"]))

    def test_regression_5_counterexample_must_change_principle(self):
        facts = [self.fact("R3", "Felix exposes reachability tensor at the interface."),
                 self.fact("R1", "Isaiah succeeded with low-level representation, 200M params, 15B steps, first place.")]
        bad = {"claim_id": "C-PRIN-01", "claim_type": "principle",
               "statement": "Future consequence belongs in the interface, not the policy.",
               "support_fact_ids": ["F-R3-001"], "counter_fact_ids": ["F-R1-001"],
               "eligible_entities": ["R1", "R3"], "boundary": ""}
        run = self.build_ow(facts, [bad])
        result = MODULE.run_verify("ow")
        self.assertFalse(result["ok"])
        self.assertTrue(any("COUNTEREXAMPLE_DECORATIVE" in e for e in result["errors"]))
        # Calibrated rewrite: conditional wording + explicit boundary absorbs the counterexample.
        good = dict(bad,
                    statement="Cheap, exact, reusable environment structure should usually be exposed at the policy interface.",
                    boundary="Scaling can substitute for interface structure: Isaiah's 200M/15B low-level route reached first place.")
        write_jsonl(run.claims_path, [good])
        write_jsonl(run.claims_verify, [{"kind": "claim", "claim_id": "C-PRIN-01", "status": "PASS", "reason": None}])
        result = MODULE.run_verify("ow")
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(run.state(), "CLAIMS_VERIFIED")


if __name__ == "__main__":
    unittest.main()
