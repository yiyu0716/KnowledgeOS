"""Durable accepted evidence and conservative Markdown write protection.

Only indexes are disposable. Accepted research bundles under sources/research/
are private durable evidence. Checksums detect drift; they do not establish the
semantic truth of a model-written verdict. Locks coordinate KnowledgeOS writers;
external editors do not participate, so the target is rechecked before replace.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from markdown_model import frontmatter, FrontmatterError

ARTIFACTS = (
    "run.json", "state-history.jsonl", "evidence-manifest.json", "coverage-plan.json",
    "evidence-bindings.jsonl", "facts.jsonl", "facts.verify.jsonl", "claims.jsonl",
    "claims.verify.jsonl", "mechanisms.jsonl", "mechanisms.verify.jsonl", "gate.json",
    "draft.md", "draft-trace.json", "draft.verify.json", "target-binding.json",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_digest(data: dict) -> str:
    return digest(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value) or ".." in value:
        raise ValueError("invalid run or managed-region identifier")
    return value


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError("expected JSON object")
    return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".kos-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data); handle.flush(); os.fsync(handle.fileno())
        if path.exists(): os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def atomic_json(path: Path, value: dict) -> None:
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def private_root(root: Path, relative: str) -> Path:
    """Reject symlink routing, including links that happen to stay inside root."""
    root = root.resolve()
    target = root / relative
    target.resolve().relative_to(root)
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink(): raise ValueError("symlink paths are not allowed for managed writes")
    return target


def target_path(root: Path, target: str) -> Path:
    root = root.resolve()
    raw = Path(target)
    absolute = raw if raw.is_absolute() else root / raw
    rel = absolute.relative_to(root)
    if ".." in rel.parts or not rel.parts or rel.parts[0] != "vault" or absolute.suffix != ".md":
        raise ValueError("target must be a Markdown file under vault/")
    return private_root(root, rel.as_posix())


def region_span(text: str, region: str) -> tuple[int, int]:
    safe_id(region)
    start = f"<!-- KOS:managed:{region}:start -->"
    end = f"<!-- KOS:managed:{region}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError("managed region must have exactly one start and one end marker")
    a, b = text.index(start) + len(start), text.index(end)
    if b < a or "KOS:managed:" in text[a:b]:
        raise ValueError("nested or reversed managed regions are not supported")
    # A selected region cannot itself be nested inside a different region.
    before = re.findall(r"<!-- KOS:managed:([A-Za-z0-9_.-]+):(start|end) -->", text[:a - len(start)])
    opened = []
    for name, kind in before:
        if kind == "start": opened.append(name)
        elif opened and opened[-1] == name: opened.pop()
        else: raise ValueError("malformed managed-region structure")
    if opened: raise ValueError("nested managed region is not supported")
    return a, b


def ownership(text: str) -> str:
    props, _, _ = frontmatter(text)
    origin = props.get("origin", "human")
    if not isinstance(origin, str) or origin not in {"human", "mixed", "codex"}:
        raise ValueError("missing, ambiguous or unknown ownership; refusing overwrite")
    return origin


def bind_target(root: Path, run, target: str, region: str | None = None) -> dict:
    """Bind before extraction/drafting. Never silently rebase an old plan."""
    if run.state() not in {"INIT", "EVIDENCE_READY", "FACTS_READY"}:
        raise ValueError("bind the target before facts are verified; start a new run for a changed plan")
    path = target_path(root, target)
    binding_path = run.dir / "target-binding.json"
    if binding_path.exists() or run.data().get("target_binding_sha256"):
        raise ValueError("target already bound; bindings are immutable")
    data = path.read_bytes() if path.is_file() else None
    text = data.decode("utf-8") if data is not None else ""
    owner = ownership(text) if data is not None else "new"
    if owner == "human": raise ValueError("human-owned or missing-origin target is protected")
    if owner == "mixed" and not region: raise ValueError("mixed targets require an explicitly named managed region")
    if region:
        if data is None: raise ValueError("managed region must already exist in the target")
        region_span(text, region)
    binding = {"schema_version": 1, "target": path.relative_to(root.resolve()).as_posix(),
               "base_sha256": digest(data) if data is not None else None,
               "owner": owner, "region": region,
               "bound_at": datetime.now(timezone.utc).isoformat(timespec="microseconds")}
    atomic_json(binding_path, binding)
    run.save(target_binding_sha256=object_digest(binding))
    return binding


def check_binding(root: Path, run, target: str) -> tuple[Path, dict, str]:
    binding_file = run.dir / "target-binding.json"
    if not binding_file.is_file(): raise ValueError("TARGET_NOT_BOUND: use research bind-target before planning")
    binding = load_json(binding_file)
    if object_digest(binding) != run.data().get("target_binding_sha256"):
        raise ValueError("TARGET_BINDING_DRIFT")
    path = target_path(root, target)
    if path.relative_to(root.resolve()).as_posix() != binding["target"]:
        raise ValueError("TARGET_MISMATCH")
    current = path.read_bytes() if path.is_file() else None
    if (digest(current) if current is not None else None) != binding["base_sha256"]:
        raise ValueError("STALE_TARGET: target changed since planning; re-read and start a new run")
    text = current.decode("utf-8") if current is not None else ""
    if current is not None and ownership(text) != binding["owner"]:
        raise ValueError("OWNERSHIP_CHANGED")
    if binding.get("region"): region_span(text, binding["region"])
    return path, binding, text


def final_text(binding: dict, existing: str, draft: str) -> str:
    # Strip only proof references, never human text or managed-region markers.
    clean = re.sub(r"<!--\s*KOS:refs=[^\n]*?-->\r?\n?", "", draft)
    if binding.get("region"):
        if clean.startswith("---") or "KOS:managed:" in clean:
            raise ValueError("a managed-region draft cannot contain frontmatter or region markers")
        a, b = region_span(existing, binding["region"])
        return existing[:a] + "\n" + clean.strip("\r\n") + "\n" + existing[b:]
    owner = ownership(clean)
    if owner != "codex":
        raise ValueError("generated whole-note drafts must declare origin: codex")
    return clean


@contextmanager
def target_lock(root: Path, relative: str):
    locks = private_root(root, ".knowledgeos/locks")
    locks.mkdir(parents=True, exist_ok=True)
    lock = locks / (digest(relative.encode()) + ".lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise ValueError("TARGET_LOCKED: another writer or interrupted operation requires review") from exc
    try:
        with os.fdopen(fd, "w") as handle: handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)


def archive_directory(root: Path, run_id: str) -> Path:
    return private_root(root, f"sources/research/{safe_id(run_id)}")


def prepare_archive(root: Path, run, final: str, entry: dict) -> Path:
    destination = archive_directory(root, run.run_id)
    if destination.exists(): raise ValueError("accepted run ID already exists; archives are never overwritten")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=".pending-", dir=destination.parent))
    try:
        files = {}
        for name in ARTIFACTS:
            source = run.dir / name
            if source.is_symlink(): raise ValueError("research artifacts may not be symlinks")
            if source.is_file():
                content = source.read_bytes()
                atomic_write(staged / name, content); files[name] = digest(content)
        final_bytes = final.encode("utf-8")
        atomic_write(staged / "final-output.md", final_bytes)
        files["final-output.md"] = digest(final_bytes)
        facts = [json.loads(line) for line in (staged / "facts.jsonl").read_text().splitlines() if line.strip()]
        bindings_present = (staged / "evidence-bindings.jsonl").is_file()
        bound_count = sum(bool(fact.get("evidence_ids")) for fact in facts) if bindings_present else 0
        grade = "bound" if facts and bound_count == len(facts) else "mixed" if bound_count else "legacy-anchor-only"
        atomic_json(staged / "acceptance.json", {"schema_version": 1, "state": "PREPARED",
                    **entry, "files": files, "provenance_grade": grade})
        return staged
    except Exception:
        import shutil
        shutil.rmtree(staged)
        raise


def commit_archive(root: Path, run, staged: Path) -> dict:
    """Seal the post-commit journal, then atomically publish the evidence bundle."""
    record = load_json(staged / "acceptance.json")
    for name in ("run.json", "state-history.jsonl"):
        source = run.dir / name
        if source.is_file():
            data = source.read_bytes(); atomic_write(staged / name, data)
            record["files"][name] = digest(data)
    record["state"] = "COMMITTED"
    atomic_json(staged / "acceptance.json", record)
    destination = archive_directory(root, run.run_id)
    if destination.exists(): raise ValueError("archive exists; refusing replacement")
    os.rename(staged, destination)
    return record


def verified_archives(root: Path) -> tuple[list[dict], list[dict]]:
    records, issues = [], []
    try:
        directory = private_root(root, "sources/research")
    except ValueError:
        return [], [{"kind": "PROVENANCE_SYMLINK"}]
    for bundle in sorted(directory.iterdir()) if directory.is_dir() else []:
        if not bundle.is_dir(): continue
        if bundle.name.startswith(".pending-"):
            issues.append({"kind": "PROVENANCE_PENDING", "bundle": bundle.name}); continue
        try:
            safe_id(bundle.name)
            if bundle.is_symlink(): raise ValueError("symlink archive")
            record = load_json(bundle / "acceptance.json")
            if record.get("state") != "COMMITTED" or record.get("run_id") != bundle.name:
                raise ValueError("uncommitted or misidentified archive")
            files = record.get("files")
            if not isinstance(files, dict) or not files or "final-output.md" not in files:
                raise ValueError("missing archive manifest")
            if not {"run.json", "facts.jsonl", "claims.jsonl", "mechanisms.jsonl", "draft-trace.json", "gate.json"} <= set(files):
                raise ValueError("incomplete accepted evidence bundle")
            for name, expected in files.items():
                if Path(name).name != name or name in {".", "..", "acceptance.json"}:
                    raise ValueError("invalid archive member")
                path = bundle / name
                if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                    raise ValueError(f"artifact checksum mismatch: {name}")
            target_path(root, record["output"])
            if files["final-output.md"] != record.get("output_sha256"):
                raise ValueError("final output checksum mismatch")
            archived_run = load_json(bundle / "run.json")
            if not archived_run.get("finalization") or archived_run.get("state") != "COMMITTED" or archived_run.get("finalization") != {
                k: record[k] for k in archived_run.get("finalization", {})}:
                raise ValueError("archive acceptance does not match committed run")
            records.append(record)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            issues.append({"kind": "PROVENANCE_ARCHIVE_DRIFT", "bundle": bundle.name, "detail": str(exc)})
    return records, issues


def finalization_entries(root: Path) -> list[dict]:
    records, _ = verified_archives(root)
    by_id = {x["run_id"]: x for x in records}
    path = root / ".knowledgeos/finalizations.json"
    if path.is_file():
        try:
            for record in load_json(path).get("entries", []):
                # Legacy state is usable only while its original run exists.
                rid = safe_id(record.get("run_id", ""))
                if rid not in by_id and (root / ".knowledgeos/runs" / rid / "run.json").is_file():
                    by_id[rid] = record
        except (OSError, ValueError, TypeError):
            pass
    return sorted(by_id.values(), key=lambda x: (str(x.get("finalized_at", "")), x["run_id"]))


def rebuild_finalizations(root: Path) -> dict:
    records, issues = verified_archives(root)
    if issues:
        return {"ok": False, "issues": issues, "detail": "index left unchanged; resolve archive integrity issues first"}
    entries = finalization_entries(root)
    atomic_json(root / ".knowledgeos/finalizations.json", {"schema_version": 1, "entries": entries})
    return {"ok": True, "durable_bundles": len(records), "entries": len(entries), "issues": []}


def archive_legacy(root: Path, run, apply: bool = False) -> dict:
    """No invented recovery: require a valid committed run and reconstructible output."""
    if run.state() != "COMMITTED": raise ValueError("only COMMITTED runs can be archived")
    if run.validate_state_history(): raise ValueError("invalid state history")
    entry = run.data().get("finalization")
    if not isinstance(entry, dict): raise ValueError("legacy run lacks a finalization record")
    draft = run.draft_path.read_bytes()
    if digest(draft) != run.data().get("draft_sha256"):
        raise ValueError("legacy draft drift")
    text = re.sub(r"<!--\s*KOS:[^\n]*?-->\n?", "", draft.decode("utf-8"))
    if digest(text.encode()) != entry.get("output_sha256"):
        raise ValueError("historical output cannot be reconstructed; do not invent evidence")
    for name, key in (("facts.jsonl", "facts_sha256"), ("claims.jsonl", "claims_sha256"), ("mechanisms.jsonl", "mechanisms_sha256")):
        rows = [json.loads(line) for line in (run.dir / name).read_text().splitlines() if line.strip()]
        canonical = "\n".join(json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for x in sorted(rows, key=lambda r: r.get("fact_id") or r.get("claim_id") or r.get("mechanism_id") or ""))
        if digest(canonical.encode()) != run.data().get(key): raise ValueError("legacy research artifacts drifted")
    if not apply:
        return {"ok": True, "dry_run": True, "run_id": run.run_id, "archive": f"sources/research/{run.run_id}", "warning": "legacy anchor-only evidence is preserved, not upgraded to bound verification"}
    staged = prepare_archive(root, run, text, entry)
    commit_archive(root, run, staged)
    return {"ok": True, "dry_run": False, "run_id": run.run_id, "index": rebuild_finalizations(root)}


def archive_audit(root: Path) -> dict:
    records, issues = verified_archives(root)
    active = {}
    for entry in sorted(records, key=lambda x: (x.get("finalized_at", ""), x["run_id"])):
        output, region = entry["output"], entry.get("region")
        if region is None:
            # A whole-note acceptance supersedes prior managed scopes.
            active = {key: value for key, value in active.items() if key[0] != output}
        else:
            # After an explicitly scoped update, the older full-file hash is
            # historical, not a current invariant. Human outside-region edits
            # are not claimed to be newly verified by a region acceptance.
            active.pop((output, None), None)
        active[(output, region)] = entry
    for (output, region), entry in active.items():
        path = target_path(root, output)
        try:
            text = path.read_bytes().decode("utf-8")
            if region:
                a, b = region_span(text, region)
                current = digest(text[a:b].encode())
                expected = entry["region_sha256"]
            else:
                current, expected = digest(text.encode()), entry["output_sha256"]
            if current != expected:
                issues.append({"kind": "FINALIZATION_HASH_DRIFT", "run": entry["run_id"], "output": output, "region": region})
        except (OSError, ValueError, KeyError):
            issues.append({"kind": "FINALIZATION_OUTPUT_MISSING_OR_INVALID", "run": entry["run_id"], "output": output})
    return {"issues": issues, "issue_count": len(issues), "accepted_bundles": len(records)}


def provenance_for(root: Path, outputs: set[str]) -> list[dict]:
    out = []
    records, _ = verified_archives(root)
    for record in sorted(records, key=lambda x: (x.get("finalized_at", ""), x["run_id"]), reverse=True):
        if record.get("output") not in outputs: continue
        bundle = archive_directory(root, record["run_id"])
        if not (bundle / "acceptance.json").is_file(): continue
        bindings = bundle / "evidence-bindings.jsonl"
        out.append({"run_id": record["run_id"], "output": record["output"],
                    "finalized_at": record.get("finalized_at"), "region": record.get("region"),
                    "provenance_grade": record.get("provenance_grade"),
                    "evidence": [json.loads(x) for x in bindings.read_text().splitlines() if x.strip()] if bindings.is_file() else [],
                    "trace": load_json(bundle / "draft-trace.json").get("blocks", [])})
    return out
