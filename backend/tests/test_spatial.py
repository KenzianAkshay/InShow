"""Tests for the deterministic booth spatial engine (app/spatial.py)."""

from app.spatial import (
    load_canvas,
    plan_layout,
    to_artifact,
    validate,
)


def _program(width=6.0, depth=4.0, btype="corner", zones=None):
    return {
        "booth": {"width": width, "depth": depth, "type": btype},
        "zones": zones
        or [
            {"kind": "reception"},
            {"kind": "demo", "count": 2},
            {"kind": "meeting"},
            {"kind": "storage"},
        ],
    }


def _overlap(zs):
    total = 0.0
    for i in range(len(zs)):
        for j in range(i + 1, len(zs)):
            a, b = zs[i], zs[j]
            dx = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            dy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            total += max(0.0, dx) * max(0.0, dy)
    return total


def test_load_canvas_defaults_open_sides():
    canvas = load_canvas({"booth": {"width": 8, "depth": 6, "type": "island"}})
    assert canvas["width"] == 8 and canvas["depth"] == 6
    assert canvas["type"] == "island"
    assert set(canvas["open_sides"]) == {"front", "back", "left", "right"}


def test_unknown_type_falls_back_to_inline():
    canvas = load_canvas({"booth": {"width": 3, "depth": 3, "type": "spaceship"}})
    assert canvas["type"] == "inline"
    assert canvas["open_sides"] == ["front"]


def test_solve_places_all_zones_valid_and_non_overlapping():
    art = to_artifact(_program(), plan_layout(_program()))
    assert len(art["zones"]) == 5  # reception + 2 demo + meeting + storage
    assert art["validation"]["ok"] is True
    assert _overlap(art["zones"]) < 1e-6
    for z in art["zones"]:
        assert z["x"] >= -1e-6 and z["y"] >= -1e-6
        assert z["x"] + z["w"] <= art["booth"]["width"] + 1e-6
        assert z["y"] + z["h"] <= art["booth"]["depth"] + 1e-6


def test_layout_is_deterministic():
    a = to_artifact(_program(), plan_layout(_program()))
    b = to_artifact(_program(), plan_layout(_program()))
    assert a == b


def test_validate_flags_overlap():
    canvas = {"width": 6, "depth": 4, "type": "inline", "open_sides": ["front"]}
    cons = {"aisle": 1.0, "setback": 0.3, "gap": 0.3, "row_gap": 0.4,
            "max_height": 4.0, "max_coverage": 0.7}
    layout = {
        "placed": [
            {"name": "A", "x": 1.0, "y": 1.5, "w": 2.0, "d": 1.0, "height": 1.0},
            {"name": "B", "x": 2.0, "y": 1.5, "w": 2.0, "d": 1.0, "height": 1.0},
        ],
        "unplaced": [],
        "front_strip": {"x": 0.3, "y": 0.3, "w": 5.4, "d": 1.0},
    }
    report = validate(canvas, layout, cons)
    checks = {c["name"]: c["ok"] for c in report["checks"]}
    assert checks["no_overlap"] is False
    assert report["ok"] is False


def test_validate_flags_out_of_bounds():
    canvas = {"width": 6, "depth": 4, "type": "inline", "open_sides": ["front"]}
    cons = {"aisle": 1.0, "setback": 0.3, "gap": 0.3, "row_gap": 0.4,
            "max_height": 4.0, "max_coverage": 0.7}
    layout = {
        "placed": [{"name": "X", "x": 5.0, "y": 1.5, "w": 3.0, "d": 1.0, "height": 1.0}],
        "unplaced": [],
        "front_strip": {"x": 0.3, "y": 0.3, "w": 5.4, "d": 1.0},
    }
    checks = {c["name"]: c["ok"] for c in validate(canvas, layout, cons)["checks"]}
    assert checks["in_bounds"] is False


def test_repair_drops_zones_for_an_overfull_booth():
    # A 3×3 booth cannot hold five zones; the engine must still return a valid
    # layout, having dropped the lowest-priority zones.
    prog = _program(width=3, depth=3, btype="inline")
    result = plan_layout(prog)
    art = to_artifact(prog, result)
    assert art["validation"]["ok"] is True
    assert len(art["zones"]) < 5
    assert result["repairs"] >= 1


def test_to_artifact_shape():
    art = to_artifact(_program(), plan_layout(_program()))
    assert art["type"] == "booth_layout"
    assert art["units"] == "m"
    assert set(art["booth"]) == {"width", "depth", "type", "open_sides"}
    z = art["zones"][0]
    assert set(z) >= {"id", "name", "kind", "x", "y", "w", "h", "height", "color"}
    assert "checks" in art["validation"]
