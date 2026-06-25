"""Deterministic spatial layout engine for trade-show booths.

This is the geometry half of the Booth Layout Planning Pipeline: it takes a
structured "functional program" (booth footprint + desired zones + constraints)
and produces a validated 2D placement of zones, repairing infeasible layouts so
only valid ones ever surface.

Everything here is pure and deterministic — no randomness, no IO, no LLM — so a
given program always yields the same layout and the whole module is unit
testable. Units are metres throughout. The coordinate origin (0, 0) is the
front-left corner: x grows to the right (booth width), y grows toward the back
(booth depth); the booth front (y = 0) faces the main aisle.
"""

from __future__ import annotations

import math
from copy import deepcopy

GRID = 0.25  # snap resolution (m)
EPS = 1e-6
MIN_DIM = 0.8  # a zone is never shrunk below this (m)
FILL = 0.72  # scale zones so they occupy at most this fraction of packable area

# Per-kind defaults: footprint (w × d), structure height, whether the zone wants
# to sit near the open frontage, and a render colour. Catalog data overrides the
# footprint/height when available; everything falls back to DEFAULT_KIND.
ZONE_KINDS: dict[str, dict] = {
    "reception": {"w": 2.5, "d": 1.5, "height": 1.1, "front": True, "color": "#ff7a59"},
    "demo": {"w": 1.5, "d": 1.0, "height": 1.2, "front": True, "color": "#2bc6df"},
    "meeting": {"w": 2.5, "d": 2.0, "height": 2.4, "front": False, "color": "#a78bfa"},
    "display": {"w": 1.0, "d": 0.5, "height": 2.0, "front": False, "color": "#4f8cff"},
    "storage": {"w": 1.5, "d": 1.2, "height": 2.4, "front": False, "color": "#7c93c9"},
    "lounge": {"w": 2.0, "d": 2.0, "height": 0.8, "front": False, "color": "#2bd4a8"},
    "cafe": {"w": 1.5, "d": 1.0, "height": 1.1, "front": True, "color": "#f0c419"},
    "counter": {"w": 1.5, "d": 0.8, "height": 1.1, "front": True, "color": "#f0c419"},
    "info": {"w": 1.2, "d": 0.8, "height": 1.1, "front": True, "color": "#46c79a"},
    "product": {"w": 1.0, "d": 1.0, "height": 1.5, "front": False, "color": "#e86fae"},
}
DEFAULT_KIND = {"w": 1.5, "d": 1.0, "height": 1.2, "front": False, "color": "#7c93c9"}

# Which edges face an aisle for each booth type (front = the y=0 edge).
OPEN_BY_TYPE = {
    "inline": ["front"],
    "corner": ["front", "right"],
    "peninsula": ["front", "left", "right"],
    "island": ["front", "back", "left", "right"],
}
MAX_HEIGHT_BY_TYPE = {"inline": 2.5, "corner": 2.5, "peninsula": 4.0, "island": 6.0}


def _snap(v: float) -> float:
    return round(v / GRID) * GRID


def _overlap_area(a: dict, b: dict) -> float:
    dx = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    dy = min(a["y"] + a["d"], b["y"] + b["d"]) - max(a["y"], b["y"])
    return max(0.0, dx) * max(0.0, dy)


# --------------------------------------------------------------------------- #
# 2 · Load canvas
# --------------------------------------------------------------------------- #
def load_canvas(program: dict) -> dict:
    booth = program.get("booth", {})
    width = max(1.0, float(booth.get("width") or 6.0))
    depth = max(1.0, float(booth.get("depth") or 4.0))
    btype = str(booth.get("type") or "inline").lower()
    if btype not in OPEN_BY_TYPE:
        btype = "inline"
    open_sides = booth.get("open_sides") or OPEN_BY_TYPE[btype]
    return {
        "width": round(width, 2),
        "depth": round(depth, 2),
        "type": btype,
        "open_sides": list(open_sides),
    }


# --------------------------------------------------------------------------- #
# 3 · Constraints
# --------------------------------------------------------------------------- #
def derive_constraints(program: dict, canvas: dict) -> dict:
    c = program.get("constraints") or {}
    return {
        "aisle": float(c.get("aisle_width", 1.0)),
        "setback": float(c.get("perimeter_setback", 0.3)),
        "gap": float(c.get("zone_gap", 0.3)),
        "row_gap": float(c.get("row_gap", 0.4)),  # corridor between rows
        "max_height": float(
            c.get("max_height", MAX_HEIGHT_BY_TYPE.get(canvas["type"], 4.0))
        ),
        "max_coverage": float(c.get("max_coverage", 0.7)),
    }


# --------------------------------------------------------------------------- #
# Expand the requested zones into concrete, sized rectangles
# --------------------------------------------------------------------------- #
def expand_zones(program: dict) -> list[dict]:
    """Flatten program zones into individually-sized placement requests, applying
    per-kind defaults where dimensions are missing and fanning out `count`."""
    out: list[dict] = []
    for spec in program.get("zones", []):
        kind = str(spec.get("kind") or spec.get("name") or "zone").lower()
        base = ZONE_KINDS.get(kind, DEFAULT_KIND)
        count = max(1, int(spec.get("count", 1) or 1))
        w = float(spec.get("w") or spec.get("width") or base["w"])
        d = float(spec.get("d") or spec.get("depth") or base["d"])
        height = float(spec.get("height") or base["height"])
        priority = int(spec.get("priority", 0) or 0)
        label = spec.get("name") or kind.title()
        for i in range(count):
            name = label if count == 1 else f"{label} {i + 1}"
            out.append(
                {
                    "id": f"{kind}-{len(out)}",
                    "name": name,
                    "kind": kind,
                    "w": round(w, 2),
                    "d": round(d, 2),
                    "height": height,
                    "priority": priority,
                    "front": bool(base.get("front")),
                    "color": base.get("color", DEFAULT_KIND["color"]),
                }
            )
    return out


# --------------------------------------------------------------------------- #
# 4 · Solve layout
# --------------------------------------------------------------------------- #
def _pack_region(canvas: dict, cons: dict) -> tuple[dict, dict]:
    """The packable rectangle plus the front entrance strip kept clear for
    egress. Zones pack behind the strip; the strip + coverage headroom provide
    circulation."""
    s, aisle = cons["setback"], cons["aisle"]
    w, d = canvas["width"], canvas["depth"]
    x0, y0, x1, y1 = s, s, w - s, d - s
    front_strip = {"x": x0, "y": y0, "w": max(0.0, x1 - x0), "d": min(aisle, max(0.0, y1 - y0))}
    pack = {"x0": x0, "y0": y0 + front_strip["d"], "x1": x1, "y1": y1}
    return pack, front_strip


def _scale_to_fit(zones: list[dict], pack: dict) -> list[dict]:
    """Deterministically shrink zones proportionally so their combined area fits
    within FILL of the packable region, and clamp any single zone to the region.
    This is the bulk of the 'solve' work; repair handles residual cases."""
    pack_w = max(EPS, pack["x1"] - pack["x0"])
    pack_d = max(EPS, pack["y1"] - pack["y0"])
    total = sum(z["w"] * z["d"] for z in zones)
    target = pack_w * pack_d * FILL
    f = math.sqrt(target / total) if total > target and total > 0 else 1.0
    out = []
    for z in zones:
        w = min(pack_w, max(MIN_DIM, z["w"] * f))
        d = min(pack_d, max(MIN_DIM, z["d"] * f))
        out.append({**z, "w": round(w, 2), "d": round(d, 2)})
    return out


def _shelf_pack(zones: list[dict], pack: dict, cons: dict) -> tuple[list[dict], list[dict]]:
    """Row/shelf packing: fill rows left→right, stacking toward the back with a
    walkable corridor between rows. Rotates a zone if that lets it fit the
    remaining row width. Returns (placed, unplaced)."""
    gap, row_gap = cons["gap"], cons["row_gap"]
    pack_w = pack["x1"] - pack["x0"]
    placed: list[dict] = []
    unplaced: list[dict] = []
    cx, cy, row_d = pack["x0"], pack["y0"], 0.0

    for z in zones:
        w, d = z["w"], z["d"]
        if w > (pack["x1"] - cx) + EPS and d <= (pack["x1"] - cx) + EPS:
            w, d = d, w  # rotate to fit remaining row width
        if cx + w > pack["x1"] + EPS:  # wrap to a new row
            cx, cy, row_d = pack["x0"], cy + row_d + row_gap, 0.0
            w, d = z["w"], z["d"]
            if w > pack_w + EPS and d <= pack_w + EPS:
                w, d = d, w
        if cx + w > pack["x1"] + EPS or cy + d > pack["y1"] + EPS:
            unplaced.append(z)
            continue
        # Snap for tidy coordinates, then clamp inside the packable region so a
        # snapped sliver never breaches the front strip or the booth edge.
        px = min(max(pack["x0"], _snap(cx)), pack["x1"] - w)
        py = min(max(pack["y0"], _snap(cy)), pack["y1"] - d)
        placed.append({**z, "x": round(px, 2), "y": round(py, 2), "w": round(w, 2), "d": round(d, 2)})
        cx = cx + w + gap
        row_d = max(row_d, d)
    return placed, unplaced


def _order(zones: list[dict], strategy: str) -> list[dict]:
    if strategy == "priority":
        key = lambda z: (-z["priority"], -(z["w"] * z["d"]), z["id"])
    elif strategy == "frontage":
        key = lambda z: (0 if z["front"] else 1, -z["priority"], -(z["w"] * z["d"]), z["id"])
    else:  # area
        key = lambda z: (-(z["w"] * z["d"]), z["id"])
    return sorted(zones, key=key)


def _best_pack(zones: list[dict], pack: dict, cons: dict) -> dict:
    """Try each ordering, keep the one that places the most zones most compactly."""
    best: dict | None = None
    for strategy in ("frontage", "priority", "area"):
        placed, unplaced = _shelf_pack(_order(zones, strategy), pack, cons)
        used_depth = max((p["y"] + p["d"] for p in placed), default=pack["y0"])
        score = (len(placed), -used_depth)
        if best is None or score > best["score"]:
            best = {"score": score, "placed": placed, "unplaced": unplaced, "strategy": strategy}
    assert best is not None
    return best


def solve(canvas: dict, zones: list[dict], cons: dict) -> dict:
    """Scale zones to fit, pack, and — if anything is left over — shrink uniformly
    and re-pack until everything fits (or zones hit the minimum size). This keeps
    `solve` self-contained and deterministic; the candidate orderings, shrink
    factor and tie-breaks are all fixed, so identical inputs give identical
    layouts. The outer `repair` loop then only handles coverage/drop cases."""
    pack, front_strip = _pack_region(canvas, cons)
    work = _scale_to_fit(zones, pack)
    best = _best_pack(work, pack, cons)
    tries = 0
    while best["unplaced"] and tries < 16:
        if all(min(z["w"], z["d"]) <= MIN_DIM + EPS for z in work):
            break
        work = [
            {**z, "w": round(max(MIN_DIM, z["w"] * 0.9), 2), "d": round(max(MIN_DIM, z["d"] * 0.9), 2)}
            for z in work
        ]
        best = _best_pack(work, pack, cons)
        tries += 1
    return {
        "placed": best["placed"],
        "unplaced": [u["name"] for u in best["unplaced"]],
        "front_strip": front_strip,
        "strategy": best["strategy"],
    }


# --------------------------------------------------------------------------- #
# 5 · Validate
# --------------------------------------------------------------------------- #
def validate(canvas: dict, layout: dict, cons: dict) -> dict:
    placed = layout["placed"]
    w, d = canvas["width"], canvas["depth"]
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("all_placed", not layout["unplaced"],
        "" if not layout["unplaced"] else f"unplaced: {', '.join(layout['unplaced'])}")

    in_bounds = all(
        p["x"] >= -EPS and p["y"] >= -EPS
        and p["x"] + p["w"] <= w + EPS and p["y"] + p["d"] <= d + EPS
        for p in placed
    )
    add("in_bounds", in_bounds, "" if in_bounds else "a zone extends past the booth edge")

    overlap = 0.0
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            overlap += _overlap_area(placed[i], placed[j])
    add("no_overlap", overlap <= EPS,
        "" if overlap <= EPS else f"{overlap:.2f} m² of overlap")

    # Egress: the front entrance strip must stay clear so visitors can enter and
    # reach the circulation behind it.
    entrance_clear = all(
        _overlap_area(p, layout["front_strip"]) <= EPS for p in placed
    )
    add("egress", entrance_clear,
        f"entrance aisle ≥ {cons['aisle']:g} m clear"
        if entrance_clear else "entrance aisle is obstructed")

    booth_area = w * d
    used = sum(p["w"] * p["d"] for p in placed)
    coverage = used / booth_area if booth_area else 0.0
    add("coverage", coverage <= cons["max_coverage"] + EPS,
        f"{coverage * 100:.0f}% of floor used (max {cons['max_coverage'] * 100:.0f}%)")

    tall = [p["name"] for p in placed if p.get("height", 0) > cons["max_height"] + EPS]
    add("height", not tall,
        "" if not tall else f"too tall: {', '.join(tall)} (max {cons['max_height']:g} m)")

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks, "coverage": round(coverage, 3)}


# --------------------------------------------------------------------------- #
# Repair (the 5 → 4 loop)
# --------------------------------------------------------------------------- #
def repair(zones: list[dict], cons: dict, report: dict, layout: dict) -> tuple[list[dict], dict, bool]:
    """Adjust inputs so the next solve has a better chance. `solve` already shrinks
    to fit as much as possible, so when zones remain unplaced the booth is simply
    too full: drop the lowest-priority unplaced zone. Over-coverage is eased by a
    uniform shrink. Returns (zones, constraints, changed)."""
    zones = deepcopy(zones)
    cons = dict(cons)
    failed = {c["name"] for c in report["checks"] if not c["ok"]}

    if "all_placed" in failed and len(zones) > 1:
        unplaced = set(layout.get("unplaced", []))
        pool = [z for z in zones if z["name"] in unplaced] or zones
        victim = min(pool, key=lambda z: (z["priority"], -(z["w"] * z["d"]), z["id"]))
        return [z for z in zones if z["id"] != victim["id"]], cons, True

    if failed & {"coverage", "in_bounds", "no_overlap"}:
        shrinkable = any(min(z["w"], z["d"]) > MIN_DIM + EPS for z in zones)
        if shrinkable:
            for z in zones:
                z["w"] = round(max(MIN_DIM, z["w"] * 0.88), 2)
                z["d"] = round(max(MIN_DIM, z["d"] * 0.88), 2)
            return zones, cons, True

    return zones, cons, False


# --------------------------------------------------------------------------- #
# Orchestration: solve → validate → repair (only valid layouts surface)
# --------------------------------------------------------------------------- #
def plan_layout(program: dict, max_repairs: int = 5) -> dict:
    canvas = load_canvas(program)
    cons = derive_constraints(program, canvas)
    zones = expand_zones(program)

    repairs = 0
    layout = solve(canvas, zones, cons)
    report = validate(canvas, layout, cons)
    while not report["ok"] and repairs < max_repairs:
        zones, cons, changed = repair(zones, cons, report, layout)
        if not changed:
            break
        repairs += 1
        layout = solve(canvas, zones, cons)
        report = validate(canvas, layout, cons)

    return {
        "canvas": canvas,
        "constraints": cons,
        "layout": layout,
        "validation": report,
        "repairs": repairs,
    }


# --------------------------------------------------------------------------- #
# 6 · Render → artifact consumed by the frontend Canvas
# --------------------------------------------------------------------------- #
def to_artifact(program: dict, result: dict) -> dict:
    canvas = result["canvas"]
    layout = result["layout"]
    report = result["validation"]
    btype = canvas["type"].title()
    title = program.get("title") or (
        f"{btype} booth · {canvas['width']:g}×{canvas['depth']:g} m"
    )
    zones = [
        {
            "id": p["id"],
            "name": p["name"],
            "kind": p["kind"],
            "x": p["x"],
            "y": p["y"],
            "w": p["w"],
            "h": p["d"],
            "height": p.get("height", 1.2),
            "color": p.get("color", DEFAULT_KIND["color"]),
        }
        for p in layout["placed"]
    ]
    fs = layout["front_strip"]
    aisles = (
        [{"x": fs["x"], "y": fs["y"], "w": fs["w"], "h": fs["d"]}]
        if fs["w"] > EPS and fs["d"] > EPS
        else []
    )
    return {
        "type": "booth_layout",
        "title": title,
        "units": "m",
        "booth": {
            "width": canvas["width"],
            "depth": canvas["depth"],
            "type": canvas["type"],
            "open_sides": canvas["open_sides"],
        },
        "zones": zones,
        "aisles": aisles,
        "validation": {
            "ok": report["ok"],
            "repaired": result["repairs"],
            "checks": report["checks"],
        },
    }
