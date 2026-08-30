#!/usr/bin/env python3
"""Dependency-light KnowledgeOS projections: search, graph, provenance, lint."""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from source_registry import resolve_source, list_sources
VAULT = ROOT / "vault"
DERIVED = ROOT / ".knowledgeos"
CONFIG = ROOT / "knowledge-config.yaml"
VECTOR_INDEX = DERIVED / "vector-index.npz"
VECTOR_META = DERIVED / "vector-meta.json"
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]")
LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SOURCE_RE = re.compile(r"(?:repo|writeup|paper|experiment)://[^\s)`]+|(?:repo|writeup|paper|experiment):[^\s)`]+")
REPO_REF_RE = re.compile(r"repo://([^@/]+)@([^/]+)(?:/([^#:`]+))?(?:::[^#`]+)?(?:#L.*)?$")


def normalize_wikilink(value: str) -> str:
    s = value.strip().strip('"\'`')
    if s.startswith("[[") and s.endswith("]]" ):
        s = s[2:-2]
    s = s.split("|", 1)[0].split("#", 1)[0]
    return s.strip()


def normalize_source_ref(value: str) -> str:
    return value.strip().strip('"\'`').rstrip("。，；,.;:)]}")


def canonical_id(path: Path) -> str:
    rel = path.relative_to(VAULT).with_suffix("")
    return "/".join(rel.parts)


def note_aliases(notes: list[dict]) -> dict[str, list[str]]:
    aliases: dict[str, list[str]] = defaultdict(list)
    for n in notes:
        for alias in (n["id"], n["path"], Path(n["path"]).name):
            aliases[alias].append(n["id"])
        aliases[Path(n["path"]).stem].append(n["id"])
    return aliases


def resolve_note_link(value: str, aliases: dict[str, list[str]], source_id: str | None = None) -> str | None:
    target = normalize_wikilink(value)
    candidates = aliases.get(target, [])
    if not candidates:
        candidates = aliases.get(Path(target).name, []) or aliases.get(Path(target).stem, [])
    if source_id and len(candidates) > 1:
        folder = source_id.rsplit("/", 1)[0]
        local = [x for x in candidates if x.rsplit("/", 1)[0] == folder]
        if len(local) == 1:
            return local[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def chinese_tokens(text: str) -> list[str]:
    out = []
    for block in re.findall(r"[一-鿿]+", text):
        out.extend(list(block))
        out.extend(block[i:i + 2] for i in range(len(block) - 1))
    return out


def tokens(text: str) -> list[str]:
    return [x.lower() for x in re.findall(r"[A-Za-z0-9_]+", text)] + [x.lower() for x in chinese_tokens(text)]


def markdown_files() -> list[Path]:
    return sorted(VAULT.rglob("*.md"))


def parse_note(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    props: dict[str, object] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 5)
        if end >= 0:
            raw = text[4:end]
            body = text[end + 4 :]
            lines = raw.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                if not line.strip() or line.lstrip().startswith("#") or ":" not in line or line.startswith(" "):
                    i += 1
                    continue
                key, value = line.split(":", 1)
                value = value.strip().strip('"')
                if value.startswith("[") and value.endswith("]"):
                    value = [x.strip().strip('"') for x in value[1:-1].split(",") if x.strip()]
                elif not value:
                    items = []
                    j = i + 1
                    while j < len(lines) and lines[j].lstrip().startswith("-"):
                        items.append(lines[j].lstrip()[1:].strip().strip('"'))
                        j += 1
                    if items:
                        value = items
                        i = j - 1
                props[key.strip()] = value
                i += 1
    links = sorted(set(normalize_wikilink(m.group(1)) for m in LINK_RE.finditer(text) if not (m.start() > 0 and text[m.start() - 1] == "!")))
    inline_refs = sorted(set(normalize_source_ref(x) for x in SOURCE_RE.findall(body)))
    values = props.get("source_refs", [])
    values = values if isinstance(values, list) else [values]
    structured_refs = sorted(set(normalize_source_ref(str(x)) for x in values if x))
    try:
        rel_path = str(path.relative_to(ROOT))
    except ValueError:
        rel_path = str(path.relative_to(VAULT.parent))
    return {"path": rel_path, "id": canonical_id(path), "properties": props,
            "links": links, "source_refs": structured_refs, "inline_source_refs": inline_refs, "body": body}


def build_graph() -> dict:
    notes = [parse_note(p) for p in markdown_files()]
    aliases = note_aliases(notes)
    edges = []
    wanted = []
    reverse_sources: dict[str, list[str]] = defaultdict(list)
    note_to_sources: dict[str, list[str]] = defaultdict(list)
    seen = set()
    for note in notes:
        src = note["id"]
        for target in note["links"]:
            resolved = resolve_note_link(target, aliases, src)
            edge = {"source": src, "target": resolved or normalize_wikilink(target), "kind": "wikilink"}
            if (edge["source"], edge["target"], edge["kind"]) not in seen:
                edges.append(edge); seen.add((edge["source"], edge["target"], edge["kind"]))
            if not resolved:
                wanted.append(edge)
        props = note["properties"]
        for key in ("projects", "derived_from", "parents"):
            vals = props.get(key, [])
            vals = vals if isinstance(vals, list) else [vals]
            for target in vals:
                if target:
                    normalized = normalize_wikilink(str(target))
                    resolved = resolve_note_link(normalized, aliases, src)
                    edge = {"source": src, "target": resolved or normalized, "kind": key}
                    if (edge["source"], edge["target"], key) not in seen:
                        edges.append(edge); seen.add((edge["source"], edge["target"], key))
                    if not resolved:
                        wanted.append(edge)
        for ref in note["source_refs"]:
            reverse_sources[ref].append(src); note_to_sources[src].append(ref)
            edge = {"source": src, "target": ref, "kind": "source_refs"}
            if (src, ref, "source_refs") not in seen:
                edges.append(edge); seen.add((src, ref, "source_refs"))
    incoming = Counter(e["target"] for e in edges)
    outgoing = Counter(e["source"] for e in edges)
    node_ids = {n["id"] for n in notes}
    orphans = [n["id"] for n in notes if not incoming[n["id"]] and not outgoing[n["id"]]]
    return {"nodes": notes, "edges": edges, "wanted_links": wanted, "orphans": orphans,
            "reverse_sources": reverse_sources, "note_to_sources": note_to_sources, "node_ids": sorted(node_ids)}


def project_graph() -> dict:
    graph = build_graph()
    projects = {n["id"]: n for n in graph["nodes"] if n["properties"].get("type") == "project"}
    all_aliases = note_aliases(graph["nodes"])
    aliases = note_aliases(list(projects.values()))
    edges, unresolved, multi = [], [], []
    for node in projects.values():
        vals = node["properties"].get("parents", [])
        vals = vals if isinstance(vals, list) else [vals]
        seen = set()
        for value in vals:
            target = resolve_note_link(str(value), aliases, node["id"])
            if target in seen:
                continue
            seen.add(target)
            if not target:
                other = resolve_note_link(str(value), all_aliases, node["id"])
                unresolved.append({"source": node["id"], "target": other or normalize_wikilink(str(value)), "kind": "non_project_parent" if other else "missing_parent"})
            elif target not in projects:
                unresolved.append({"source": node["id"], "target": target, "kind": "non_project_parent"})
            else:
                edges.append({"parent": target, "child": node["id"]})
        if len(seen) > 1:
            multi.append(node["id"])
    adjacency = defaultdict(list)
    for edge in edges: adjacency[edge["parent"]].append(edge["child"])
    cycles = []
    def visit(node, stack):
        if node in stack:
            cycles.append(stack[stack.index(node):] + [node]); return
        for child in adjacency[node]: visit(child, stack + [node])
    for node in projects: visit(node, [])
    return {"nodes": sorted(projects), "edges": edges, "roots": sorted(n for n in projects if not any(e["child"] == n for e in edges)), "multi_parent": multi, "unresolved_parents": unresolved, "cycles": cycles}


def snippet(text: str, query_terms: list[str], width: int = 180) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    positions = [compact.lower().find(term.lower()) for term in query_terms if compact.lower().find(term.lower()) >= 0]
    start = max(0, min(positions) - 60) if positions else 0
    excerpt = compact[start:start + width]
    return ("..." if start else "") + excerpt + ("..." if start + width < len(compact) else "")


def bm25(query: str, limit: int = 10) -> list[dict]:
    notes = [parse_note(p) for p in markdown_files()]
    q = tokens(query)
    if not q:
        return []
    docs = []
    for n in notes:
        title = Path(n["path"]).stem.replace("-", " ")
        props = " ".join(map(str, n["properties"].values()))
        body = n["body"]
        text = title + " " + props + " " + body
        docs.append((n, title, props, body, Counter(tokens(text)), len(tokens(text)), set(tokens(title))))
    avgdl = sum(x[5] for x in docs) / max(1, len(docs))
    df = Counter(term for _, _, _, _, counts, _, _ in docs for term in counts)
    results = []
    query_phrase = query.strip().lower()
    for n, title, props, body, counts, dl, title_terms in docs:
        score = 0.0
        for term in set(q):
            if term not in counts:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            tf = counts[term]
            score += idf * (tf * 2.2 / (tf + 1.2 * (0.65 + 0.35 * dl / max(1, avgdl))))
            if term in title_terms:
                score += 2.0
            elif term in tokens(props):
                score += 0.5
        full_text = (title + " " + props + " " + body).lower()
        if query_phrase and query_phrase in full_text:
            score += 2.5
        if n["properties"].get("type") == "learning":
            score *= 1.25
        elif n["properties"].get("type") == "project-doc":
            # Project research notes are the canonical answer surface for
            # focused queries; keep the project home as navigation context.
            score *= 1.35
        if score:
            results.append({"path": n["path"], "id": n["id"], "score": round(score, 5),
                            "type": n["properties"].get("type"), "snippet": snippet(body, q),
                            "matched_terms": sorted(set(q) & set(counts))})
    return sorted(results, key=lambda x: (-x["score"], x["path"]))[:limit]

def config_value(key: str, default=None):
    if not CONFIG.is_file(): return default
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(key + ":"):
            return line.split(":", 1)[1].strip().strip('"\'')
    return default


def vector_enabled() -> bool:
    return str(config_value("vector", "false")).lower() in {"1", "true", "yes", "on"}


def semantic_chunks() -> list[dict]:
    chunks = []
    for path in markdown_files():
        note = parse_note(path)
        if note["properties"].get("type") not in {"learning", "project", "project-doc", "paper"}: continue
        lines = note["body"].splitlines(); heading = "Document"; buf = []
        def flush():
            text = "\n".join(buf).strip()
            if text:
                title = Path(note["path"]).stem
                chunks.append({"chunk_id": f"{note['id']}#{heading}", "note_id": note["id"], "note_type": note["properties"].get("type"), "heading": heading, "text": f"Title: {title}\nType: {note['properties'].get('type')}\nHeading: {heading}\n{text}", "content_hash": __import__('hashlib').sha256(text.encode()).hexdigest()})
        for line in lines:
            if line.startswith("## ") or line.startswith("### "):
                flush(); buf.clear(); heading = line.lstrip("# ").strip()
            elif heading != "Evidence Map": buf.append(line)
        flush()
    return chunks


def build_vector_index() -> dict:
    provider = str(config_value("provider", "sentence-transformers"))
    model_name = str(config_value("model", "Qwen/Qwen3-Embedding-0.6B"))
    chunks = semantic_chunks()
    try:
        import numpy as np
        if provider == "ollama":
            endpoint = str(config_value("endpoint", "http://localhost:11434")) + "/api/embed"
            payload = json.dumps({"model": model_name, "input": [x["text"] for x in chunks]}).encode()
            req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as response: result = json.loads(response.read())
            vectors = np.asarray(result["embeddings"], dtype="float32")
        else:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
            kwargs = {"normalize_embeddings": False}
            if "truncate_dim" in model.encode.__code__.co_varnames: kwargs["truncate_dim"] = requested_dim
            vectors = model.encode_document([x["text"] for x in chunks], **kwargs) if hasattr(model, "encode_document") else model.encode([x["text"] for x in chunks], **kwargs)
            vectors = np.asarray(vectors, dtype="float32")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True); vectors = vectors / np.maximum(norms, 1e-12)
        DERIVED.mkdir(exist_ok=True); np.savez_compressed(VECTOR_INDEX, embeddings=vectors)
        VECTOR_META.write_text(json.dumps({"provider": provider, "model": model_name, "dimension": int(vectors.shape[1]), "chunks": chunks}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "built", "provider": provider, "chunks": len(chunks), "dimension": int(vectors.shape[1]), "model": model_name}
    except Exception as exc:
        return {"status": "unavailable", "provider": provider, "reason": str(exc)}


def vector_search(query: str, limit: int = 20) -> tuple[list[dict], str | None]:
    try:
        import numpy as np
        if not VECTOR_INDEX.is_file() or not VECTOR_META.is_file(): return [], "vector index missing; run rebuild"
        meta = json.loads(VECTOR_META.read_text(encoding="utf-8")); provider = meta.get("provider", "sentence-transformers")
        if provider == "ollama":
            endpoint = str(config_value("endpoint", "http://localhost:11434")) + "/api/embed"
            payload = json.dumps({"model": meta["model"], "input": [query]}).encode()
            req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response: vec = np.asarray(json.loads(response.read())["embeddings"][0], dtype="float32")
        else:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(meta["model"]); kwargs = {"normalize_embeddings": False}
            if "truncate_dim" in model.encode.__code__.co_varnames: kwargs["truncate_dim"] = int(meta["dimension"])
            vec = np.asarray((model.encode_query([query], **kwargs) if hasattr(model, "encode_query") else model.encode([query], **kwargs))[0], dtype="float32")
        vec /= max(float(np.linalg.norm(vec)), 1e-12)
        scores = np.load(VECTOR_INDEX)["embeddings"] @ vec; order = np.argsort(-scores)[:limit]
        return [{"id": meta["chunks"][int(i)]["note_id"], "heading": meta["chunks"][int(i)]["heading"], "score": float(scores[int(i)]), "rank": r + 1} for r, i in enumerate(order)], None
    except Exception as exc:
        return [], f"vector search unavailable; using BM25 only ({exc})"


def rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1 / (k + rank) for rank in ranks)


def hybrid_search(query: str, limit: int = 10) -> list[dict]:
    lexical = bm25(query, 20); semantic, warning = vector_search(query, 20)
    if not semantic: return lexical[:limit]
    ranks = {}
    for rank, item in enumerate(lexical, 1): ranks.setdefault(item["id"], {})["bm25"] = rank
    for item in semantic: ranks.setdefault(item["id"], {})["vector"] = item["rank"]
    by_id = {x["id"]: x for x in lexical}
    by_id.update({n["id"]: {"id": n["id"], "path": n["path"], "type": n["properties"].get("type")} for n in build_graph()["nodes"]})
    out = []
    for note_id, r in ranks.items():
        score = rrf_score(list(r.values())); n = by_id.get(note_id, {"id": note_id, "path": note_id, "type": None})
        if n.get("type") == "learning": score *= 1.10
        out.append({"id": note_id, "path": n.get("path", note_id), "type": n.get("type"), "rrf": round(score, 6), "bm25_rank": r.get("bm25"), "vector_rank": r.get("vector")})
    return sorted(out, key=lambda x: (-x["rrf"], x["path"]))[:limit]

def registry_entries() -> list[tuple[str, str]]:
    entries = []
    for registry in sorted((ROOT / "registry").glob("*.yaml")):
        current_path = recorded = None
        for line in registry.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("local_path:"):
                current_path = line.split(":", 1)[1].strip()
            elif line.strip().startswith(("head:", "last_ingested_head:")):
                recorded = line.split(":", 1)[1].strip()
            elif line.startswith("  - rank:") and current_path and recorded:
                entries.append((current_path, recorded)); current_path = recorded = None
        if current_path and recorded:
            entries.append((current_path, recorded))
    return entries
def style_issues(note: dict) -> list[dict]:
    issues = []
    text_path = ROOT / note["path"]
    if not text_path.exists(): text_path = VAULT.parent / note["path"]
    text = text_path.read_text(encoding="utf-8")
    if note["properties"].get("type") in {"project", "project-doc"}:
        marker = "## Evidence Map" if "## Evidence Map" in text else "<summary>Evidence Map</summary>"
        if marker in text and any(line.startswith("## ") for line in text[text.rfind(marker):].splitlines()[1:]): issues.append({"kind": "evidence_map_not_last", "path": note["path"]})
        if "Evidence and limits" in text: issues.append({"kind": "legacy_evidence_section", "path": note["path"]})
        if len(re.findall(r"repo://[^\s)`]+", note["body"])) > 3: issues.append({"kind": "path_heavy_prose", "path": note["path"]})
        if note["source_refs"] and any(str(x).startswith("repo://") for x in note["source_refs"]):
            issues.append({"kind": "PROVENANCE_MIGRATION_WARNING", "path": note["path"]})
    if note["properties"].get("type") == "project":
        required = ["Project Overview", "Task", "Evaluation", "Core Challenges", "Solution Landscape", "Top 3 Principles", "Evidence Map"]
        missing = [x for x in required if f"## {x}" not in text and f"# {x}" not in text and f"<summary>{x}</summary>" not in text]
        if missing: issues.append({"kind": "project_home_incomplete", "path": note["path"], "missing": missing})
    return issues


def trace(query: str) -> dict:
    graph = build_graph()
    target = query.strip()
    matches = [n for n in graph["nodes"] if n["id"] == target or Path(n["path"]).stem == target or n["id"].endswith("/" + target)]
    if not matches:
        return {"query": query, "matches": [], "relations": [], "source_refs": []}
    ids = {n["id"] for n in matches}
    relations = [e for e in graph["edges"] if e["source"] in ids or e["target"] in ids]
    refs = sorted({ref for n in matches for ref in n["source_refs"]})
    return {"query": query, "matches": [n["id"] for n in matches], "relations": relations, "source_refs": refs}


def lint() -> dict:
    graph = build_graph()
    issues = []
    for note in graph["nodes"]:
        issues.extend(style_issues(note))
    for path in markdown_files():
        text = path.read_text(encoding="utf-8")
        if "/Users/" in text or "C:\\Users\\" in text:
            issues.append({"kind": "absolute_path", "path": str(path.relative_to(ROOT))})
        if text.startswith("---\n") and "\n---" not in text[5:]:
            issues.append({"kind": "invalid_frontmatter", "path": str(path.relative_to(ROOT))})
    pgraph = project_graph()
    issues.extend({"kind": "invalid_project_parent", **x} for x in pgraph["unresolved_parents"])
    issues.extend({"kind": "project_cycle", "cycle": x} for x in pgraph["cycles"])
    for node in graph["nodes"]:
        parents = node["properties"].get("parents", [])
        parents = parents if isinstance(parents, list) else [parents]
        normalized_parents = [normalize_wikilink(str(p)) for p in parents]
        if len(normalized_parents) != len(set(normalized_parents)):
            issues.append({"kind": "duplicate_project_parent", "path": node["path"]})
        if node["properties"].get("type") == "project" and any(resolve_note_link(p, note_aliases([node]), node["id"]) == node["id"] or p == Path(node["path"]).stem for p in normalized_parents):
            issues.append({"kind": "self_project_parent", "path": node["path"]})
        if parents and node["properties"].get("type") != "project":
            issues.append({"kind": "parents_on_non_project", "path": node["path"]})
    registry_heads: dict[str, str] = {Path(path).name: head for path, head in registry_entries()}
    stable_sources = {x.get("id"): x for x in list_sources(ROOT) if x.get("id")}
    for path, head in registry_entries():
        if not (ROOT / path).is_dir():
            issues.append({"kind": "missing_source", "path": path, "recorded_head": head})
    for note in graph["nodes"]:
        for ref in note["source_refs"]:
            if ref.startswith("source:"):
                sid = ref.split(":", 1)[1]
                if sid not in stable_sources:
                    issues.append({"kind": "unregistered_source_ref", "path": note["path"], "ref": ref})
                continue
            match = REPO_REF_RE.match(ref)
            if not match:
                continue
            repo_id, commit, _ = match.groups()
            if repo_id not in registry_heads:
                issues.append({"kind": "unregistered_repo_ref", "path": note["path"], "ref": ref})
            elif not registry_heads[repo_id].startswith(commit):
                issues.append({"kind": "stale_repo_ref", "path": note["path"], "ref": ref, "registered_head": registry_heads[repo_id]})
    return {"issues": issues, "issue_count": len(issues)}


def _load_research_gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("research_gate", Path(__file__).resolve().parent / "research_gate.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def claim_ledger_report() -> list[dict]:
    """Spec §33: claims.yaml is an optional durable summary; flag when a newer
    sibling synthesis doc exists but the ledger was not refreshed (report-only)."""
    issues = []
    for ledger in sorted(VAULT.rglob("claims.yaml")):
        fields = {}
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1); fields[k.strip()] = v.strip().strip('"')
        run_id = fields.get("generated_from_run")
        if not run_id:
            updated = fields.get("updated")
            if updated:
                try:
                    ledger_date = datetime.fromisoformat(updated).date()
                    siblings = [p for p in ledger.parent.glob("*.md") if p != ledger]
                    newest = max((p.stat().st_mtime for p in siblings), default=None)
                    if newest is not None and datetime.fromtimestamp(newest).date() > ledger_date:
                        issues.append({"kind": "CLAIM_LEDGER_STALE", "ledger": str(ledger.relative_to(ROOT))})
                except ValueError:
                    pass
            continue
        gate = ROOT / ".knowledgeos" / "runs" / run_id / "gate.json"
        run = ROOT / ".knowledgeos" / "runs" / run_id / "run.json"
        if not gate.is_file() or not run.is_file() or json.loads(run.read_text()).get("state") != "COMMITTED":
            issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": str(ledger.relative_to(ROOT)), "run": run_id})
            continue
        gate_data = json.loads(gate.read_text())
        run_dir = ROOT / ".knowledgeos" / "runs" / run_id
        claims_path = run_dir / "claims.jsonl"
        if not claims_path.is_file():
            issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": str(ledger.relative_to(ROOT)), "run": run_id}); continue
        try:
            claims = [json.loads(x) for x in claims_path.read_text(encoding="utf-8").splitlines() if x.strip()]
            ledger_ids = {json.loads(x.strip()[2:].strip()).get("claim_id") for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip().startswith("- {")}
            durable = [dict(c, durable=True) for c in claims if c.get("durable") is True or c.get("claim_id") in ledger_ids]
            canonical = "\n".join(json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for c in durable)
            expected = __import__('hashlib').sha256(canonical.encode()).hexdigest()
            ledger_hash = fields.get("durable_claims_sha256") or fields.get("claims_sha256")
            if ledger_hash and ledger_hash != expected:
                issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": str(ledger.relative_to(ROOT)), "run": run_id})
            ledger_claims = [json.loads(x.strip()[2:].strip()) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip().startswith("- {")]
            actual = __import__('hashlib').sha256("\n".join(json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for c in ledger_claims).encode()).hexdigest()
            if ledger_hash and ledger_claims and actual != ledger_hash:
                issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": str(ledger.relative_to(ROOT)), "run": run_id})
        except (ValueError, json.JSONDecodeError):
            issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": str(ledger.relative_to(ROOT)), "run": run_id})
    return issues


def canonical_duplication_report() -> list[dict]:
    """Report long exact prose repeated across project docs with different owners."""
    issues: list[dict] = []
    for folder in sorted({p.parent for p in VAULT.glob("projects/*/*.md")}):
        docs = sorted(folder.glob("*.md"))
        if len(docs) < 2:
            continue
        paragraphs: dict[str, list[str]] = defaultdict(list)
        for path in docs:
            text = path.read_text(encoding="utf-8")
            text = re.sub(r"(?is)## Evidence Map.*", "", text)
            text = re.sub(r"(?is)<summary>Evidence Map</summary>.*", "", text)
            text = re.sub(r"(?m)^---.*?^---\s*", "", text, count=1, flags=re.S)
            for paragraph in re.split(r"\n\s*\n", text):
                compact = " ".join(x.strip() for x in paragraph.splitlines() if x.strip())
                if len(compact) >= 180:
                    paragraphs[compact].append(path.name)
        for paragraph, owners in paragraphs.items():
            if len(set(owners)) > 1:
                issues.append({"kind": "CANONICAL_DUPLICATION", "folder": str(folder.relative_to(ROOT)), "documents": sorted(set(owners)), "excerpt": paragraph[:180]})
    return issues


def knowledge_density_report() -> list[dict]:
    """Report suspiciously thin canonical research notes. Smoke alarm only, never a writing target."""
    issues: list[dict] = []
    for path in sorted(VAULT.glob("projects/*/*.md")):
        try:
            note = parse_note(path)
        except Exception:
            continue
        if note.get("properties", {}).get("type") != "project-doc":
            continue
        body = note.get("body", "").strip()
        name = path.name
        source_refs = note.get("properties", {}).get("source_refs", [])
        if not isinstance(source_refs, list):
            source_refs = [source_refs] if source_refs else []
        threshold = None
        role = None
        if name == "solutions.md":
            threshold, role = 3000, "solutions"
        elif name == "solution-space.md":
            threshold, role = 2500, "solution-space"
        elif len(source_refs) >= 4:
            threshold, role = 2000, "multi-source-focused"
        if threshold and len(body) < threshold:
            issues.append({"kind": "SUSPICIOUSLY_THIN_OUTPUT", "document": str(path.relative_to(ROOT)),
                           "role": role, "chars": len(body), "warning_threshold": threshold})
    return issues


def maintain() -> dict:
    graph = build_graph()
    report = {"source_drift": [], "issues": lint()["issues"],
              "research_gate": _load_research_gate().research_report(),
              "claim_ledger": claim_ledger_report(),
              "canonical_duplication": canonical_duplication_report(),
              "knowledge_density": knowledge_density_report(),
              "vector": {"enabled": vector_enabled(), "index": "present" if VECTOR_INDEX.is_file() and VECTOR_META.is_file() else "missing"}}
    repos = [(x.get("local_path") or x.get("path"), x.get("revision") or x.get("head"), x.get("id")) for x in list_sources(ROOT) if x.get("kind") in {"repository", "repositories"} and (x.get("local_path") or x.get("path"))]
    for local_path, ingested, source_id in repos or [(p, h, Path(p).name) for p, h in registry_entries()]:
        repo = ROOT / local_path
        try:
            current = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if current == ingested:
            continue
        try:
            changed = subprocess.check_output(["git", "-C", str(repo), "diff", "--name-only", f"{ingested}..{current}"], text=True).splitlines()
        except (OSError, subprocess.CalledProcessError):
            changed = []
        repo_id = repo.name
        direct = set()
        for ref, notes in graph["reverse_sources"].items():
            if ref == f"source:{source_id}" or ref.startswith(f"repo://{repo_id}@"):
                if ref.startswith("source:"):
                    direct.update(notes); continue
                path = ref.split("/", 3)[-1].split("#", 1)[0].split("::", 1)[0]
                if not changed or path in changed or any(path.startswith(c.rstrip("/" ) + "/") for c in changed):
                    direct.update(notes)
        impacted = set(direct)
        changed_flag = True
        while changed_flag:
            changed_flag = False
            for edge in graph["edges"]:
                if edge["kind"] == "derived_from" and edge["target"] in impacted and edge["source"] not in impacted:
                    impacted.add(edge["source"]); changed_flag = True
        report["source_drift"].append({"repo": local_path, "ingested_head": ingested, "current_head": current,
                                       "changed_files": changed, "direct_impacted": sorted(direct),
                                       "transitive_impacted": sorted(impacted - direct)})
    return report


def write_projection(name: str, payload: object) -> Path:
    DERIVED.mkdir(exist_ok=True)
    out = DERIVED / name
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_projects = sub.add_parser("projects")
    sub.add_parser("trace").add_argument("query")
    sub.add_parser("maintain")
    sub.add_parser("lint")
    sub.add_parser("rebuild")
    p_research = sub.add_parser("research")
    p_research.add_argument("research_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "research":
        return _load_research_gate().main(args.research_args)
    if args.command == "search":
        if vector_enabled():
            print(json.dumps(hybrid_search(args.query, args.limit), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(bm25(args.query, args.limit), ensure_ascii=False, indent=2))
    elif args.command == "projects":
        print(json.dumps(project_graph(), ensure_ascii=False, indent=2))
    elif args.command == "graph":
        print(json.dumps(build_graph(), ensure_ascii=False, indent=2))
    elif args.command == "trace":
        print(json.dumps(trace(args.query), ensure_ascii=False, indent=2))
    elif args.command == "provenance":
        graph = build_graph()
        print(json.dumps({"source_to_notes": graph["reverse_sources"], "note_to_sources": graph["note_to_sources"]}, ensure_ascii=False, indent=2))
    elif args.command == "maintain":
        print(json.dumps(maintain(), ensure_ascii=False, indent=2))
    elif args.command == "lint":
        print(json.dumps(lint(), ensure_ascii=False, indent=2))
    elif args.command == "rebuild":
        graph = build_graph()
        lint_report = lint()
        graph_path = write_projection("graph.json", graph)
        project_path = write_projection("projects.json", project_graph())
        vector_report = build_vector_index() if vector_enabled() else {"status": "disabled"}
        provenance_path = write_projection("provenance-index.json", {"source_to_notes": graph["reverse_sources"], "note_to_sources": graph["note_to_sources"]})
        lint_path = write_projection("lint-result.json", lint_report)
        print(json.dumps({"graph": str(graph_path.relative_to(ROOT)), "projects": str(project_path.relative_to(ROOT)), "provenance": str(provenance_path.relative_to(ROOT)), "lint": str(lint_path.relative_to(ROOT)), "vector": vector_report}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(lint(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
