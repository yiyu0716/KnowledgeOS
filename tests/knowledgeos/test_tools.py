import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("knowledgeos_tools", ROOT / "tools/knowledgeos.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class KnowledgeOSToolsTest(unittest.TestCase):
    def tearDown(self):
        MODULE.ROOT = ROOT
        MODULE.VAULT = ROOT / "vault"

    def test_search_supports_mixed_language(self):
        results = MODULE.bm25("provenance 知识", limit=10)
        self.assertTrue(any(x.get("type") == "learning" for x in results))

    def test_vector_search_is_graceful(self):
        results, warning = MODULE.vector_search("test query", limit=5)
        self.assertTrue(results or warning)


    def test_search_returns_explainable_context(self):
        results = MODULE.bm25("对手分布", limit=5)
        self.assertTrue(results)
        self.assertTrue(all("snippet" in x and "matched_terms" in x for x in results))
        self.assertEqual(results[0]["type"], "project-doc")

        graph = MODULE.build_graph()
        self.assertTrue(any(e["kind"] == "projects" for e in graph["edges"]))
        self.assertTrue(any("OrbitWars" in e["target"] for e in graph["edges"]))
        self.assertTrue(any(e["kind"] == "source_refs" for e in graph["edges"]))

    def test_rrf_uses_rank_one_and_k_sixty(self):
        self.assertAlmostEqual(MODULE.rrf_score([1, 1]), 2 / 61)
        self.assertAlmostEqual(MODULE.rrf_score([1, 2]), 1 / 61 + 1 / 62)

    def test_vector_disabled_keeps_bm25_search(self):
        old = MODULE.CONFIG.read_text(encoding="utf-8")
        MODULE.CONFIG.write_text(old.replace("vector: true", "vector: false"), encoding="utf-8")
        try:
            self.assertFalse(MODULE.vector_enabled())
            self.assertTrue(MODULE.bm25("feasibility layer", limit=3))
        finally:
            MODULE.CONFIG.write_text(old, encoding="utf-8")


        graph = MODULE.build_graph()
        ids = {n["id"] for n in graph["nodes"]}
        self.assertIn("projects/OrbitWars/OrbitWars", ids)
        self.assertFalse(graph["wanted_links"])
        self.assertTrue(any(e["target"] == "projects/OrbitWars/OrbitWars" for e in graph["edges"]))

    def test_resolver_prefers_same_folder_and_rejects_ambiguous_global_name(self):
        aliases = {"solution-space": ["projects/A/solution-space", "projects/B/solution-space"]}
        self.assertEqual(MODULE.resolve_note_link("solution-space", aliases, "projects/A/notes"), "projects/A/solution-space")
        self.assertIsNone(MODULE.resolve_note_link("solution-space", aliases, "projects/C/notes"))

    def test_project_projection_is_separate(self):
        pgraph = MODULE.project_graph()
        self.assertEqual(set(pgraph["nodes"]), {"projects/KnowledgeOS/KnowledgeOS", "projects/OrbitWars/OrbitWars"})
        self.assertEqual(pgraph["roots"], ["projects/KnowledgeOS/KnowledgeOS"])
        self.assertEqual(pgraph["edges"], [{"parent": "projects/KnowledgeOS/KnowledgeOS", "child": "projects/OrbitWars/OrbitWars"}])
        self.assertFalse(pgraph["unresolved_parents"])
        self.assertFalse(pgraph["cycles"])

    def test_project_graph_supports_multiple_parents(self):
        old_vault = MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            for name in ("A", "X", "E"):
                (vault / "projects" / name).mkdir(parents=True)
            (vault / "projects/A/A.md").write_text("---\ntype: project\nparents: []\n---\n")
            (vault / "projects/X/X.md").write_text("---\ntype: project\nparents: []\n---\n")
            (vault / "projects/E/E.md").write_text("---\ntype: project\nparents:\n  - \"[[A]]\"\n  - \"[[X]]\"\n---\n")
            MODULE.VAULT = vault
            pgraph = MODULE.project_graph()
            self.assertEqual({(e["parent"], e["child"]) for e in pgraph["edges"]}, {("projects/A/A", "projects/E/E"), ("projects/X/X", "projects/E/E")})
            self.assertIn("projects/E/E", pgraph["multi_parent"])
        MODULE.VAULT = old_vault

    def test_project_graph_reports_invalid_parent_and_cycle(self):
        old_vault = MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            for name, body in {
                "A": 'parents:\n  - "[[B]]"\n',
                "B": 'parents:\n  - "[[A]]"\n',
                "C": 'parents:\n  - "[[Missing]]"\n',
            }.items():
                folder = vault / "projects" / name; folder.mkdir(parents=True)
                (folder / f"{name}.md").write_text(f"---\ntype: project\n{body}---\n")
            MODULE.VAULT = vault
            pgraph = MODULE.project_graph()
            self.assertTrue(pgraph["cycles"])
            self.assertTrue(any(x["target"] == "Missing" for x in pgraph["unresolved_parents"]))
        MODULE.VAULT = old_vault

    def test_maintain_reports_source_drift(self):
        old_root, old_vault = MODULE.ROOT, MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = root / "sources/repos/demo"
            repo.mkdir(parents=True); (repo / "model.py").write_text("a\n")
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True); subprocess.run(["git", "-C", str(repo), "commit", "-qm", "A"], check=True)
            first = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            (repo / "model.py").write_text("b\n"); subprocess.run(["git", "-C", str(repo), "commit", "-qam", "B"], check=True)
            vault = root / "vault/projects/Demo"; vault.mkdir(parents=True)
            (vault / "Demo.md").write_text("---\ntype: project\n---\n# Demo\n")
            (vault / "notes.md").write_text(f"---\ntype: project-doc\nsource_refs:\n  - repo://demo@{first}/model.py\nderived_from:\n  - \"[[Demo]]\"\n---\n# Notes\n")
            reg = root / "registry"; reg.mkdir(); (reg / "demo.yaml").write_text(f"repositories:\n  - rank: 1\n    local_path: sources/repos/demo\n    head: {first}\n")
            MODULE.ROOT, MODULE.VAULT = root, root / "vault"
            report = MODULE.maintain()
            self.assertEqual(len(report["source_drift"]), 1)
            self.assertIn("projects/Demo/notes", report["source_drift"][0]["direct_impacted"])
        MODULE.ROOT, MODULE.VAULT = old_root, old_vault

    def test_stable_source_drift_finds_impacted_note(self):
        old_root, old_vault = MODULE.ROOT, MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); repo = root / "sources/repos/demo"; repo.mkdir(parents=True); (repo / "model.py").write_text("a\n")
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True); subprocess.run(["git", "-C", str(repo), "config", "user.email", "a@b"], check=True); subprocess.run(["git", "-C", str(repo), "config", "user.name", "A"], check=True); subprocess.run(["git", "-C", str(repo), "add", "."], check=True); subprocess.run(["git", "-C", str(repo), "commit", "-qm", "A"], check=True)
            first = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(); (repo / "model.py").write_text("b\n"); subprocess.run(["git", "-C", str(repo), "commit", "-qam", "B"], check=True)
            vault = root / "vault/projects/Demo"; vault.mkdir(parents=True); (vault / "Demo.md").write_text("---\ntype: project\n---\n# Demo\n"); (vault / "notes.md").write_text("---\ntype: project-doc\nsource_refs:\n  - source:demo-repo\n---\n# Notes\n")
            reg = root / "registry"; reg.mkdir(); (reg / "demo.yaml").write_text(f"repositories:\n  - id: demo-repo\n    local_path: sources/repos/demo\n    head: {first}\n")
            MODULE.ROOT, MODULE.VAULT = root, root / "vault"; report = MODULE.maintain()
            self.assertIn("projects/Demo/notes", report["source_drift"][0]["direct_impacted"])
        MODULE.ROOT, MODULE.VAULT = old_root, old_vault

    def test_knowledge_density_reports_thin_canonical_docs(self):
        old_root, old_vault = MODULE.ROOT, MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault/projects/Demo"; vault.mkdir(parents=True)
            (vault / "solutions.md").write_text("---\ntype: project-doc\nsource_refs: [source:a, source:b, source:c, source:d]\n---\n# Solutions\nTiny\n", encoding="utf-8")
            MODULE.ROOT, MODULE.VAULT = root, root / "vault"
            issues = MODULE.knowledge_density_report()
            self.assertTrue(any(i["kind"] == "SUSPICIOUSLY_THIN_OUTPUT" for i in issues))
        MODULE.ROOT, MODULE.VAULT = old_root, old_vault

    def test_claim_ledger_stale_is_reported(self):
        import os
        from datetime import datetime, timedelta
        old_root, old_vault = MODULE.ROOT, MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault" / "projects" / "Demo"
            vault.mkdir(parents=True)
            ledger = vault / "claims.yaml"
            ledger.write_text("schema_version: 1\nupdated: 2020-01-01\nclaims: []\n", encoding="utf-8")
            doc = vault / "solution-space.md"
            doc.write_text("# Synthesis\n", encoding="utf-8")
            fresh = datetime.now() - timedelta(days=1)
            os.utime(doc, (fresh.timestamp(), fresh.timestamp()))
            MODULE.VAULT = Path(tmp) / "vault"
            MODULE.ROOT = Path(tmp)
            issues = MODULE.claim_ledger_report()
            self.assertTrue(any(i["kind"] == "CLAIM_LEDGER_STALE" for i in issues))
            # Fresh ledger (updated >= newest sibling change) is not flagged.
            ledger.write_text(f"schema_version: 1\nupdated: {fresh.date().isoformat()}\nclaims: []\n", encoding="utf-8")
            self.assertFalse(MODULE.claim_ledger_report())
        MODULE.ROOT, MODULE.VAULT = old_root, old_vault

    def test_claim_ledger_manual_edit_is_reported(self):
        old_root, old_vault = MODULE.ROOT, MODULE.VAULT
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault/projects/Demo"; vault.mkdir(parents=True)
            run = root / ".knowledgeos/runs/r1"; run.mkdir(parents=True)
            claim = {"claim_id":"C1","durable":True,"statement":"original"}
            canon = __import__('json').dumps(claim, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            import hashlib
            digest = hashlib.sha256(canon.encode()).hexdigest()
            (run / "run.json").write_text('{"state":"COMMITTED"}'); (run / "gate.json").write_text('{}'); (run / "claims.jsonl").write_text(canon + "\n")
            (vault / "claims.yaml").write_text(f"schema_version: 1\ngenerated_from_run: r1\ndurable_claims_sha256: {digest}\nclaims:\n  - {canon}\n")
            (vault / "claims.yaml").write_text(f"schema_version: 1\ngenerated_from_run: r1\ndurable_claims_sha256: {digest}\nclaims:\n  - {{\"claim_id\":\"C1\",\"durable\":true,\"statement\":\"tampered\"}}\n")
            MODULE.ROOT, MODULE.VAULT = root, root / "vault"; self.assertTrue(any(i["kind"] == "CLAIM_LEDGER_DRIFT" for i in MODULE.claim_ledger_report()))
        MODULE.ROOT, MODULE.VAULT = old_root, old_vault


if __name__ == "__main__":
    unittest.main()
