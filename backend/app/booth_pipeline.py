"""Booth Layout pipeline — the LLM-orchestration half that wraps the deterministic
spatial engine in `app.spatial`.

Flow per chat turn:  read element catalog (uploaded data source) → Synthesise a
functional program from the exhibitor's natural language (LLM when an API key is
present, deterministic keyword parser otherwise) → run the spatial engine →
Explain the result. The program is returned so the chat layer can persist it and
feed it back on the next turn (the iteration loop: "add a demo station").
"""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path

from app.db import connect
from app.ingestion import parse_sheets
from app.llm import LLMProvider
from app.spatial import OPEN_BY_TYPE, ZONE_KINDS, plan_layout, to_artifact

PROGRAM_RE = re.compile(r"```(?:program|json)?\s*(\{.*?\})\s*```", re.DOTALL)

# Map free-text words to canonical zone kinds (longest / most specific first).
KIND_SYNONYMS: list[tuple[str, list[str]]] = [
    ("reception", ["reception", "welcome", "greeter", "front desk"]),
    ("meeting", ["meeting room", "meeting", "conference", "boardroom", "huddle"]),
    ("demo", ["demo station", "demo pod", "demo", "demonstration", "kiosk", "pod"]),
    ("storage", ["storage", "store room", "stockroom", "back office", "closet"]),
    ("display", ["display", "showcase", "product wall", "exhibit", "shelving"]),
    ("lounge", ["lounge", "seating area", "sofa", "waiting area"]),
    ("cafe", ["cafe", "café", "coffee bar", "coffee", "catering", "refreshment", "bar"]),
    ("counter", ["counter", "service desk"]),
    ("info", ["info desk", "information", "help desk", "helpdesk", "info"]),
    ("product", ["product feature", "feature wall", "product"]),
]
PRIORITY = {
    "reception": 5, "meeting": 4, "demo": 3, "cafe": 3, "counter": 3,
    "info": 3, "lounge": 2, "display": 2, "product": 2, "storage": 1,
}
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
DEFAULT_ZONES = [
    {"kind": "reception", "count": 1},
    {"kind": "demo", "count": 2},
    {"kind": "meeting", "count": 1},
    {"kind": "storage", "count": 1},
]


# --------------------------------------------------------------------------- #
# Catalog (uploaded data source)
# --------------------------------------------------------------------------- #
def _find_col(headers: list[str], *candidates: str) -> str | None:
    low = {h.lower(): h for h in headers}
    for cand in candidates:
        for key, original in low.items():
            if cand in key:
                return original
    return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(m.group()) if m else None


def _canon_kind(text: str) -> str | None:
    t = (text or "").lower()
    for kind, words in KIND_SYNONYMS:
        if any(w in t for w in words):
            return kind
    return kind_if_known(t)


def kind_if_known(text: str) -> str | None:
    t = (text or "").lower().strip()
    return t if t in ZONE_KINDS else None


def read_catalog(data_source_id: int | None) -> dict:
    """Return {by_kind: {kind: {w,d,height}}, booth_meta: {...}|None} parsed from
    the uploaded data source. Best-effort: returns empties if unavailable."""
    catalog: dict = {"by_kind": {}, "booth_meta": None}
    if not data_source_id:
        return catalog
    conn = connect()
    row = conn.execute(
        "SELECT * FROM data_sources WHERE id = ?", (data_source_id,)
    ).fetchone()
    conn.close()
    if not row or not row["location"]:
        return catalog
    try:
        sheets = parse_sheets(Path(row["location"]).read_bytes(), row["name"])
    except Exception:
        return catalog

    for records in sheets.values():
        if not records:
            continue
        headers = list(records[0].keys())
        name_col = _find_col(headers, "name", "element", "item", "zone", "label")
        kind_col = _find_col(headers, "kind", "category", "type", "role")
        w_col = _find_col(headers, "width", "w", "size_x")
        d_col = _find_col(headers, "depth", "length", "d", "size_y")
        h_col = _find_col(headers, "height", "tall", "h", "size_z")
        for rec in records:
            kind_text = (rec.get(kind_col, "") if kind_col else "") or (
                rec.get(name_col, "") if name_col else ""
            )
            w = _to_float(rec.get(w_col)) if w_col else None
            d = _to_float(rec.get(d_col)) if d_col else None
            h = _to_float(rec.get(h_col)) if h_col else None

            # Booth meta row: an explicit booth type + footprint.
            type_val = str(rec.get(kind_col, "")).lower() if kind_col else ""
            if type_val in OPEN_BY_TYPE and w and d and not catalog["booth_meta"]:
                catalog["booth_meta"] = {"width": w, "depth": d, "type": type_val}
                continue

            kind = _canon_kind(kind_text)
            if kind and (w or d) and kind not in catalog["by_kind"]:
                base = ZONE_KINDS.get(kind, {})
                catalog["by_kind"][kind] = {
                    "w": w or base.get("w", 2.0),
                    "d": d or base.get("d", 1.5),
                    "height": h or base.get("height", 1.2),
                }
    return catalog


# --------------------------------------------------------------------------- #
# 1 · Synthesise — natural language → functional program
# --------------------------------------------------------------------------- #
def _parse_dims(text: str) -> tuple[float, float] | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*m?\s*(?:x|×|by)\s*(\d+(?:\.\d+)?)", text.lower())
    return (float(m.group(1)), float(m.group(2))) if m else None


def _parse_type(text: str) -> str | None:
    t = text.lower()
    for bt in ("peninsula", "island", "corner", "inline"):
        if bt in t:
            return bt
    return None


# Number prefix: digits or a spelled-out number word, longest words first.
_NUM = r"\d+|" + "|".join(
    sorted((w for w in NUMBER_WORDS), key=len, reverse=True)
)


def _extract_zones(text: str) -> list[dict]:
    """Pull (kind, count) requests out of a sentence using the synonym table.
    A number immediately before a zone word sets its count (default 1)."""
    t = text.lower()
    out: list[dict] = []
    seen: set[str] = set()
    for kind, words in KIND_SYNONYMS:
        if kind in seen:
            continue
        for w in words:
            m = re.search(r"(" + _NUM + r")?\s*" + re.escape(w), t)
            if not m:
                continue
            prefix = (m.group(1) or "").strip()
            if prefix.isdigit():
                count = int(prefix)
            else:
                count = NUMBER_WORDS.get(prefix, 1)
            out.append({"kind": kind, "count": count})
            seen.add(kind)
            break
    return out


def _normalise_program(program: dict, catalog: dict) -> dict:
    booth = program.get("booth") or {}
    booth.setdefault("width", 6.0)
    booth.setdefault("depth", 4.0)
    booth.setdefault("type", "inline")
    program["booth"] = booth
    zones = []
    for z in program.get("zones") or []:
        kind = str(z.get("kind") or z.get("name") or "").lower()
        kind = _canon_kind(kind) or (kind if kind in ZONE_KINDS else "display")
        entry = {
            "kind": kind,
            "name": z.get("name") or kind.title(),
            "count": max(1, int(z.get("count", 1) or 1)),
            "priority": int(z.get("priority", PRIORITY.get(kind, 2)) or PRIORITY.get(kind, 2)),
        }
        cat = catalog["by_kind"].get(kind)
        if cat:  # size from the uploaded catalog when available
            entry.update({"w": cat["w"], "d": cat["d"], "height": cat["height"]})
        for dim in ("w", "d", "width", "depth", "height"):
            if z.get(dim) is not None:
                entry[dim] = float(z[dim])
        zones.append(entry)
    program["zones"] = zones or [dict(z) for z in DEFAULT_ZONES]
    return program


def _keyword_program(message: str, prev: dict | None, catalog: dict) -> dict:
    dims = _parse_dims(message)
    btype = _parse_type(message)
    mentioned = _extract_zones(message)
    msg = message.lower()
    is_edit = prev is not None and bool(
        re.search(r"\b(add|another|more|also|remove|delete|drop|without|move|swap)\b", msg)
    )

    if is_edit:
        program = deepcopy(prev)
        if dims:
            program["booth"]["width"], program["booth"]["depth"] = dims
        if btype:
            program["booth"]["type"] = btype
        if re.search(r"\b(add|another|more|also)\b", msg):
            for z in mentioned:
                program["zones"].append(z)
        if re.search(r"\b(remove|delete|drop|without)\b", msg):
            drop = {z["kind"] for z in mentioned}
            program["zones"] = [z for z in program["zones"] if z["kind"] not in drop] or program["zones"]
        if "move" in msg:
            to_back = "back" in msg or "rear" in msg
            for z in program["zones"]:
                if z["kind"] in {m["kind"] for m in mentioned}:
                    z["priority"] = 1 if to_back else 5
    else:
        booth = {
            "width": dims[0] if dims else (prev or {}).get("booth", {}).get("width", 6.0),
            "depth": dims[1] if dims else (prev or {}).get("booth", {}).get("depth", 4.0),
            "type": btype or (prev or {}).get("booth", {}).get("type", "inline"),
        }
        zones = mentioned or (prev or {}).get("zones") or DEFAULT_ZONES
        program = {"booth": booth, "zones": [dict(z) for z in zones], "constraints": {}}

    if catalog.get("booth_meta") and not dims and not (prev and prev.get("booth")):
        program["booth"].update(catalog["booth_meta"])
    return _normalise_program(program, catalog)


def _llm_program(provider: LLMProvider, message: str, history: list[dict], catalog: dict) -> dict | None:
    kinds = ", ".join(sorted(ZONE_KINDS))
    sizes = json.dumps(catalog["by_kind"]) if catalog["by_kind"] else "(none provided)"
    system = (
        "You convert a trade-show exhibitor's request into a strict JSON booth program. "
        "Reply with ONLY one fenced ```program {JSON}``` block, no prose. Schema:\n"
        '{"booth":{"width":<m>,"depth":<m>,"type":"inline|corner|peninsula|island"},'
        '"zones":[{"name":"...","kind":"<one of: ' + kinds + '>","count":<int>,'
        '"priority":<1-5>}],"constraints":{"aisle_width":<m>,"max_height":<m>}}\n'
        f"Available element sizes from the catalog: {sizes}\n"
        "Infer sensible booth size/type and zones from the request and prior layout."
    )
    msgs = [{"role": m["role"], "content": m["content"]} for m in history]
    msgs.append({"role": "user", "content": message})
    try:
        reply = provider.complete(system, msgs)
    except Exception:
        return None
    match = PROGRAM_RE.search(reply)
    if not match:
        return None
    try:
        program = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(program, dict) or "zones" not in program:
        return None
    return _normalise_program(program, catalog)


def synthesise(
    provider: LLMProvider | None,
    message: str,
    history: list[dict],
    prev_program: dict | None,
    catalog: dict,
) -> dict:
    if provider is not None:
        program = _llm_program(provider, message, history, catalog)
        if program is not None:
            return program
    return _keyword_program(message, prev_program, catalog)


# --------------------------------------------------------------------------- #
# 7 · Explain
# --------------------------------------------------------------------------- #
def _template_explain(program: dict, result: dict) -> str:
    canvas = result["canvas"]
    placed = result["layout"]["placed"]
    report = result["validation"]
    names = ", ".join(p["name"] for p in placed) or "no zones"
    coverage = int(report.get("coverage", 0) * 100)
    failed = [c for c in report["checks"] if not c["ok"]]
    status = (
        "All compliance checks pass"
        + (f" (after {result['repairs']} repair{'s' if result['repairs'] != 1 else ''})"
           if result["repairs"] else "")
        if report["ok"]
        else "Some checks still fail: "
        + "; ".join(f"{c['name']} — {c['detail']}" for c in failed)
    )
    return (
        f"Here's a {canvas['type']} booth at {canvas['width']:g}×{canvas['depth']:g} m. "
        f"I placed {len(placed)} zone(s): {names}. The plan uses {coverage}% of the floor "
        f"with clear circulation aisles. {status}.\n\n"
        "Tell me what to change — e.g. “add a demo station”, "
        "“move the meeting room to the back”, or “make it an 8×6 island”."
    )


def explain(provider: LLMProvider | None, program: dict, result: dict) -> str:
    if provider is None:
        return _template_explain(program, result)
    report = result["validation"]
    summary = {
        "booth": result["canvas"],
        "zones": [
            {"name": p["name"], "x": p["x"], "y": p["y"], "w": p["w"], "d": p["d"]}
            for p in result["layout"]["placed"]
        ],
        "checks": report["checks"],
        "repairs": result["repairs"],
    }
    system = (
        "You are an InShow booth-design assistant. In 2-4 short sentences, explain the "
        "layout to the exhibitor: what's placed and why, that it meets aisle/egress and "
        "fit rules, and invite a refinement. Do not output JSON or code blocks."
    )
    try:
        return provider.complete(
            system, [{"role": "user", "content": json.dumps(summary)}]
        )
    except Exception:
        return _template_explain(program, result)


# --------------------------------------------------------------------------- #
# Entry point used by the chat router
# --------------------------------------------------------------------------- #
def has_api_key(config: dict) -> bool:
    return bool(config.get("api_key")) or bool(
        os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    )


def run(
    provider: LLMProvider | None,
    data_source_id: int | None,
    message: str,
    history: list[dict],
    prev_program: dict | None,
) -> dict:
    catalog = read_catalog(data_source_id)
    program = synthesise(provider, message, history, prev_program, catalog)
    result = plan_layout(program)
    artifact = to_artifact(program, result)
    content = explain(provider, program, result)
    return {"content": content, "artifact": artifact, "program": program}
