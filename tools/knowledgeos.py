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

from markdown_model import (frontmatter, FrontmatterError, as_list, split_link, body_links, visible_lines, sections, missing_project_roles)
from durable_provenance import (atomic_write, atomic_json, safe_id, verified_archives, finalization_entries, rebuild_finalizations, archive_audit, provenance_for)
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
    return split_link(value)["note"]


def normalize_source_ref(value: str) -> str:
    return value.strip().strip('"\'`').rstrip("。，；,.;:)]}")


def canonical_id(path: Path) -> str:
    rel = path.relative_to(VAULT).with_suffix("")
    return "/".join(rel.parts)


def note_aliases(notes: list[dict]) -> dict[str, list[str]]:
    aliases = defaultdict(set)
    for note in notes:
        names = [note["id"], note["path"], Path(note["path"]).name, Path(note["path"]).stem]
        names.extend(as_list(note["properties"].get("aliases")))
        for alias in names:
            if isinstance(alias, str) and alias.strip(): aliases[alias.strip()].add(note["id"])
    return {key: sorted(value) for key, value in aliases.items()}


def resolve_note_link(value: str, aliases: dict[str, list[str]], source_id: str | None = None) -> str | None:
    target = normalize_wikilink(value)
    if not target: return source_id  # [[#Heading]] or [[#^block]]
    candidates = sorted(set(aliases.get(target, [])))
    if not candidates and target.endswith(".md"):
        candidates = sorted(set(aliases.get(target[:-3], [])))
    if not candidates and "/" not in target:
        candidates = sorted(set(aliases.get(Path(target).stem, [])))
    if source_id and len(candidates) > 1:
        folder = source_id.rsplit("/", 1)[0]
        local = [x for x in candidates if x.rsplit("/", 1)[0] == folder]
        if len(local) == 1: return local[0]
    return candidates[0] if len(candidates) == 1 else None


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
    errors = []
    try:
        props, body, offset = frontmatter(text)
    except FrontmatterError as exc:
        props, body, offset = {}, text, 0
        errors.append(str(exc))
    refs = [normalize_source_ref(str(x)) for x in as_list(props.get("source_refs")) if x]
    links = body_links(body, offset)
    for key in ("projects", "derived_from", "parents"):
        for value in as_list(props.get(key)):
            if value: links.append({**split_link(str(value)), "property": key, "line": None, "context": "", "embedded": False})
    try:
        rel_path = str(path.relative_to(ROOT))
    except ValueError:
        rel_path = str(path.relative_to(VAULT.parent))
    return {"path": rel_path, "id": canonical_id(path), "properties": props,
            "links": sorted({x["note"] for x in links if x["note"]}), "link_details": links,
            "source_refs": sorted(set(refs)),
            "inline_source_refs": sorted(set(normalize_source_ref(x) for x in SOURCE_RE.findall(body))),
            "body": body, "body_line_offset": offset, "parse_errors": errors}


def build_graph() -> dict:
    notes = [parse_note(p) for p in markdown_files()]
    aliases = note_aliases(notes)
    by_id = {n["id"]: n for n in notes}
    edges, wanted, seen = [], [], set()
    reverse_sources, note_to_sources = defaultdict(list), defaultdict(list)
    for note in notes:
        source = note["id"]
        for link in note["link_details"]:
            resolved = resolve_note_link(link["target"], aliases, source)
            kind = link.get("property", "embed" if link.get("embedded") else "wikilink")
            edge = {"source": source, "target": resolved or link["note"], "kind": kind,
                    "anchor": link["anchor"], "line": link.get("line"), "context": link.get("context", "")}
            key = (source, edge["target"], kind, link["anchor"], link.get("line"))
            if key in seen: continue
            seen.add(key); edges.append(edge)
            if not resolved:
                wanted.append({**edge, "reason": "missing_or_ambiguous_note"}); continue
            anchor = link["anchor"]
            if anchor:
                target = by_id[resolved]
                if anchor.startswith("^"):
                    found = sum(bool(re.search(r"(?:^|\s)" + re.escape(anchor) + r"\s*$", line)) for _, line in visible_lines(target["body"]))
                else:
                    chunks = sections(target["body"])
                    found = sum(1 for chunk in chunks if anchor.casefold() in {chunk["anchor"].casefold(), chunk["heading"].casefold()})
                if found != 1:
                    wanted.append({**edge, "reason": "missing_anchor" if not found else "ambiguous_anchor"})
        for ref in note["source_refs"]:
            reverse_sources[ref].append(source); note_to_sources[source].append(ref)
            edges.append({"source": source, "target": ref, "kind": "source_refs"})
    connected = {x for edge in edges if edge["target"] in by_id for x in (edge["source"], edge["target"])}
    return {"nodes": notes, "edges": edges, "wanted_links": wanted,
            "orphans": sorted(set(by_id) - connected), "reverse_sources": reverse_sources,
            "note_to_sources": note_to_sources, "node_ids": sorted(by_id)}


def project_graph() -> dict:
    graph = build_graph()
    projects = {n["id"]: n for n in graph["nodes"] if n["properties"].get("type") == "project"}
    aliases, all_aliases = note_aliases(list(projects.values())), note_aliases(graph["nodes"])
    edges, unresolved, multi = [], [], []
    for node in projects.values():
        seen = set()
        for value in as_list(node["properties"].get("parents")):
            target = resolve_note_link(str(value), aliases, node["id"])
            if not target:
                other = resolve_note_link(str(value), all_aliases, node["id"])
                unresolved.append({"source": node["id"], "target": other or normalize_wikilink(str(value)),
                                   "kind": "non_project_parent" if other else "missing_parent"})
            elif target not in seen:
                seen.add(target); edges.append({"parent": target, "child": node["id"]})
        if len(seen) > 1: multi.append(node["id"])
    adjacency = defaultdict(list)
    for edge in edges: adjacency[edge["parent"]].append(edge["child"])
    # Iterative three-color traversal avoids recursion depth and repeated DAG walks.
    colors, cycles = {}, []
    for start in projects:
        if colors.get(start): continue
        stack, path = [(start, iter(adjacency[start]))], [start]
        colors[start] = 1
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                colors[node] = 2; stack.pop(); path.pop(); continue
            if colors.get(child) == 1:
                cycles.append(path[path.index(child):] + [child])
            elif not colors.get(child):
                colors[child] = 1; path.append(child); stack.append((child, iter(adjacency[child])))
    child_ids = {edge["child"] for edge in edges}
    return {"nodes": sorted(projects), "edges": edges, "roots": sorted(set(projects) - child_ids),
            "multi_parent": sorted(multi), "unresolved_parents": unresolved, "cycles": cycles}


def snippet(text: str, query_terms: list[str], width: int = 180) -> str:
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    positions = [compact.lower().find(term.lower()) for term in query_terms if compact.lower().find(term.lower()) >= 0]
    start = max(0, min(positions) - 60) if positions else 0
    excerpt = compact[start:start + width]
    return ("..." if start else "") + excerpt + ("..." if start + width < len(compact) else "")


def bm25(query: str, limit: int = 10) -> list[dict]:
    if limit < 1: return []
    q = set(tokens(query))
    if not q: return []
    notes = [parse_note(p) for p in markdown_files()]
    docs = []
    for note in notes:
        title = Path(note["path"]).stem.replace("-", " ") + " " + " ".join(map(str, as_list(note["properties"].get("aliases"))))
        props = " ".join(map(str, note["properties"].values()))
        terms = tokens(title + " " + props + " " + note["body"])
        docs.append((note, title, props, Counter(terms), len(terms), set(tokens(title)), set(tokens(props))))
    average = sum(x[4] for x in docs) / max(1, len(docs))
    df = Counter(term for _, _, _, counts, _, _, _ in docs for term in counts)
    results = []
    for note, title, props, counts, length, title_terms, property_terms in docs:
        score = 0.0
        for term in q & counts.keys():
            idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
            tf = counts[term]
            score += idf * tf * 2.2 / (tf + 1.2 * (.65 + .35 * length / max(1, average)))
            score += 2.0 if term in title_terms else .5 if term in property_terms else 0
        if query.strip().casefold() in (title + " " + props + " " + note["body"]).casefold(): score += 2.5
        kind = note["properties"].get("type")
        score *= 1.25 if kind == "learning" else 1.35 if kind == "project-doc" else 1
        if not score: continue
        parts = sections(note["body"], note["body_line_offset"])
        def section_score(part):
            words = set(tokens(part["body"]))
            return (sum(math.log(1 + (len(docs) + .5) / (df.get(t, 0) + .5)) for t in q & words), -part["start_line"])
        best = max(parts, key=section_score) if parts else None
        result = {"id": note["id"], "path": note["path"], "type": kind,
                  "learning_kind": note["properties"].get("learning_kind"), "score": round(score, 5),
                  "snippet": snippet(best["body"] if best else note["body"], sorted(q)),
                  "matched_terms": sorted(q & counts.keys())}
        if best: result.update({key: best[key] for key in ("heading", "heading_path", "anchor", "start_line", "end_line")})
        results.append(result)
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
        for part in sections(note["body"], note["body_line_offset"]):
            # Evidence is traceable but not used to swamp conceptual embeddings.
            if any(x.casefold() in {"evidence map", "证据地图", "证据映射"} for x in part["heading_path"]): continue
            identity = json.dumps([note["id"], part["heading_path"], part["occurrence"]], ensure_ascii=False)
            chunk_id = note["id"] + "::" + __import__('hashlib').sha256(identity.encode()).hexdigest()[:24]
            text = f"Title: {Path(note['path']).stem}\nAliases: {note['properties'].get('aliases', [])}\nType: {note['properties'].get('type')}\nHeading: {' / '.join(part['heading_path'])}\n{part['body']}"
            chunks.append({**part, "chunk_id": chunk_id, "note_id": note["id"], "path": note["path"],
                           "note_type": note["properties"].get("type"), "learning_kind": note["properties"].get("learning_kind"),
                           "text": text, "content_hash": __import__('hashlib').sha256(text.encode()).hexdigest()})
    return chunks


def build_vector_index() -> dict:
    provider = str(config_value("provider", "sentence-transformers"))
    model_name = str(config_value("model", "Qwen/Qwen3-Embedding-0.6B"))
    chunks = semantic_chunks()
    try:
        import numpy as np
        requested_dim = int(config_value("dimension", "0"))
        if requested_dim < 0: raise ValueError("dimension must be non-negative")
        if not chunks:
            VECTOR_INDEX.unlink(missing_ok=True); VECTOR_META.unlink(missing_ok=True)
            return {"status": "empty", "chunks": 0}
        if provider == "ollama":
            endpoint = str(config_value("endpoint", "http://localhost:11434")).rstrip("/") + "/api/embed"
            batches = []
            for start in range(0, len(chunks), 32):
                payload = json.dumps({"model": model_name, "input": [x["text"] for x in chunks[start:start + 32]]}).encode()
                req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=120) as response:
                    batches.extend(json.loads(response.read())["embeddings"])
            vectors = np.asarray(batches, dtype="float32")
        elif provider == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(model_name)
            encoder = getattr(model, "encode_document", model.encode)
            vectors = np.asarray(encoder([x["text"] for x in chunks], normalize_embeddings=False), dtype="float32")
        else:
            raise ValueError("unsupported vector provider")
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or not np.isfinite(vectors).all():
            raise ValueError("invalid embedding shape or non-finite values")
        if requested_dim:
            if requested_dim > vectors.shape[1]: raise ValueError("configured dimension exceeds embedding dimension")
            vectors = vectors[:, :requested_dim]
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms < 1e-12): raise ValueError("zero embedding")
        vectors = vectors / norms
        import io
        buffer = io.BytesIO(); np.savez_compressed(buffer, embeddings=vectors)
        data = buffer.getvalue()
        atomic_write(VECTOR_INDEX, data)
        atomic_json(VECTOR_META, {"schema_version": 2, "provider": provider, "model": model_name,
                    "requested_dimension": requested_dim, "dimension": int(vectors.shape[1]),
                    "corpus_sha256": _corpus_hash(chunks), "index_sha256": __import__('hashlib').sha256(data).hexdigest(), "chunks": chunks})
        return {"status": "built", "provider": provider, "chunks": len(chunks), "dimension": int(vectors.shape[1]), "model": model_name}
    except Exception as exc:
        return {"status": "unavailable", "provider": provider, "reason": str(exc)}


def vector_search(query: str, limit: int = 20) -> tuple[list[dict], str | None]:
    try:
        import numpy as np
        if limit < 1: return [], None
        if not VECTOR_INDEX.is_file() or not VECTOR_META.is_file(): return [], "vector index missing; run rebuild"
        meta = json.loads(VECTOR_META.read_text(encoding="utf-8"))
        if meta.get("schema_version") != 2 or meta.get("corpus_sha256") != _corpus_hash(semantic_chunks()):
            return [], "vector index stale; run rebuild"
        if meta.get("model") != str(config_value("model", "Qwen/Qwen3-Embedding-0.6B")) or meta.get("provider") != str(config_value("provider", "sentence-transformers")) or meta.get("requested_dimension") != int(config_value("dimension", "0")):
            return [], "vector configuration changed; run rebuild"
        if __import__('hashlib').sha256(VECTOR_INDEX.read_bytes()).hexdigest() != meta.get("index_sha256"):
            return [], "vector index checksum mismatch; run rebuild"
        if meta["provider"] == "ollama":
            endpoint = str(config_value("endpoint", "http://localhost:11434")).rstrip("/") + "/api/embed"
            payload = json.dumps({"model": meta["model"], "input": [query]}).encode()
            req = urllib.request.Request(endpoint, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                vector = np.asarray(json.loads(response.read())["embeddings"][0], dtype="float32")
        else:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(meta["model"])
            encoder = getattr(model, "encode_query", model.encode)
            vector = np.asarray(encoder([query], normalize_embeddings=False)[0], dtype="float32")
        dimension = int(meta["dimension"])
        if vector.ndim != 1 or len(vector) < dimension or not np.isfinite(vector).all(): raise ValueError("query embedding shape mismatch")
        vector = vector[:dimension]
        norm = float(np.linalg.norm(vector))
        if norm < 1e-12: raise ValueError("zero query embedding")
        with np.load(VECTOR_INDEX, allow_pickle=False) as loaded:
            matrix = loaded["embeddings"]
            if matrix.shape != (len(meta["chunks"]), dimension): raise ValueError("index shape mismatch")
            scores = matrix @ (vector / norm)
        # Best chunk per note, then dense note ranks; a long note cannot consume all slots.
        best = {}
        for index in np.argsort(-scores, kind="stable"):
            chunk = meta["chunks"][int(index)]
            if chunk["note_id"] in best: continue
            best[chunk["note_id"]] = {"id": chunk["note_id"], "score": float(scores[index]), "rank": len(best) + 1,
                **{k: chunk[k] for k in ("chunk_id", "heading", "heading_path", "anchor", "start_line", "end_line")},
                "snippet": snippet(chunk["body"], tokens(query))}
            if len(best) >= limit: break
        return list(best.values()), None
    except Exception as exc:
        return [], f"vector search unavailable; using BM25 only ({exc})"


def rrf_score(ranks: list[int], k: int = 60) -> float:
    return sum(1 / (k + rank) for rank in ranks)


def hybrid_search(query: str, limit: int = 10) -> list[dict]:
    if limit < 1: return []
    lexical = bm25(query, max(20, limit))
    semantic, warning = vector_search(query, max(20, limit))
    if warning: print(warning, file=sys.stderr)
    if not semantic: return lexical[:limit]
    ranks, best_semantic = {}, {}
    for rank, item in enumerate(lexical, 1): ranks.setdefault(item["id"], {})["bm25"] = rank
    for item in semantic:
        old = best_semantic.get(item["id"])
        if old is None or item["rank"] < old["rank"]: best_semantic[item["id"]] = item
    for rank, item in enumerate(sorted(best_semantic.values(), key=lambda x: (x["rank"], x["id"])), 1):
        ranks.setdefault(item["id"], {})["vector"] = rank
    by_id = {n["id"]: {"id": n["id"], "path": n["path"], "type": n["properties"].get("type"), "learning_kind": n["properties"].get("learning_kind")} for n in build_graph()["nodes"]}
    by_id.update({x["id"]: dict(x) for x in lexical})
    out = []
    for note_id, rank in ranks.items():
        item = dict(by_id.get(note_id, {"id": note_id, "path": note_id, "type": None}))
        sem = best_semantic.get(note_id)
        if sem:
            item["semantic_match"] = {k: sem[k] for k in ("chunk_id", "heading", "heading_path", "anchor", "start_line", "end_line", "snippet") if k in sem}
            for key, value in item["semantic_match"].items(): item.setdefault(key, value)
        score = rrf_score(list(rank.values())) * (1.10 if item.get("type") == "learning" else 1.0)
        item.update(rrf=round(score, 6), bm25_rank=rank.get("bm25"), vector_rank=rank.get("vector"))
        out.append(item)
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
    issues = [{"kind": "invalid_frontmatter", "path": note["path"], "detail": message} for message in note.get("parse_errors", [])]
    if issues: return issues
    path = ROOT / note["path"]
    if not path.exists(): path = VAULT.parent / note["path"]
    text = path.read_text(encoding="utf-8")
    kind = note["properties"].get("type")
    if kind in {"project", "project-doc"}:
        if len(re.findall(r"repo://[^\s)`]+", note["body"])) > 3:
            issues.append({"kind": "path_heavy_prose", "path": note["path"]})
        if any(str(x).startswith("repo://") for x in note["source_refs"]):
            issues.append({"kind": "PROVENANCE_MIGRATION_WARNING", "path": note["path"]})
        chunks = sections(note["body"])
        positions = [i for i, part in enumerate(chunks) if part["heading"].casefold() in {"evidence map", "证据地图", "证据映射"}]
        if positions and positions[-1] < len(chunks) - 1:
            later = chunks[positions[-1] + 1:]
            if any("Evidence Map" not in part["heading_path"] for part in later):
                issues.append({"kind": "evidence_map_not_last", "path": note["path"]})
    if kind == "project":
        missing = missing_project_roles(text)
        if missing: issues.append({"kind": "project_home_incomplete", "path": note["path"], "missing_roles": missing})
    learning_kind = note["properties"].get("learning_kind")
    if learning_kind and (kind != "learning" or (not isinstance(learning_kind, str) or learning_kind not in {"project", "mechanism"})):
        issues.append({"kind": "invalid_learning_kind", "path": note["path"]})
    return issues


def trace(query: str) -> dict:
    graph = build_graph()
    resolved = resolve_note_link(query, note_aliases(graph["nodes"]))
    matches = [note for note in graph["nodes"] if note["id"] == resolved]
    ids = {note["id"] for note in matches}
    return {"query": query, "anchor": split_link(query)["anchor"], "matches": sorted(ids),
            "relations": [e for e in graph["edges"] if e["source"] in ids or e["target"] in ids],
            "source_refs": sorted({ref for n in matches for ref in n["source_refs"]}),
            "accepted_evidence": provenance_for(ROOT, {n["path"] for n in matches})}


def lint() -> dict:
    graph = build_graph()
    issues = [{"kind": "unresolved_link", **edge} for edge in graph["wanted_links"]]
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
    module.ROOT = ROOT
    module.DERIVED = ROOT / ".knowledgeos"
    module.RUNS_DIR = module.DERIVED / "runs"
    module.FINALIZATIONS_PATH = module.DERIVED / "finalizations.json"
    return module


def claim_ledger_report() -> list[dict]:
    issues = []
    archives, archive_issues = verified_archives(ROOT)
    archived = {record["run_id"]: record for record in archives}
    entries = finalization_entries(ROOT)
    for ledger in sorted(VAULT.rglob("claims.yaml")):
        label = str(ledger.relative_to(ROOT))
        try:
            fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip().strip('"') for line in ledger.read_text().splitlines() if ":" in line and not line.startswith(" ")}
            rid = fields.get("generated_from_run")
            if not rid:
                issues.append({"kind": "CLAIM_LEDGER_STALE", "ledger": label, "detail": "ledger lacks generated_from_run"}); continue
            safe_id(rid)
            run_dir = ROOT / "sources/research" / rid if rid in archived else ROOT / ".knowledgeos/runs" / rid
            data = json.loads((run_dir / "run.json").read_text())
            if data.get("state") != "COMMITTED": raise ValueError("run not committed")
            canonical = str((ledger.parent / "solution-space.md").relative_to(ROOT))
            candidates = [entry for entry in entries if entry.get("output") == canonical]
            if candidates and max(candidates, key=lambda x: (x.get("finalized_at", ""), x["run_id"]))["run_id"] != rid:
                issues.append({"kind": "CLAIM_LEDGER_STALE", "ledger": label, "run": rid, "active_run": max(candidates, key=lambda x: (x.get("finalized_at", ""), x["run_id"]))["run_id"]}); continue
            claims = [json.loads(line) for line in (run_dir / "claims.jsonl").read_text().splitlines() if line.strip()]
            durable = [claim for claim in claims if claim.get("durable") is True]
            ledger_claims = [json.loads(line.strip()[2:]) for line in ledger.read_text().splitlines() if line.strip().startswith("- {")]
            def sha(rows):
                return __import__('hashlib').sha256("\n".join(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for row in rows).encode()).hexdigest()
            if not fields.get("durable_claims_sha256") or sha(durable) != fields["durable_claims_sha256"] or sha(ledger_claims) != sha(durable):
                raise ValueError("ledger differs from accepted durable claims")
        except (OSError, ValueError, KeyError, TypeError):
            issues.append({"kind": "CLAIM_LEDGER_DRIFT", "ledger": label})
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
    search = sub.add_parser("search"); search.add_argument("query"); search.add_argument("--limit", type=int, default=10)
    for name in ("projects", "graph", "provenance", "maintain", "lint", "rebuild", "reuse"): sub.add_parser(name)
    sub.add_parser("trace").add_argument("query")
    sub.add_parser("eval").add_argument("suite")
    research = sub.add_parser("research"); research.add_argument("research_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == "research": return _load_research_gate().main(args.research_args)
        if args.command == "search":
            result = hybrid_search(args.query, args.limit) if vector_enabled() else bm25(args.query, args.limit)
        elif args.command == "projects": result = project_graph()
        elif args.command == "graph": result = build_graph()
        elif args.command == "trace": result = trace(args.query)
        elif args.command == "reuse": result = reuse_report()
        elif args.command == "eval": result = retrieval_eval(args.suite)
        elif args.command == "provenance":
            graph = build_graph()
            result = {"source_to_notes": graph["reverse_sources"], "note_to_sources": graph["note_to_sources"], "accepted": archive_audit(ROOT)}
        elif args.command == "maintain":
            result = maintain(); result["accepted_provenance"] = archive_audit(ROOT); result["declared_reuse"] = reuse_report()
        elif args.command == "lint":
            result = lint()
        else:
            graph = build_graph()
            result = {"graph": str(write_projection("graph.json", graph).relative_to(ROOT)),
                      "projects": str(write_projection("projects.json", project_graph()).relative_to(ROOT)),
                      "provenance": str(write_projection("provenance-index.json", {"source_to_notes": graph["reverse_sources"], "note_to_sources": graph["note_to_sources"]}).relative_to(ROOT)),
                      "lint": str(write_projection("lint-result.json", lint()).relative_to(ROOT)),
                      "accepted_evidence": rebuild_finalizations(ROOT),
                      "vector": build_vector_index() if vector_enabled() else {"status": "disabled"}}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "eval": return 0 if result["passed"] == result["case_count"] else 1
        if args.command == "lint": return 1 if result["issue_count"] else 0
        if args.command == "rebuild" and not result["accepted_evidence"].get("ok"): return 1
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)); return 1



def _corpus_hash(chunks: list[dict]) -> str:
    return __import__('hashlib').sha256(json.dumps([(x["chunk_id"], x["content_hash"]) for x in chunks], ensure_ascii=False).encode()).hexdigest()


def reuse_report() -> dict:
    graph = build_graph()
    notes = {note["id"]: note for note in graph["nodes"]}
    uses = []
    for edge in graph["edges"]:
        source, target = notes.get(edge["source"]), notes.get(edge["target"])
        if not source or not target or edge["kind"] not in {"wikilink", "embed"}: continue
        if source["properties"].get("type") not in {"project", "project-doc"} or target["properties"].get("type") != "learning": continue
        line = edge.get("line") or 0
        part = next((part for part in sections(source["body"], source["body_line_offset"]) if part["start_line"] <= line <= part["end_line"]), None)
        if part and any(heading.casefold() in {"applications", "application records", "应用记录", "复用记录"} for heading in part["heading_path"]):
            uses.append({"project_note": source["id"], "learning": target["id"], "line": line,
                         "context": edge["context"], "record": part["body"], "verification": "declared-use-not-validated-effect"})
    return {"declared_applications": uses, "count": len(uses), "note": "projects/derived_from metadata and ordinary links are not counted as successful reuse"}


def retrieval_eval(path: str) -> dict:
    suite = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = suite.get("cases", [])
    if not cases: raise ValueError("retrieval suite must contain cases")
    limit = int(suite.get("top_k", 5))
    if limit < 1: raise ValueError("top_k must be positive")
    rows = []
    for case in cases:
        results = hybrid_search(case["query"], limit) if vector_enabled() else bm25(case["query"], limit)
        expected = set(case["expected_ids"])
        if not expected: raise ValueError("expected_ids must not be empty")
        found = {item["id"] for item in results}
        first = next((i for i, item in enumerate(results, 1) if item["id"] in expected), None)
        # Check only the relevant result surface, never an unrelated match.
        text = "\n".join(str(item.get("snippet", "")) + " " + json.dumps(item.get("semantic_match", {}), ensure_ascii=False) for item in results if item["id"] in expected)
        missing = [term for term in case.get("required_terms", []) if term.casefold() not in text.casefold()]
        rows.append({"id": case.get("id", case["query"]), "recall": len(expected & found) / len(expected),
                     "reciprocal_rank": 1 / first if first else 0, "missing_terms": missing,
                     "passed": expected <= found and not missing, "results": results})
    return {"cases": rows, "case_count": len(rows), "passed": sum(row["passed"] for row in rows),
            "mean_recall_at_k": sum(row["recall"] for row in rows) / len(rows),
            "mrr_at_k": sum(row["reciprocal_rank"] for row in rows) / len(rows),
            "limitation": "retrieval/term-preservation checks, not semantic correctness or real-world reuse validation"}

if __name__ == "__main__":
    raise SystemExit(main())
