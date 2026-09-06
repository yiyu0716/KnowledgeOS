"""Small, dependency-free Markdown model shared by readers and write guards.

Frontmatter supports scalar values and flat lists (block or inline). It is a
strict documented YAML subset, not a general YAML parser. Unsupported/ambiguous
syntax is reported; write guards fail closed rather than guessing ownership.
"""
from __future__ import annotations

import ast
import hashlib
import re
from collections import Counter


class FrontmatterError(ValueError):
    pass


def as_list(value):
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


def _without_comment(value: str) -> str:
    quote = None
    escape = False
    for i, ch in enumerate(value):
        if escape:
            escape = False
            continue
        if ch == "\\" and quote == '"':
            escape = True
        elif quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or value[i - 1] in "[, \t"):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1].isspace()):
            return value[:i].rstrip()
    if quote:
        raise FrontmatterError("unterminated quoted scalar")
    return value.strip()


def _scalar(value: str):
    value = _without_comment(value.strip())
    if value.startswith("'"):
        if not value.endswith("'"):
            raise FrontmatterError("invalid quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.startswith('"'):
        try:
            result = ast.literal_eval(value)
        except (ValueError, SyntaxError) as exc:
            raise FrontmatterError("unsupported double-quoted scalar") from exc
        if not isinstance(result, str):
            raise FrontmatterError("expected quoted text")
        return result
    if value.startswith(("{", "&", "*", "!", "|", ">", "[")):
        raise FrontmatterError("nested YAML, tags, anchors and block scalars are not supported")
    return value


def _value(value: str):
    clean = _without_comment(value.strip())
    if not clean.startswith("["):
        return _scalar(clean)
    if not clean.endswith("]"):
        raise FrontmatterError("invalid inline list")
    body = clean[1:-1]
    fields, buf, quote, escape = [], [], None, False
    for ch in body:
        if escape:
            buf.append(ch); escape = False; continue
        if ch == "\\" and quote == '"':
            buf.append(ch); escape = True; continue
        if quote:
            buf.append(ch)
            if ch == quote: quote = None
        elif ch in "\"'":
            quote = ch; buf.append(ch)
        elif ch == ",":
            fields.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    if quote:
        raise FrontmatterError("unterminated inline list scalar")
    if buf: fields.append("".join(buf))
    return [_scalar(x) for x in fields if x.strip()]


def frontmatter(text: str) -> tuple[dict, str, int]:
    """Return properties, unchanged body, and number of frontmatter lines."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, text, 0
    lines = text.splitlines(keepends=True)
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() in {"---", "..."}), None)
    if end is None:
        raise FrontmatterError("unclosed frontmatter")
    props, current, block_list = {}, None, False
    for line in lines[1:end]:
        raw = line.rstrip("\r\n")
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.lstrip().startswith("- "):
            if current is None or not block_list:
                raise FrontmatterError("list item without an empty property")
            props[current].append(_scalar(raw.lstrip()[2:]))
            continue
        if raw[:1].isspace() or ":" not in raw:
            raise FrontmatterError("only top-level scalars and flat lists are supported")
        key, value = raw.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) or key in props:
            raise FrontmatterError("invalid or duplicate property")
        current = key
        block_list = not _without_comment(value.strip())
        props[key] = [] if block_list else _value(value)
    return props, "".join(lines[end + 1:]), end + 1


def split_link(value: str) -> dict:
    raw = str(value).strip().strip('"\'`')
    if raw.startswith("[[") and raw.endswith("]]"):
        raw = raw[2:-2]
    target, sep, label = raw.partition("|")
    note, hashmark, anchor = target.partition("#")
    return {"note": note.strip(), "anchor": anchor.strip() if hashmark else "",
            "label": label.strip() if sep else "", "target": target.strip()}


def visible_lines(text: str):
    """Ignore fenced examples and HTML comments while preserving line numbers."""
    fence = None
    comment = False
    for number, line in enumerate(text.splitlines(), 1):
        if comment:
            if "-->" in line: comment = False
            continue
        if "<!--" in line:
            if "-->" not in line.split("<!--", 1)[1]: comment = True
            line = re.sub(r"<!--.*?-->", "", line).split("<!--", 1)[0]
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)
            if fence is None: fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence): fence = None
            continue
        if fence is None:
            yield number, line


def body_links(body: str, offset: int = 0) -> list[dict]:
    out = []
    for number, line in visible_lines(body):
        # Inline code is an example, not a relationship.
        clean = re.sub(r"`+[^`]*`+", "", line)
        for match in re.finditer(r"(!?)\[\[([^\]]+)\]\]", clean):
            link = split_link(match.group(2))
            out.append({**link, "line": number + offset, "embedded": bool(match.group(1)),
                        "context": line.strip()})
    return out


def sections(body: str, offset: int = 0) -> list[dict]:
    """Heading paths and occurrence ordinals are collision-free, not permanent IDs.

    A heading rename changes the generated ID. An explicit Obsidian block ID is
    the appropriate durable anchor when rename-stability matters.
    """
    lines = body.splitlines()
    headings = {}
    for i, line in visible_lines(body):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match: headings[i] = (len(match.group(1)), re.sub(r"\s+#+\s*$", "", match.group(2)))
    stack, out, occurrences = [], [], Counter()
    start, current, current_level = 1, [], 0

    def flush(end):
        text = "\n".join(lines[start - 1:end]).strip()
        if not text: return
        path = list(current)
        key = "#".join(path) or "Document"
        occurrences[key] += 1
        out.append({"heading": path[-1] if path else "Document", "heading_path": path,
                    "anchor": "#".join(path), "occurrence": occurrences[key],
                    "start_line": offset + start, "end_line": offset + end,
                    "body": text, "content_hash": hashlib.sha256(text.encode()).hexdigest()})

    for number, (level, heading) in headings.items():
        flush(number - 1)
        stack = [(d, h) for d, h in stack if d < level]
        stack.append((level, heading))
        current, current_level, start = [h for _, h in stack], level, number
    flush(len(lines))
    return out


def missing_project_roles(text: str) -> list[str]:
    roles = {
        "overview": {"project overview", "overview", "项目概述", "概述"},
        "task": {"task", "problem model", "任务", "问题模型"},
        "evaluation": {"evaluation", "评估", "评价标准"},
        "challenges": {"core challenges", "challenges", "核心挑战", "挑战"},
        "solutions": {"solution landscape", "solutions", "方案全景", "方案概览"},
        "conclusions": {"top 3 principles", "top principles", "compressed conclusions", "核心原则", "压缩结论", "核心结论"},
        "evidence": {"evidence map", "证据地图", "证据映射"},
    }
    _, body, _ = frontmatter(text)
    labels = {re.sub(r"^\d+[.、)\s]+", "", x["heading"]).strip().casefold() for x in sections(body)}
    labels.update(x.strip().casefold() for x in re.findall(r"<summary>(.*?)</summary>", body))
    return [role for role, names in roles.items() if not labels & names]
