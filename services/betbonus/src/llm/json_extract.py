"""Parse JSON from LLM chat — fences, thinking tags, trailing commas, truncation."""

from __future__ import annotations

import json
import re
from typing import Any

_THINK = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def llm_json_ok(data: dict[str, Any], *, require_vectors: bool = False) -> bool:
    if not isinstance(data, dict) or data.get("parse_error"):
        return False
    if require_vectors:
        return isinstance(data.get("abuse_vectors"), list)
    return True


def extract_json(content: str | None) -> dict[str, Any]:
    text = _normalize(content or "")
    if not text:
        return {"parse_error": True, "summary": "", "reason": "empty"}

    for candidate in _candidates(text):
        parsed = _loads_relaxed(candidate)
        if isinstance(parsed, dict):
            return parsed
        repaired = _repair_truncated_object(candidate)
        if isinstance(repaired, dict):
            repaired.setdefault("repaired", True)
            return repaired

    preview = text[:800]
    return {"parse_error": True, "summary": preview, "reason": "invalid_json"}


def _normalize(content: str) -> str:
    text = _THINK.sub("", content).strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    elif text.lstrip().startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text.lstrip(), flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _candidates(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    def add(chunk: str) -> None:
        chunk = chunk.strip()
        if chunk and chunk not in seen:
            seen.add(chunk)
            out.append(chunk)

    add(text)
    start = text.find("{")
    if start >= 0:
        add(text[start:])
        balanced = _slice_balanced_object(text, start)
        if balanced:
            add(balanced)
    return out


def _loads_relaxed(text: str) -> dict[str, Any] | None:
    blob = _TRAILING_COMMA.sub(r"\1", text)
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        try:
            data, _ = decoder.raw_decode(blob)
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _slice_balanced_object(text: str, start: int) -> str | None:
    in_str = False
    escape = False
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair_truncated_object(fragment: str) -> dict[str, Any] | None:
    start = fragment.find("{")
    if start < 0:
        return None
    body = fragment[start:]
    in_str = False
    escape = False
    stack: list[str] = []
    for ch in body:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()

    out = body
    if in_str:
        if escape:
            out = out[:-1]
        out += '"'

    stripped = out.rstrip()
    if stripped.endswith(":"):
        stripped += " null"
    elif stripped.endswith(","):
        stripped = stripped[:-1].rstrip()

    # dangling `"key"` without `:` at object level — drop incomplete key
    if stripped.endswith('"'):
        probe = stripped
        # if last quote pair is a key (no colon after previous comma/{)
        last_quote = probe.rfind('"')
        prev = probe.rfind('"', 0, last_quote)
        if prev >= 0:
            between = probe[prev + 1 : last_quote]
            prefix = probe[:prev].rstrip()
            if between and prefix.endswith(("{", ",", "[")):
                # incomplete string value already closed; keep it
                pass
            elif prefix.endswith(":"):
                pass
            elif prefix.endswith(("{", ",")):
                stripped = prefix.rstrip(" ,")

    for closer in reversed(stack):
        stripped = stripped.rstrip().rstrip(",")
        stripped += closer

    parsed = _loads_relaxed(stripped)
    return parsed
