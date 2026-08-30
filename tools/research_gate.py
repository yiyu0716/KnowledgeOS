#!/usr/bin/env python3
"""Research Gate: stateful, hash-frozen, hard-gated research runs for KnowledgeOS.

Pipeline:
    Evidence -> Verified Frozen Facts -> Verified Claims -> Verified Mechanisms
    -> WRITE_ALLOWED -> Draft -> Final Verification -> Final Markdown

All gate state lives under .knowledgeos/runs/<run-id>/ as derived machine state.
gate.json is only ever written by this tool; agents write facts/claims/mechanisms
artifacts and semantic verify files, then ask the tool to verify each stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from source_registry import resolve_source
DERIVED = ROOT / ".knowledgeos"
RUNS_DIR = DERIVED / "runs"
FINALIZATIONS_PATH = DERIVED / "finalizations.json"

STATES = [
    "INIT", "EVIDENCE_READY", "FACTS_READY", "FACTS_VERIFIED", "FACTS_FROZEN",
    "CLAIMS_VERIFIED", "MECHANISMS_VERIFIED",
    "WRITE_ALLOWED", "DRAFT_READY", "FINAL_VERIFIED", "COMMITTED",
]
ALLOWED_TRANSITIONS = {
    "INIT": "EVIDENCE_READY",
    "EVIDENCE_READY": "FACTS_READY",
    "FACTS_READY": "FACTS_VERIFIED",
    "FACTS_VERIFIED": "FACTS_FROZEN",
    "FACTS_FROZEN": "CLAIMS_VERIFIED",
    "CLAIMS_VERIFIED": "MECHANISMS_VERIFIED",
    "MECHANISMS_VERIFIED": "WRITE_ALLOWED",
    "WRITE_ALLOWED": "DRAFT_READY",
    "DRAFT_READY": "FINAL_VERIFIED",
    "FINAL_VERIFIED": "COMMITTED",
}

EVIDENCE_TYPES = {"code_demonstrated", "author_stated", "experiment_reported", "derived_numeric"}
CLAIM_TYPES = {"convergence", "alternative", "negative", "mechanism", "principle", "open_question"}
VERIFY_STATUSES = {"PASS", "FAIL", "AMBIGUOUS"}
COUNTEREXAMPLE_TYPES = {"convergence", "mechanism", "principle"}
STRONG_TYPES = {"convergence", "mechanism", "principle"}
MECHANISM_FIELDS = ["mechanism_id", "intervention", "changed_variable", "expected_effect", "support_claim_ids"]

KOS_MARKER_RE = re.compile(r"<!--\s*KOS:refs=([A-Za-z0-9_,\- ]+)\s*-->")
MACHINE_PATH_RE = re.compile(r"repo://|writeup://|paper://|experiment://|sources/(repos|writeups|papers)/|registry/")
UNIVERSAL_WORDS = ["all", "every", "none", "only", "never", "both", "全部", "所有", "唯一", "从不", "必须", "总是", "一定", "都", "均", "各方案", "各个", "各自", "两者", "全体", "无一例外"]
FACT_ID_RE = re.compile(r"^(F)-([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)-(\d+)$")
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
# Spec §28: counts in drafts must come from the computed support set, not the model.
COUNT_TOKEN_RE = re.compile(
    rf"\b(\d+|{'|'.join(WORD_NUMBERS)})\s+(solutions?|approaches?|entities|methods?|adopters?|方案|家)\b",
    re.IGNORECASE)


# ---------------------------------------------------------------- primitives

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_line(record: dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def jsonl_sha256(records: list[dict]) -> str:
    payload = "\n".join(canonical_line(x) for x in sorted(records, key=lambda r: r.get("fact_id") or r.get("claim_id") or r.get("mechanism_id") or "")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def json_sha256_obj(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records, errors = [], []
    if not path.is_file():
        return records, [f"missing file: {path.name}"]
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{lineno}: invalid JSON ({exc})")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path.name}:{lineno}: not a JSON object")
            continue
        records.append(record)
    return records, errors

def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(canonical_line(x) for x in records) + ("\n" if records else ""), encoding="utf-8")


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Run:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.dir = RUNS_DIR / run_id
        self.run_json = self.dir / "run.json"
        self.history_path = self.dir / "state-history.jsonl"
        self.manifest = self.dir / "evidence-manifest.json"
        self.coverage_plan_path = self.dir / "coverage-plan.json"
        self.facts_path = self.dir / "facts.jsonl"
        self.facts_verify = self.dir / "facts.verify.jsonl"
        self.evidence_bindings_path = self.dir / "evidence-bindings.jsonl"
        self.claims_path = self.dir / "claims.jsonl"
        self.claims_verify = self.dir / "claims.verify.jsonl"
        self.mechanisms_path = self.dir / "mechanisms.jsonl"
        self.mechanisms_verify = self.dir / "mechanisms.verify.jsonl"
        self.gate_path = self.dir / "gate.json"
        self.draft_path = self.dir / "draft.md"
        self.draft_trace_path = self.dir / "draft-trace.json"
        self.draft_verify_path = self.dir / "draft.verify.json"
        self.report_path = self.dir / "report.json"

    def exists(self) -> bool:
        return self.run_json.is_file()

    def state(self) -> str:
        data = read_json(self.run_json)
        return (data or {}).get("state", "INIT")

    def data(self) -> dict:
        return read_json(self.run_json) or {}

    def save(self, **updates) -> dict:
        payload = self.data()
        previous_state = payload.get("state")
        payload.update(updates)
        payload["run_id"] = self.run_id
        payload.setdefault("created_at", utc_now())
        payload["updated_at"] = utc_now()
        write_json_atomic(self.run_json, payload)
        if "state" in updates and updates["state"] != previous_state:
            self.append_transition(str(updates["state"]))
        return payload

    def append_transition(self, state: str) -> None:
        previous_hash = ""
        seq = 0
        if self.history_path.is_file():
            lines = [x for x in self.history_path.read_text(encoding="utf-8").splitlines() if x.strip()]
            if lines:
                prior = json.loads(lines[-1])
                previous_hash = prior.get("entry_sha256", "")
                seq = int(prior.get("seq", 0)) + 1
        entry = {"seq": seq, "state": state, "previous_sha256": previous_hash}
        entry["entry_sha256"] = hashlib.sha256(canonical_line(entry).encode("utf-8")).hexdigest()
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_line(entry) + "\n")

    def validate_state_history(self) -> list[str]:
        if not self.history_path.is_file():
            return []  # legacy runs created before the journal was introduced
        errors: list[str] = []
        previous_hash = ""
        previous_state = None
        expected_seq = 0
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                errors.append("STATE_HISTORY_INVALID_JSON")
                continue
            if entry.get("seq") != expected_seq or entry.get("previous_sha256", "") != previous_hash:
                errors.append("STATE_HISTORY_CHAIN_INVALID")
            unsigned = {k: entry.get(k) for k in ("seq", "state", "previous_sha256")}
            expected_hash = hashlib.sha256(canonical_line(unsigned).encode("utf-8")).hexdigest()
            if entry.get("entry_sha256") != expected_hash:
                errors.append("STATE_HISTORY_HASH_INVALID")
            state = entry.get("state")
            if state not in STATES:
                errors.append(f"STATE_HISTORY_UNKNOWN_STATE:{state}")
            rollback = state == "FACTS_READY" and previous_state not in {"INIT", "EVIDENCE_READY", "FACTS_READY"}
            if previous_state is not None and ALLOWED_TRANSITIONS.get(previous_state) != state and not rollback:
                errors.append(f"STATE_TRANSITION_INVALID:{previous_state}->{state}")
            previous_hash = entry.get("entry_sha256", "")
            previous_state = state
            expected_seq += 1
        if previous_state != self.state():
            errors.append(f"STATE_HISTORY_STATE_MISMATCH:{previous_state}->{self.state()}")
        return sorted(set(errors))

    def fail(self, stage: str, errors: list[str]) -> dict:
        data = self.save(last_verify={"stage": stage, "ok": False, "errors": errors, "at": utc_now()})
        return {"run": self.run_id, "state": data["state"], "advanced_to": None,
                "ok": False, "stage": stage, "errors": errors}

    def revoke_gate(self, reason: str) -> None:
        if self.gate_path.is_file():
            write_json_atomic(self.gate_path, {
                "state": self.state(), "write_allowed": False,
                "revoked_at": utc_now(), "reason": reason,
            })
        data = self.data()
        if data.get("state") in {"WRITE_ALLOWED", "DRAFT_READY", "FINAL_VERIFIED"}:
            self.save(state="FACTS_READY", gate_revoked=True)

    def advance(self, stage: str, new_state: str, extra: dict | None = None, warnings: list[str] | None = None) -> dict:
        updates = {"state": new_state,
                   "last_verify": {"stage": stage, "ok": True, "errors": [], "at": utc_now()}}
        if extra:
            updates.update(extra)
        self.save(**updates)
        return {"run": self.run_id, "state": new_state, "advanced_to": new_state,
                "ok": True, "stage": stage, "errors": [], "warnings": warnings or []}


def init_run(run_id: str, project: str, scope: str) -> dict:
    run = Run(run_id)
    if run.exists():
        return {"run": run_id, "state": run.state(), "ok": False,
                "errors": ["run already exists"]}
    run.dir.mkdir(parents=True, exist_ok=False)
    payload = {"run_id": run_id, "project": project, "scope": scope, "state": "INIT",
               "created_at": utc_now(), "updated_at": utc_now()}
    write_json_atomic(run.run_json, payload)
    run.append_transition("INIT")
    write_json_atomic(run.gate_path, {"state": "INIT", "write_allowed": False, "created_at": utc_now()})
    write_json_atomic(run.manifest, {"project": project, "scope": scope, "sources": []})
    write_json_atomic(run.coverage_plan_path, {
        "document_kind": scope,
        "expected_entities": [],
        "required_axes_by_entity": {},
        "min_facts_per_entity": 1,
        "output_contract": {
            "required_sections": [],
            "required_entity_labels": [],
            "min_chars_warning": 0,
        },
    })
    return {"run": run_id, "state": "INIT", "advanced_to": None, "ok": True, "errors": [],
            "next": "write evidence-manifest.json and coverage-plan.json, then `research verify`"}


# ------------------------------------------------------------ deterministic verification

def verify_manifest(run: Run) -> dict:
    errors: list[str] = []
    manifest = read_json(run.manifest)
    if manifest is None:
        return run.fail("manifest", ["missing or invalid evidence-manifest.json"])
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("evidence-manifest.json must contain a non-empty 'sources' list")
        return run.fail("manifest", errors)
    seen_ids = set()
    for i, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{i}]: not an object")
            continue
        if not source.get("source_id"):
            errors.append(f"sources[{i}]: missing source_id")
        elif source["source_id"] in seen_ids:
            errors.append(f"sources[{i}]: duplicate source_id {source['source_id']}")
        else:
            seen_ids.add(source["source_id"])
        if not source.get("solution_id"):
            errors.append(f"sources[{i}]: missing solution_id")
        available = source.get("available")
        if not isinstance(available, list) or not available:
            errors.append(f"sources[{i}]: 'available' must list e.g. [writeup, repository]")
    if errors:
        return run.fail("manifest", errors)
    return run.advance("manifest", "EVIDENCE_READY",
                       extra={"manifest_sources": len(sources)},
                       warnings=["writeup-only sources must never back code-verified facts"])


def validate_coverage_plan(run: Run, manifest: dict) -> tuple[dict, list[str]]:
    plan = read_json(run.coverage_plan_path)
    errors: list[str] = []
    if plan is None:
        return {}, ["missing or invalid coverage-plan.json"]
    if not isinstance(plan.get("document_kind"), str) or not plan.get("document_kind", "").strip():
        errors.append("coverage-plan.json: document_kind must be a non-empty string")
    entities = plan.get("expected_entities")
    if not isinstance(entities, list) or not entities:
        errors.append("coverage-plan.json: expected_entities must be a non-empty list")
        entities = []
    elif len(set(map(str, entities))) != len(entities):
        errors.append("coverage-plan.json: expected_entities contains duplicates")
    manifest_entities = {str(x.get("solution_id")) for x in manifest.get("sources", []) if isinstance(x, dict) and x.get("solution_id")}
    missing_manifest = sorted(set(map(str, entities)) - manifest_entities)
    if missing_manifest:
        errors.append(f"COVERAGE_ENTITY_NOT_IN_MANIFEST: {missing_manifest}")
    axes = plan.get("required_axes_by_entity", {})
    if not isinstance(axes, dict):
        errors.append("coverage-plan.json: required_axes_by_entity must be an object")
        axes = {}
    else:
        unknown = sorted(set(map(str, axes)) - set(map(str, entities)))
        if unknown:
            errors.append(f"coverage-plan.json: axes specified for unknown entities {unknown}")
        for entity, values in axes.items():
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                errors.append(f"coverage-plan.json: required axes for {entity} must be a list of non-empty strings")
    minimum = plan.get("min_facts_per_entity", 1)
    if not isinstance(minimum, int) or minimum < 1:
        errors.append("coverage-plan.json: min_facts_per_entity must be an integer >= 1")
    contract = plan.get("output_contract", {})
    if not isinstance(contract, dict):
        errors.append("coverage-plan.json: output_contract must be an object")
    else:
        for key in ("required_sections", "required_entity_labels"):
            value = contract.get(key, [])
            if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
                errors.append(f"coverage-plan.json: output_contract.{key} must be a list of non-empty strings")
        warning = contract.get("min_chars_warning", 0)
        if not isinstance(warning, int) or warning < 0:
            errors.append("coverage-plan.json: output_contract.min_chars_warning must be an integer >= 0")
    return plan, errors


def fact_coverage_errors(plan: dict, facts: list[dict]) -> list[str]:
    errors: list[str] = []
    entities = [str(x) for x in plan.get("expected_entities", [])]
    minimum = int(plan.get("min_facts_per_entity", 1) or 1)
    axes_by_entity = plan.get("required_axes_by_entity", {}) or {}
    by_entity: dict[str, list[dict]] = {}
    for fact in facts:
        by_entity.setdefault(str(fact.get("solution_id")), []).append(fact)
    for entity in entities:
        count = len(by_entity.get(entity, []))
        if count < minimum:
            errors.append(f"KNOWLEDGE_COVERAGE_FAIL: {entity} has {count} facts, requires >= {minimum}")
        present_axes = {str(f.get("axis")) for f in by_entity.get(entity, []) if f.get("axis")}
        for axis in axes_by_entity.get(entity, []):
            if axis not in present_axes:
                errors.append(f"KNOWLEDGE_COVERAGE_FAIL: {entity} missing required axis {axis!r}")
    return errors


def verify_evidence_ready(run: Run) -> dict:
    manifest = read_json(run.manifest) or {}
    if not manifest.get("sources"):
        return run.fail("evidence_ready", ["evidence manifest is empty"])
    plan, errors = validate_coverage_plan(run, manifest)
    if errors:
        return run.fail("coverage_plan", errors)
    return run.advance("evidence_ready", "FACTS_READY", extra={"coverage_plan_sha256": json_sha256_obj(plan)})


def verify_facts(run: Run) -> dict:
    errors: list[str] = []
    manifest = read_json(run.manifest) or {}
    source_index = {s.get("source_id"): s for s in manifest.get("sources", []) if isinstance(s, dict)}
    facts, parse_errors = read_jsonl(run.facts_path)
    errors.extend(parse_errors)
    if not facts:
        errors.append("facts.jsonl contains no facts")
        return run.fail("facts", errors)
    plan, coverage_plan_errors = validate_coverage_plan(run, manifest)
    errors.extend(coverage_plan_errors)
    if plan:
        if run.data().get("coverage_plan_sha256") and json_sha256_obj(plan) != run.data().get("coverage_plan_sha256"):
            errors.append("COVERAGE_PLAN_STALE: coverage-plan.json changed after evidence-ready verification")
        errors.extend(fact_coverage_errors(plan, facts))
    seen_ids = set()
    for fact in facts:
        fid = fact.get("fact_id")
        if not fid:
            errors.append("fact missing fact_id")
            continue
        if fid in seen_ids:
            errors.append(f"{fid}: duplicate fact_id")
        seen_ids.add(fid)
        match = FACT_ID_RE.match(str(fid))
        if not match:
            errors.append(f"{fid}: fact_id must match F-<entity>-<num>")
            continue
        fact_entity = match.group(2)
        solution_id = fact.get("solution_id")
        if not solution_id:
            errors.append(f"{fid}: missing solution_id")
        elif solution_id != fact_entity:
            # FACT_ATTRIBUTION_ERROR: fact id entity and declared solution disagree.
            errors.append(f"{fid}: FACT_ATTRIBUTION_ERROR (fact_id entity {fact_entity} != solution_id {solution_id})")
        source_id = fact.get("source_id")
        source = source_index.get(source_id)
        if not source_id or source is None:
            errors.append(f"{fid}: source_id {source_id!r} not present in evidence-manifest")
        else:
            if source.get("solution_id") != solution_id:
                errors.append(f"{fid}: FACT_ATTRIBUTION_ERROR (source {source_id} belongs to {source.get('solution_id')}, fact claims {solution_id})")
            available = source.get("available", [])
            evidence_type = fact.get("evidence_type")
            if evidence_type == "code_demonstrated" and "repository" not in available:
                errors.append(f"{fid}: evidence_type code_demonstrated but source has no repository (writeup-only)")
        if not fact.get("statement"):
            errors.append(f"{fid}: missing statement")
        if not fact.get("source_anchor") and not fact.get("evidence_ids"):
            errors.append(f"{fid}: missing source_anchor")
        if fact.get("evidence_type") not in EVIDENCE_TYPES:
            errors.append(f"{fid}: evidence_type must be one of {sorted(EVIDENCE_TYPES)}")
    if any(f.get("evidence_ids") for f in facts):
        errors.extend(bind_evidence(run, facts, source_index))
    bindings, binding_errors = (read_jsonl(run.evidence_bindings_path) if any(f.get("evidence_ids") for f in facts) else ([], []))
    errors.extend(binding_errors)
    binding_by_id = {b.get("evidence_id"): b for b in bindings}
    # Semantic verification pass (verifier-written facts.verify.jsonl).
    verdicts, verify_errors = read_jsonl(run.facts_verify)
    errors.extend(verify_errors)
    verdict_index = {v.get("fact_id"): v for v in verdicts}
    for fact in facts:
        fid = fact.get("fact_id")
        verdict = verdict_index.get(fid)
        if verdict is None:
            errors.append(f"{fid}: no semantic verification entry in facts.verify.jsonl")
        elif verdict.get("status") not in VERIFY_STATUSES:
            errors.append(f"{fid}: verify status must be PASS/FAIL/AMBIGUOUS")
        elif fact.get("evidence_ids"):
            expected = hashlib.sha256(str(fact.get("statement", "")).encode()).hexdigest()
            if verdict.get("statement_sha256") != expected:
                errors.append(f"{fid}: SEMANTIC_VERDICT_STALE")
            for eid in fact.get("evidence_ids", []):
                bound = binding_by_id.get(eid)
                supplied = next((x.get("excerpt_sha256") for x in verdict.get("evidence", []) if x.get("evidence_id") == eid), None)
                if not bound or supplied != bound.get("excerpt_sha256"):
                    errors.append(f"{fid}: SEMANTIC_VERDICT_STALE")
    if errors:
        return run.fail("facts", errors)
    failed = [v["fact_id"] for v in verdicts if v.get("status") == "FAIL"]
    ambiguous = [v["fact_id"] for v in verdicts if v.get("status") == "AMBIGUOUS"]
    if failed:
        return run.fail("facts", [f"{fid}: semantic verification FAIL" for fid in failed])
    warnings = [f"{fid}: AMBIGUOUS - may not support strong claims" for fid in ambiguous]
    return run.advance("facts", "FACTS_VERIFIED",
                       extra={"facts_sha256_pending": len(facts), "ambiguous_facts": ambiguous},
                       warnings=warnings)


def freeze_facts(run: Run) -> dict:
    facts, errors = read_jsonl(run.facts_path)
    if errors or not facts:
        return run.fail("freeze", errors or ["facts.jsonl empty"])
    digest = jsonl_sha256(facts)
    return run.advance("freeze", "FACTS_FROZEN", extra={"facts_sha256": digest})


def _claim_entities(facts_by_id: dict[str, dict], fact_ids: list) -> set[str]:
    out = set()
    for fid in fact_ids or []:
        fact = facts_by_id.get(fid)
        if fact:
            out.add(str(fact.get("solution_id")))
    return out

def bind_evidence(run: Run, facts: list[dict], source_index: dict) -> list[str]:
    errors, rows = [], []
    for fact in facts:
        for eid in fact.get("evidence_ids", []):
            anchor = fact.get("source_anchor")
            if not isinstance(anchor, dict) or anchor.get("kind") != "file_lines":
                errors.append(f"{fact.get('fact_id')}: evidence anchor must be file_lines")
                continue
            source_id = fact.get("source_id")
            source = resolve_source(ROOT, source_id, source_index.values())
            if source is None or not source.get("root"):
                errors.append(f"{fact.get('fact_id')}: EVIDENCE_SOURCE_MISMATCH (unknown source {source_id})")
                continue
            if fact.get("evidence_type") == "code_demonstrated" and source.get("kind") != "repository":
                errors.append(f"{fact.get('fact_id')}: CODE_DEMONSTRATED_WRONG_SOURCE_KIND")
                continue
            requested_revision = anchor.get("commit") or anchor.get("revision")
            if requested_revision and source.get("revision") and not str(source.get("revision")).startswith(str(requested_revision)):
                errors.append(f"{fact.get('fact_id')}: EVIDENCE_SOURCE_MISMATCH (revision differs from registry)")
            path = (source["root"] / str(anchor.get("path", ""))) if anchor.get("kind") == "git_file_lines" else (ROOT / str(anchor.get("path", "")))
            try:
                path.resolve().relative_to(source["root"])
            except ValueError:
                errors.append(f"{fact.get('fact_id')}: EVIDENCE_SOURCE_MISMATCH")
                continue
            if anchor.get("kind") == "git_file_lines" and source.get("kind") == "repository" and requested_revision:
                try:
                    content = subprocess.check_output(["git", "-C", str(source["root"]), "show", f"{requested_revision}:{anchor.get('path')}"], text=True)
                    lines = content.splitlines()
                    path = source["root"] / str(anchor.get("path"))
                except (OSError, subprocess.CalledProcessError):
                    errors.append(f"{fact.get('fact_id')}: evidence git path missing")
                    continue
            elif not path.is_file():
                errors.append(f"{fact.get('fact_id')}: evidence file missing")
                continue
            else:
                lines = path.read_text(encoding="utf-8").splitlines()
            start, end = int(anchor.get("start_line", 0)), int(anchor.get("end_line", 0))
            if start < 1 or end < start or end > len(lines):
                errors.append(f"{fact.get('fact_id')}: invalid evidence line range")
                continue
            excerpt = "\n".join(lines[start-1:end])
            rows.append({"evidence_id": eid, "fact_id": fact.get("fact_id"), "solution_id": fact.get("solution_id"),
                         "source_id": fact.get("source_id"), "anchor": anchor, "source_revision": requested_revision or source.get("revision"),
                         "excerpt": excerpt, "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                         "source_file_sha256": hashlib.sha256(("\n".join(lines)).encode()).hexdigest()})
    if not errors:
        write_jsonl(run.evidence_bindings_path, rows)
    return errors


def has_universal_wording(text: str) -> list[str]:
    lowered = text.lower()
    hits = []
    for word in UNIVERSAL_WORDS:
        if word.isascii():
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                hits.append(word)
        elif word in text:
            hits.append(word)
    return hits


def verify_claims(run: Run) -> dict:
    errors: list[str] = []
    data = run.data()
    facts, fact_errors = read_jsonl(run.facts_path)
    errors.extend(fact_errors)
    facts_by_id = {f.get("fact_id"): f for f in facts}
    fact_verdicts, _ = read_jsonl(run.facts_verify)
    fact_status = {v.get("fact_id"): v.get("status") for v in fact_verdicts}
    claims, claim_errors = read_jsonl(run.claims_path)
    errors.extend(claim_errors)
    if not claims:
        errors.append("claims.jsonl contains no claims; write claims from FROZEN facts only")
        return run.fail("claims", errors)
    claim_frozen_sha = jsonl_sha256(facts)
    if claim_frozen_sha != data.get("facts_sha256"):
        errors.append("facts.jsonl changed since FACTS_FROZEN; hash invalidation - re-verify facts")

    seen = set()
    for claim in claims:
        cid = claim.get("claim_id")
        if not cid:
            errors.append("claim missing claim_id")
            continue
        if cid in seen:
            errors.append(f"{cid}: duplicate claim_id")
        seen.add(cid)
        if claim.get("claim_type") not in CLAIM_TYPES:
            errors.append(f"{cid}: claim_type must be one of {sorted(CLAIM_TYPES)}")
        if not claim.get("statement"):
            errors.append(f"{cid}: missing statement")
        support = claim.get("support_fact_ids")
        if not isinstance(support, list):
            errors.append(f"{cid}: support_fact_ids must be a list")
            support = []
        if claim.get("claim_type") != "open_question" and not support:
            errors.append(f"{cid}: {claim.get('claim_type')} claim requires support_fact_ids")
        for fid in support:
            if fid not in facts_by_id:
                errors.append(f"{cid}: support fact {fid} does not exist")
            elif fact_status.get(fid) != "PASS":
                errors.append(f"{cid}: support fact {fid} is {fact_status.get(fid)}, not PASS (CLAIM_SUPPORT_FAIL)")
        if "counter_fact_ids" not in claim:
            errors.append(f"{cid}: counter_fact_ids is a required field (run the Strongest Counterexample Search; use [] if truly none)")
        for fid in claim.get("counter_fact_ids", []):
            if fid not in facts_by_id:
                errors.append(f"{cid}: counter fact {fid} does not exist")
        if "eligible_entities" not in claim or not claim.get("eligible_entities"):
            errors.append(f"{cid}: eligible_entities must be a non-empty list")
        for value in claim.values():
            if isinstance(value, str) and MACHINE_PATH_RE.search(value):
                errors.append(f"{cid}: CLAIM_RAW_SOURCE_REF - claims reference fact_ids only, never raw evidence paths")
                break
        covered = _claim_entities(facts_by_id, support)
        eligible = {str(x) for x in claim.get("eligible_entities", [])}
        mode = claim.get("coverage_mode")
        if mode is not None and mode not in {"none", "all", "exact_count"}:
            errors.append(f"{cid}: invalid coverage_mode")
        if mode == "all" and covered != eligible:
            errors.append(f"{cid}: UNIVERSAL_QUANTIFIER_FAIL (support entities {sorted(covered)} != eligible {sorted(eligible)})")
        if mode is None and has_universal_wording(str(claim.get("statement", ""))) and claim.get("claim_type") in STRONG_TYPES and covered != eligible:
            errors.append(f"{cid}: UNIVERSAL_QUANTIFIER_FAIL (support entities {sorted(covered)} != eligible {sorted(eligible)})")
        if mode is not None and mode != "all" and has_universal_wording(str(claim.get("statement", ""))):
            errors.append(f"{cid}: UNIVERSAL_QUANTIFIER_FAIL (coverage_mode is not all)")
        # Decorative counterexample: a principle/convergence/mechanism claim that
        # lists counter facts but no boundary has not absorbed the counterexample.
        if claim.get("claim_type") in COUNTEREXAMPLE_TYPES and claim.get("counter_fact_ids") and not claim.get("boundary"):
            errors.append(f"{cid}: COUNTEREXAMPLE_DECORATIVE - counter facts exist but boundary is empty; counterexample must change wording, boundary, or strength")

    # Semantic verification pass + contradiction entries.
    verdicts, verify_errors = read_jsonl(run.claims_verify)
    errors.extend(verify_errors)
    verdict_index = {v.get("claim_id"): v for v in verdicts if v.get("kind") != "contradiction"}
    for claim in claims:
        cid = claim.get("claim_id")
        verdict = verdict_index.get(cid)
        if verdict is None:
            errors.append(f"{cid}: no semantic verification entry in claims.verify.jsonl")
        elif verdict.get("status") not in VERIFY_STATUSES:
            errors.append(f"{cid}: verify status must be PASS/FAIL/AMBIGUOUS")
        elif verdict.get("status") == "FAIL":
            errors.append(f"{cid}: CLAIM_VERIFY_FAIL ({verdict.get('reason')})")
    for entry in verdicts:
        if entry.get("kind") == "contradiction" and entry.get("status") == "FAIL":
            errors.append(f"CLAIM_CONTRADICTION ({entry.get('claims')}); rewrite, downgrade, or split one claim and record resolution")
    # Derived support counts (single source of truth for counts in Markdown).
    counts = {}
    for claim in claims:
        covered = _claim_entities(facts_by_id, claim.get("support_fact_ids", []))
        eligible = {str(x) for x in claim.get("eligible_entities", [])}
        counts[claim.get("claim_id")] = {"support_count": len(covered), "support_entities": sorted(covered),
                                          "eligible_count": len(eligible), "coverage_ratio": (len(covered) / len(eligible) if eligible else 0)}
    if errors:
        return run.fail("claims", errors)
    return run.advance("claims", "CLAIMS_VERIFIED", extra={"claim_counts": counts})


def current_artifact_hashes(run: Run) -> dict[str, str]:
    facts, _ = read_jsonl(run.facts_path)
    claims, _ = read_jsonl(run.claims_path)
    mechanisms, _ = read_jsonl(run.mechanisms_path)
    coverage = read_json(run.coverage_plan_path) or {}
    return {
        "coverage_plan_sha256": json_sha256_obj(coverage),
        "facts_sha256": jsonl_sha256(facts),
        "claims_sha256": jsonl_sha256(claims),
        "mechanisms_sha256": jsonl_sha256(mechanisms),
    }


def invalidate_stale(run: Run) -> list[str]:
    """Revoke downstream authority when frozen artifacts or verified draft drift."""
    data = run.data()
    state = data.get("state", "INIT")
    if state in {"INIT", "EVIDENCE_READY", "FACTS_READY", "FACTS_VERIFIED"}:
        return []
    current = current_artifact_hashes(run)
    reasons: list[str] = []
    if data.get("coverage_plan_sha256") and current["coverage_plan_sha256"] != data.get("coverage_plan_sha256"):
        reasons.append("COVERAGE_PLAN_STALE")
    if data.get("facts_sha256") and current["facts_sha256"] != data.get("facts_sha256"):
        reasons.append("FACT_MATRIX_STALE")
    if data.get("claims_sha256") and current["claims_sha256"] != data.get("claims_sha256"):
        reasons.append("CLAIM_MATRIX_STALE")
    if data.get("mechanisms_sha256") and current["mechanisms_sha256"] != data.get("mechanisms_sha256"):
        reasons.append("MECHANISM_MAP_STALE")
    if data.get("draft_sha256") and run.draft_path.is_file():
        digest = hashlib.sha256(run.draft_path.read_bytes()).hexdigest()
        if digest != data.get("draft_sha256"):
            reasons.append("DRAFT_STALE")
    if not reasons:
        return []
    run.revoke_gate(", ".join(reasons))
    return reasons


def verify_mechanisms(run: Run) -> dict:
    errors: list[str] = []
    data = run.data()
    hashes = current_artifact_hashes(run)
    if data.get("coverage_plan_sha256") and hashes["coverage_plan_sha256"] != data.get("coverage_plan_sha256"):
        errors.append("COVERAGE_PLAN_STALE: coverage plan changed after evidence verification")
    if data.get("facts_sha256") and hashes["facts_sha256"] != data.get("facts_sha256"):
        errors.append("FACT_MATRIX_STALE: facts changed after freeze")
    if data.get("claims_sha256") and hashes["claims_sha256"] != data.get("claims_sha256"):
        errors.append("CLAIM_MATRIX_STALE: claims changed after verification")
    mechanisms, mech_errors = read_jsonl(run.mechanisms_path)
    errors.extend(mech_errors)
    claims, _ = read_jsonl(run.claims_path)
    claim_ids = {c.get("claim_id") for c in claims}
    claim_verdicts, _ = read_jsonl(run.claims_verify)
    claim_status = {v.get("claim_id"): v.get("status") for v in claim_verdicts if v.get("kind") != "contradiction"}
    if not mechanisms:
        errors.append("mechanisms.jsonl contains no mechanisms")
        return run.fail("mechanisms", errors)
    seen = set()
    by_intervention: dict[str, set[str]] = {}
    for mech in mechanisms:
        mid = mech.get("mechanism_id")
        if not mid:
            errors.append("mechanism missing mechanism_id")
            continue
        if mid in seen:
            errors.append(f"{mid}: duplicate mechanism_id")
        seen.add(mid)
        for field in MECHANISM_FIELDS:
            if field not in mech:
                errors.append(f"{mid}: missing required field {field}")
        for support_id in mech.get("support_claim_ids", []):
            if support_id not in claim_ids:
                errors.append(f"{mid}: support claim {support_id} does not exist")
            elif claim_status.get(support_id) != "PASS":
                errors.append(f"{mid}: support claim {support_id} is not verified PASS")
        if not mech.get("boundary"):
            errors.append(f"{mid}: missing boundary")
        changed = str(mech.get("changed_variable", "")).lower()
        intervention = str(mech.get("intervention", ""))
        key = canonical_line({"intervention": intervention, "changed_variable": changed})
        by_intervention.setdefault(key, set()).add(str(mid))
    for key, mids in by_intervention.items():
        if len(mids) > 1:
            errors.append(f"MECHANISM_DUPLICATE: {sorted(mids)} share identical intervention+changed_variable")
    verdicts, verify_errors = read_jsonl(run.mechanisms_verify)
    errors.extend(verify_errors)
    verdict_index = {v.get("mechanism_id"): v for v in verdicts if v.get("kind") != "conflation"}
    for mech in mechanisms:
        mid = mech.get("mechanism_id")
        verdict = verdict_index.get(mid)
        if verdict is None:
            errors.append(f"{mid}: no semantic verification entry in mechanisms.verify.jsonl")
        elif verdict.get("status") == "FAIL":
            errors.append(f"{mid}: MECHANISM_VERIFY_FAIL ({verdict.get('reason')})")
    for entry in verdicts:
        if entry.get("kind") == "conflation" and entry.get("status") == "FAIL":
            errors.append(f"MECHANISM_CONFLATION ({entry.get('mechanisms')}); same name does not imply same changed_variable")
    if errors:
        return run.fail("mechanisms", errors)
    return run.advance("mechanisms", "MECHANISMS_VERIFIED", extra={"claims_sha256": hashes["claims_sha256"]})


def open_gate(run: Run) -> dict:
    errors: list[str] = []
    data = run.data()
    facts, _ = read_jsonl(run.facts_path)
    claims, _ = read_jsonl(run.claims_path)
    mechanisms, _ = read_jsonl(run.mechanisms_path)
    digests = current_artifact_hashes(run)
    for key in ("coverage_plan_sha256", "facts_sha256", "claims_sha256"):
        if data.get(key) and digests[key] != data.get(key):
            errors.append(f"{key} drift before gate")
    verdicts, _ = read_jsonl(run.claims_verify)
    unresolved = [v for v in verdicts if v.get("kind") == "contradiction" and v.get("status") == "FAIL"]
    if unresolved:
        errors.append("unresolved contradictions remain")
    if errors:
        return run.fail("gate", errors)
    gate = {"state": "WRITE_ALLOWED", "write_allowed": True, "opened_at": utc_now(), **digests}
    write_json_atomic(run.gate_path, gate)
    return run.advance("gate", "WRITE_ALLOWED", extra=digests,
                       warnings=["draft.md may now be written from verified artifacts only"])


# ------------------------------------------------------------------ draft / finalize

def trace_refs(text: str) -> list[tuple[set[str], str]]:
    """Return (ref_ids, following_block_text) pairs for each KOS marker."""
    matches = list(KOS_MARKER_RE.finditer(text))
    out = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        refs = {x.strip() for x in match.group(1).split(",") if x.strip()}
        out.append((refs, text[start:end]))
    return out


def verify_draft(run: Run) -> dict:
    errors: list[str] = []
    data = run.data()
    if run.state() == "WRITE_ALLOWED":
        if not run.draft_path.is_file():
            return {"run": run.run_id, "state": "WRITE_ALLOWED", "ok": False, "errors":
                    ["write draft.md first (from verified facts/claims/mechanisms only), then verify-draft"]}
        digest = hashlib.sha256(run.draft_path.read_bytes()).hexdigest()
        write_json_atomic(run.draft_trace_path, {"run_id": run.run_id, "blocks": [{"refs": sorted(refs), "text": block} for refs, block in trace_refs(run.draft_path.read_text(encoding="utf-8"))]})
        return run.advance("draft", "DRAFT_READY", extra={"draft_sha256": digest})
    if run.state() != "DRAFT_READY":
        return run.fail("draft", [f"state {run.state()} does not allow draft verification"])
    if not run.gate_path.is_file() or not (read_json(run.gate_path) or {}).get("write_allowed"):
        return run.fail("draft", ["no WRITE_ALLOWED gate on record; verify through the gate first"])
    gate = read_json(run.gate_path) or {}
    facts, _ = read_jsonl(run.facts_path)
    claims, _ = read_jsonl(run.claims_path)
    mechanisms, _ = read_jsonl(run.mechanisms_path)
    current = {
        "facts_sha256": jsonl_sha256(facts),
        "claims_sha256": jsonl_sha256(claims),
        "mechanisms_sha256": jsonl_sha256(mechanisms),
    }
    for key, value in current.items():
        if gate.get(key) != value:
            errors.append(f"STALE_HASHES: {key} changed after WRITE_ALLOWED; re-run the gate")
    draft = run.draft_path.read_text(encoding="utf-8")
    warnings: list[str] = []
    plan = read_json(run.coverage_plan_path) or {}
    contract = plan.get("output_contract", {}) if isinstance(plan, dict) else {}
    for section in contract.get("required_sections", []) if isinstance(contract, dict) else []:
        if not re.search(rf"(?m)^#{{1,6}}\s+{re.escape(section)}(?:\s|$)", draft, re.IGNORECASE):
            errors.append(f"DOCUMENT_COMPLETENESS_FAIL: missing required section {section!r}")
    for label in contract.get("required_entity_labels", []) if isinstance(contract, dict) else []:
        if label not in draft:
            errors.append(f"DOCUMENT_COMPLETENESS_FAIL: missing expected entity label {label!r}")
    min_chars = int(contract.get("min_chars_warning", 0) or 0) if isinstance(contract, dict) else 0
    visible = re.sub(r"(?s)^---.*?---\s*", "", draft, count=1)
    if min_chars and len(visible.strip()) < min_chars:
        warnings.append(f"SUSPICIOUSLY_THIN_OUTPUT: {len(visible.strip())} chars < warning threshold {min_chars}")
    fact_ids = {f.get("fact_id") for f in facts}
    claim_ids = {c.get("claim_id") for c in claims}
    mech_ids = {m.get("mechanism_id") for m in mechanisms}
    known = fact_ids | claim_ids | mech_ids
    claim_counts = data.get("claim_counts", {})
    support_solutions = {}
    facts_by_id = {f.get("fact_id"): f for f in facts}
    for claim in claims:
        support_solutions[claim.get("claim_id")] = {
            str(facts_by_id.get(fid, {}).get("solution_id"))
            for fid in claim.get("support_fact_ids", []) if fid in facts_by_id}
    traced = trace_refs(draft)
    for refs, block in traced:
        unknown = refs - known
        if unknown:
            errors.append(f"KOS refs not found in verified artifacts: {sorted(unknown)}")
        if not has_universal_wording(block):
            continue
        # Universal wording needs either a full-coverage claim or counts that
        # match the tool-computed support_count (spec §14/§15/§28).
        full_coverage = any(
            c.get("claim_id") in refs and c.get("coverage_mode") == "all"
            and claim_counts.get(c.get("claim_id"), {}).get("support_count") == claim_counts.get(c.get("claim_id"), {}).get("eligible_count")
            for c in claims)
        needed = set()
        for match in COUNT_TOKEN_RE.finditer(block):
            token = match.group(1).lower()
            needed.add(int(token) if token.isdigit() else WORD_NUMBERS[token])
        counts_ok = bool(needed) and all(
            any(claim_counts.get(cid, {}).get("support_count") == n and next((c.get("coverage_mode") == "exact_count" for c in claims if c.get("claim_id") == cid), False) for cid in refs) for n in needed)
        if not (counts_ok if needed else full_coverage):
            errors.append("UNIVERSAL_WORDING_UNVERIFIED: traced block uses universal wording without a full-coverage claim or a matching computed support count")
    if MACHINE_PATH_RE.search(draft):
        errors.append("MACHINE_PATH_LEAK: draft must not contain repo://, sources/, or registry paths")
    write_json_atomic(run.draft_trace_path, {"run_id": run.run_id, "blocks": [{"refs": sorted(refs), "text": block} for refs, block in traced]})
    write_json_atomic(run.draft_verify_path, {"ok": not errors, "errors": errors, "warnings": warnings, "at": utc_now(), "draft_sha256": hashlib.sha256(run.draft_path.read_bytes()).hexdigest()})
    if errors:
        return run.fail("draft", errors)
    return run.advance("draft", "FINAL_VERIFIED", extra={"draft_sha256": hashlib.sha256(run.draft_path.read_bytes()).hexdigest()}, warnings=warnings)


def finalize_run(run: Run, target: str) -> dict:
    history_errors = run.validate_state_history()
    if history_errors:
        return {"run": run.run_id, "ok": False,
                "error": f"ERROR: Final Markdown write blocked by research gate ({'; '.join(history_errors)})."}
    invalidate_stale(run)
    state = run.state()
    if state != "FINAL_VERIFIED":
        return {"run": run.run_id, "ok": False,
                "error": f"ERROR: Final Markdown write blocked by research gate (state={state}, need FINAL_VERIFIED)."}
    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = ROOT / target
    vault_root = (ROOT / "vault").resolve()
    resolved = target_path.resolve()
    root_resolved = ROOT.resolve()  # tolerate /var -> /private/var symlink on macOS
    try:
        output_rel = str(resolved.relative_to(root_resolved))
    except ValueError:
        output_rel = str(resolved)
    if vault_root not in resolved.parents or resolved.suffix != ".md":
        return {"run": run.run_id, "ok": False, "error": f"target must be a markdown file under vault/: {target}"}
    existing = resolved.read_text(encoding="utf-8") if resolved.is_file() else ""
    if re.search(r"^origin:\s*human\s*$", existing, re.MULTILINE):
        return {"run": run.run_id, "ok": False,
                "error": f"target is explicitly human-owned (origin: human); finalize blocked: {target}"}
    draft = run.draft_path.read_text(encoding="utf-8")
    expected_draft = run.data().get("draft_sha256")
    if not expected_draft or hashlib.sha256(run.draft_path.read_bytes()).hexdigest() != expected_draft:
        return {"run": run.run_id, "ok": False, "error": "ERROR: Final Markdown write blocked by research gate (draft hash stale)."}
    final_text = re.sub(r"<!--\s*KOS:[^\n]*?-->\n?", "", draft)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(resolved.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(final_text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, resolved)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    data = run.data()
    manifest_entry = {
        "run_id": run.run_id,
        "output": output_rel,
        "output_sha256": hashlib.sha256(final_text.encode("utf-8")).hexdigest(),
        "coverage_plan_sha256": data.get("coverage_plan_sha256"),
        "facts_sha256": data.get("facts_sha256"),
        "claims_sha256": data.get("claims_sha256"),
        "mechanisms_sha256": data.get("mechanisms_sha256"),
        "finalized_at": utc_now(),
    }
    run.save(state="COMMITTED", finalization=manifest_entry)
    finalizations = read_json(FINALIZATIONS_PATH) or {"entries": []}
    finalizations["entries"] = [e for e in finalizations.get("entries", []) if e.get("run_id") != run.run_id]
    finalizations["entries"].append(manifest_entry)
    write_json_atomic(FINALIZATIONS_PATH, finalizations)
    write_json_atomic(run.report_path, {"run_id": run.run_id, "result": "COMMITTED", **manifest_entry})
    if run.data().get("scope") == "solution-space":
        claims, _ = read_jsonl(run.claims_path)
        durable = [c for c in claims if c.get("durable") is True]
        if durable:
            claim_digest = hashlib.sha256("\n".join(canonical_line(c) for c in durable).encode()).hexdigest()
            ledger = resolved.parent / "claims.yaml"
            lines = ["schema_version: 1", f"project: {run.data().get('project')}", f"generated_from_run: {run.run_id}", f"facts_sha256: {data.get('facts_sha256')}", f"claims_source_sha256: {jsonl_sha256(claims)}", f"durable_claims_sha256: {claim_digest}", f"generated_at: {utc_now()}", "claims:"]
            lines.extend("  - " + json.dumps(c, ensure_ascii=False) for c in durable)
            ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"run": run.run_id, "ok": True, "state": "COMMITTED", "output": manifest_entry["output"]}


# ------------------------------------------------------------------ status / maintain

def status_run(run: Run) -> dict:
    invalidate_stale(run)
    data = run.data()
    files = {
        "evidence-manifest.json": run.manifest.is_file(), "coverage-plan.json": run.coverage_plan_path.is_file(), "facts.jsonl": run.facts_path.is_file(),
        "facts.verify.jsonl": run.facts_verify.is_file(), "claims.jsonl": run.claims_path.is_file(),
        "claims.verify.jsonl": run.claims_verify.is_file(), "mechanisms.jsonl": run.mechanisms_path.is_file(),
        "mechanisms.verify.jsonl": run.mechanisms_verify.is_file(), "gate.json": run.gate_path.is_file(),
        "draft.md": run.draft_path.is_file(), "draft-trace.json": run.draft_trace_path.is_file(), "draft.verify.json": run.draft_verify_path.is_file(),
    }
    gate = read_json(run.gate_path) or {}
    return {"run": run.run_id, "state": data.get("state", "INIT"), "project": data.get("project"),
            "scope": data.get("scope"), "files": files, "write_allowed": gate.get("write_allowed", False),
            "last_verify": data.get("last_verify")}


def next_step(state: str) -> str:
    return {
        "INIT": "write evidence-manifest.json and coverage-plan.json, then `research verify`",
        "EVIDENCE_READY": "confirm coverage plan, then `research verify`",
        "FACTS_READY": "extract dense facts.jsonl to satisfy the coverage plan + facts.verify.jsonl, then `research verify`",
        "FACTS_VERIFIED": "`research verify` freezes facts (SHA256)",
        "FACTS_FROZEN": "write claims.jsonl (fact_ids only) + claims.verify.jsonl, then `research verify`",
        "CLAIMS_VERIFIED": "write mechanisms.jsonl + mechanisms.verify.jsonl, then `research verify`",
        "MECHANISMS_VERIFIED": "`research verify` runs the final gate check and opens WRITE_ALLOWED",
        "WRITE_ALLOWED": "write draft.md from verified artifacts only, then `research verify-draft`",
        "DRAFT_READY": "`research verify-draft` runs final draft verification",
        "FINAL_VERIFIED": "`research finalize <run> <target-note>` writes final Markdown",
        "COMMITTED": "run committed",
    }.get(state, "unknown state")


def run_verify(run_id: str) -> dict:
    run = Run(run_id)
    if not run.exists():
        return {"run": run_id, "ok": False, "errors": ["run not found; use `research init`"]}
    history_errors = run.validate_state_history()
    if history_errors:
        return {"run": run_id, "state": run.state(), "ok": False, "errors": history_errors}
    invalidate_stale(run)
    state = run.state()
    dispatch = {
        "INIT": verify_manifest, "EVIDENCE_READY": verify_evidence_ready, "FACTS_READY": verify_facts, "FACTS_VERIFIED": freeze_facts,
        "FACTS_FROZEN": verify_claims,
        "CLAIMS_VERIFIED": verify_mechanisms, "MECHANISMS_VERIFIED": open_gate,
    }
    handler = dispatch.get(state)
    if handler is None:
        return {"run": run_id, "state": state, "ok": False,
                "errors": [f"no automated verification from state {state}; next: {next_step(state)}"]}
    result = handler(run)
    result["next"] = next_step(result.get("state", state))
    return result


def research_report() -> dict:
    """Report-only drift checks over all runs and finalizations (used by maintain)."""
    issues: list[dict] = []
    late_states = {"CLAIMS_VERIFIED", "MECHANISMS_VERIFIED", "WRITE_ALLOWED",
                   "DRAFT_READY", "FINAL_VERIFIED", "COMMITTED"}
    if RUNS_DIR.is_dir():
        for run_dir in sorted(RUNS_DIR.iterdir()):
            if not run_dir.is_dir():
                continue
            run = Run(run_dir.name)
            if not run.exists():
                continue
            data = run.data()
            state = data.get("state", "INIT")
            def drifted(artifact: Path, key: str, code: str):
                if not artifact.is_file() or not data.get(key):
                    return
                records, _ = read_jsonl(artifact)
                if jsonl_sha256(records) != data.get(key):
                    issues.append({"kind": code, "run": run.run_id, "detail": f"{artifact.name} changed after freeze"})
            if state in {"FACTS_FROZEN"} | late_states:
                coverage = read_json(run.coverage_plan_path) or {}
                if data.get("coverage_plan_sha256") and json_sha256_obj(coverage) != data.get("coverage_plan_sha256"):
                    issues.append({"kind": "COVERAGE_PLAN_STALE", "run": run.run_id, "detail": "coverage-plan.json changed after verification"})
                drifted(run.facts_path, "facts_sha256", "FACT_MATRIX_STALE")
            if state in late_states:
                drifted(run.claims_path, "claims_sha256", "CLAIM_MATRIX_STALE")
            if state in late_states - {"CLAIMS_VERIFIED"}:
                drifted(run.mechanisms_path, "mechanisms_sha256", "MECHANISM_MAP_STALE")
            if state in late_states:
                # CLAIM_SUPPORT_DRIFT: a claim's support set no longer resolves in facts.jsonl.
                facts, _ = read_jsonl(run.facts_path)
                claims, _ = read_jsonl(run.claims_path)
                fact_ids = {f.get("fact_id") for f in facts}
                for claim in claims:
                    missing = [fid for fid in claim.get("support_fact_ids", []) if fid not in fact_ids]
                    if missing:
                        issues.append({"kind": "CLAIM_SUPPORT_DRIFT", "run": run.run_id,
                                       "claim": claim.get("claim_id"),
                                       "detail": f"support facts no longer present: {', '.join(sorted(missing))}"})
    if FINALIZATIONS_PATH.is_file():
        finalizations = read_json(FINALIZATIONS_PATH) or {}
        entries = finalizations.get("entries", [])
        active = {}
        for entry in entries:
            output = entry.get("output")
            prior = active.get(output)
            if prior is None or str(entry.get("finalized_at", "")) >= str(prior.get("finalized_at", "")):
                active[output] = entry
        for entry in entries:
            if active.get(entry.get("output")) is not entry:
                continue  # legitimate historical finalization superseded by a later run
            output = ROOT / entry.get("output", "")
            if not output.is_file():
                issues.append({"kind": "FINALIZATION_OUTPUT_MISSING", "run": entry.get("run_id"), "output": entry.get("output")})
                continue
            current = hashlib.sha256(output.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if current != entry.get("output_sha256"):
                issues.append({"kind": "UNVERIFIED_GENERATED_UPDATE", "run": entry.get("run_id"),
                               "output": entry.get("output"),
                               "detail": "finalized Markdown changed outside the research gate (FINALIZATION_HASH_DRIFT)"})
    return {"issues": issues, "issue_count": len(issues)}


# ------------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="knowledgeos research")
    sub = parser.add_subparsers(dest="research_command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("run_id")
    p_init.add_argument("--project", required=True)
    p_init.add_argument("--scope", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("run_id")
    sub.add_parser("verify").add_argument("run_id")
    p_draft = sub.add_parser("verify-draft")
    p_draft.add_argument("run_id")
    p_final = sub.add_parser("finalize")
    p_final.add_argument("run_id")
    p_final.add_argument("target")
    args = parser.parse_args(argv)
    if args.research_command == "init":
        result = init_run(args.run_id, args.project, args.scope)
    elif args.research_command == "status":
        result = status_run(Run(args.run_id)) if Run(args.run_id).exists() else {"ok": False, "errors": ["run not found"]}
    elif args.research_command == "verify":
        result = run_verify(args.run_id)
    elif args.research_command == "verify-draft":
        result = verify_draft(Run(args.run_id)) if Run(args.run_id).exists() else {"ok": False, "errors": ["run not found"]}
    else:
        result = finalize_run(Run(args.run_id), args.target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
