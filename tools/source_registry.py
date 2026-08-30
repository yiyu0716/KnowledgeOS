"""Small dependency-free resolver for stable KnowledgeOS source IDs."""
from __future__ import annotations

from pathlib import Path
import re

def _scalar(value: str):
    value = value.strip().strip('"\'')
    return value

def _candidates(root: Path) -> list[dict]:
    candidates = []
    for path in sorted((root / "registry").glob("*.yaml")):
        section = None; current = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.rstrip()
            if line and not line.startswith(" ") and line.endswith(":"):
                section = line[:-1]
            m = re.match(r"^\s*-\s+(?:id|source_id):\s*(.+)$", line)
            if m:
                if current: candidates.append(current)
                current = {"id": _scalar(m.group(1)), "kind": section}; continue
            if re.match(r"^\s*-\s+rank:\s*", line):
                if current: candidates.append(current)
                current = {"kind": section}; continue
            if current:
                m = re.match(r"^\s+(id|source_id|kind|local_path|path|remote|branch|head|revision|code_local_path|code_head):\s*(.+)$", line)
                if m: current[m.group(1)] = _scalar(m.group(2))
        if current: candidates.append(current)
    return candidates

def list_sources(root: Path) -> list[dict]:
    return _candidates(root)

def resolve_source(root: Path, source_id: str, manifest_sources=None) -> dict | None:
    """Resolve a stable source ID to its permitted local root and metadata.

    The registry format is intentionally simple YAML; this parser only reads the
    scalar fields used by source ownership and drift checks.
    """
    candidates = _candidates(root)
    found = next((x for x in candidates if x.get("id") == source_id), None)
    if not found and manifest_sources:
        found = next((dict(x, id=x.get("source_id")) for x in manifest_sources if x.get("source_id") == source_id), None)
    if not found:
        return None
    raw_kind = str(found.get("kind", ""))
    if raw_kind in {"repositories", "repository"} or found.get("remote"):
        kind = "repository"
    elif raw_kind in {"writeups", "writeup"}:
        kind = "writeup"
    else:
        kind = found.get("kind", "source")
    local = found.get("local_path") or found.get("path")
    if not local and found.get("code_local_path"):
        local = found["code_local_path"]
    return {"id": source_id, "kind": kind, "path": local, "root": (root / local).resolve() if local else None,
            "remote": found.get("remote"), "revision": found.get("revision") or found.get("head") or found.get("code_head"),
            "metadata": found}
