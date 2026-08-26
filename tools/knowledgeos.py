#!/usr/bin/env python3
"""Dependency-light KnowledgeOS projections: search, graph, provenance, lint."""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
DERIVED = ROOT / ".knowledgeos"
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


def tokens(text: str) -> list[str]:
    chars = TOKEN_RE.findall(text)
    out = [x.lower() for x in chars]
    han = "".join(x for x in chars if re.fullmatch(r"[一-鿿]", x))
    out.extend(han[i:i + 2] for i in range(len(han) - 1))
    return out


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


def bm25(query: str, limit: int = 10) -> list[dict]:
    notes = [parse_note(p) for p in markdown_files()]
    q = tokens(query)
    if not q:
        return []
    docs = []
    for n in notes:
        title = Path(n["path"]).stem.replace("-", " ")
        text = title + " " + " ".join(map(str, n["properties"].values())) + " " + n["body"]
        docs.append((n, Counter(tokens(text)), len(tokens(text)), set(tokens(title))))
    avgdl = sum(x[2] for x in docs) / max(1, len(docs))
    df = Counter(term for _, counts, _, _ in docs for term in counts)
    results = []
    for n, counts, dl, title_terms in docs:
        score = 0.0
        for term in q:
            if term not in counts:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            tf = counts[term]
            score += idf * (tf * 2.2 / (tf + 1.2 * (0.65 + 0.35 * dl / max(1, avgdl))))
            if term in title_terms:
                score += 1.5
        score *= 1.25 if n["properties"].get("type") == "learning" else 1.0
        if score:
            results.append({"path": n["path"], "id": n["id"], "score": round(score, 5), "type": n["properties"].get("type")})
    return sorted(results, key=lambda x: (-x["score"], x["path"]))[:limit]

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
    if not text_path.exists():
        text_path = VAULT.parent / note["path"]
    text = text_path.read_text(encoding="utf-8")
    if note["properties"].get("type") in {"project", "project-doc"}:
        marker = "## Evidence Map"
        if marker in text:
            tail = text[text.rfind(marker):].splitlines()[1:]
            if any(line.startswith("## ") for line in tail):
                issues.append({"kind": "evidence_map_not_last", "path": note["path"]})
        if "Evidence and limits" in text:
            issues.append({"kind": "legacy_evidence_section", "path": note["path"]})
        body = note["body"]
        if len(re.findall(r"repo://[^\s)`]+", body)) > 3:
            issues.append({"kind": "path_heavy_prose", "path": note["path"]})
    if note["properties"].get("type") == "project":
        required = ["Project Overview", "Task", "Evaluation", "Core Challenges", "Solution Landscape", "Top 3 Principles", "Evidence Map"]
        missing = [x for x in required if f"## {x}" not in text and f"# {x}" not in text]
        if missing:
            issues.append({"kind": "project_home_incomplete", "path": note["path"], "missing": missing})
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
    for path, head in registry_entries():
        if not (ROOT / path).is_dir():
            issues.append({"kind": "missing_source", "path": path, "recorded_head": head})
    for note in graph["nodes"]:
        for ref in note["source_refs"]:
            match = REPO_REF_RE.match(ref)
            if not match:
                continue
            repo_id, commit, _ = match.groups()
            if repo_id not in registry_heads:
                issues.append({"kind": "unregistered_repo_ref", "path": note["path"], "ref": ref})
            elif not registry_heads[repo_id].startswith(commit):
                issues.append({"kind": "stale_repo_ref", "path": note["path"], "ref": ref, "registered_head": registry_heads[repo_id]})
    return {"issues": issues, "issue_count": len(issues)}


def maintain() -> dict:
    graph = build_graph()
    report = {"source_drift": [], "issues": lint()["issues"]}
    for local_path, ingested in registry_entries():
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
            if ref.startswith(f"repo://{repo_id}@"):
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
    args = parser.parse_args()
    if args.command == "search":
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
        provenance_path = write_projection("provenance-index.json", {"source_to_notes": graph["reverse_sources"], "note_to_sources": graph["note_to_sources"]})
        lint_path = write_projection("lint-result.json", lint_report)
        print(json.dumps({"graph": str(graph_path.relative_to(ROOT)), "projects": str(project_path.relative_to(ROOT)), "provenance": str(provenance_path.relative_to(ROOT)), "lint": str(lint_path.relative_to(ROOT))}, indent=2))
    else:
        print(json.dumps(lint(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
