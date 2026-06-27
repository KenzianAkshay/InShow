"""Deterministic analytics over a project's ontology graph.

Two roles:
  1. The implementations behind the agent's `query_ontology` and `calculate`
     tools (exact aggregation + arithmetic — the model never does math itself).
  2. A keyword-driven fallback (`deterministic_analytics`) that turns a chart /
     aggregation request into a canvas artifact without any LLM, so the feature
     works even when no model API key is configured.
"""

import ast
import operator
import re

INTERNAL = {"uid", "project_id", "source_id", "ingested_at"}


def _to_float(value) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# --- Aggregations over the ontology graph -----------------------------------

def class_counts(driver, project_id: int) -> list[dict]:
    """Number of entities per class. Good for an overview bar chart."""
    with driver.session() as session:
        return [
            {"label": r["label"], "value": r["value"]}
            for r in session.run(
                "MATCH (e:Entity {project_id: $pid}) "
                "WITH [l IN labels(e) WHERE l <> 'Entity'][0] AS label "
                "RETURN label, count(*) AS value ORDER BY value DESC, label",
                pid=project_id,
            )
            if r["label"]
        ]


def count_by_dimension(
    driver, project_id: int, source_label: str | None, dimension_label: str | None
) -> list[dict]:
    """Count entities grouped by a connected dimension value (e.g. exhibitors by
    city). If source_label is omitted, counts every entity linked to the
    dimension."""
    if not dimension_label:
        return []
    with driver.session() as session:
        if source_label:
            rows = session.run(
                "MATCH (src:Entity {project_id: $pid})-[]->(d:Entity {project_id: $pid}) "
                "WHERE $src IN labels(src) AND $dim IN labels(d) "
                "RETURN coalesce(d.value, d.uid) AS label, count(DISTINCT src) AS value "
                "ORDER BY value DESC, label",
                pid=project_id, src=source_label, dim=dimension_label,
            )
        else:
            rows = session.run(
                "MATCH (x:Entity {project_id: $pid})-[]->(d:Entity {project_id: $pid}) "
                "WHERE $dim IN labels(d) "
                "RETURN coalesce(d.value, d.uid) AS label, count(DISTINCT x) AS value "
                "ORDER BY value DESC, label",
                pid=project_id, dim=dimension_label,
            )
        return [{"label": str(r["label"]), "value": r["value"]} for r in rows]


def count_class(driver, project_id: int, label: str | None) -> int:
    if not label:
        return 0
    with driver.session() as session:
        for r in session.run(
            "MATCH (e:Entity {project_id: $pid}) WHERE $label IN labels(e) "
            "RETURN count(e) AS value",
            pid=project_id, label=label,
        ):
            return r["value"]
    return 0


def numeric_properties(driver, project_id: int, label: str | None) -> dict[str, list[float]]:
    """Collect the numeric property values of a class, keyed by property name."""
    agg: dict[str, list[float]] = {}
    if not label:
        return agg
    with driver.session() as session:
        for r in session.run(
            "MATCH (e:Entity {project_id: $pid}) WHERE $label IN labels(e) "
            "RETURN properties(e) AS props LIMIT 2000",
            pid=project_id, label=label,
        ):
            for k, v in (r["props"] or {}).items():
                if k in INTERNAL:
                    continue
                f = _to_float(v)
                if f is not None:
                    agg.setdefault(k, []).append(f)
    return agg


def numeric_stats(
    driver, project_id: int, label: str | None, prop: str | None, op: str
) -> float:
    vals = numeric_properties(driver, project_id, label).get(prop or "", [])
    if not vals:
        return 0
    if op == "sum":
        r = sum(vals)
    elif op in ("average", "avg", "mean"):
        r = sum(vals) / len(vals)
    elif op == "min":
        r = min(vals)
    elif op == "max":
        r = max(vals)
    else:
        r = len(vals)
    return round(r, 4)


# --- Exact arithmetic (no LLM math) -----------------------------------------

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_FUNCS = {"round": round, "abs": abs, "min": min, "max": max}


def safe_calculate(expression: str):
    """Evaluate a pure arithmetic expression safely (no names, attribute access,
    or arbitrary calls — only numbers, + - * / ** % //, and a few math helpers)."""
    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return +v if isinstance(node.op, ast.UAdd) else -v
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FUNCS
            and not node.keywords
        ):
            return _FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError("unsupported expression")

    tree = ast.parse(expression, mode="eval")
    return ev(tree.body)


# --- Tool specs + dispatch (used by the agentic loop) -----------------------

TOOLS = [
    {
        "name": "query_ontology",
        "description": (
            "Query exact aggregations over THIS project's ontology data. "
            "operation=class_counts (entities per class), "
            "count_by_dimension (group a source class by a connected dimension "
            "class, e.g. source_label=Exhibitors dimension_label=City), "
            "count_class (total entities of a class), or "
            "numeric_stats (sum/average/min/max of a numeric property of a class). "
            "Use this to gather numbers for answers and charts."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": [
                        "class_counts",
                        "count_by_dimension",
                        "count_class",
                        "numeric_stats",
                    ],
                },
                "source_label": {"type": "string"},
                "dimension_label": {"type": "string"},
                "label": {"type": "string"},
                "property": {"type": "string"},
                "op": {
                    "type": "string",
                    "enum": ["sum", "average", "min", "max", "count"],
                },
            },
            "required": ["operation"],
        },
    },
    {
        "name": "calculate",
        "description": (
            "Evaluate an arithmetic expression exactly (e.g. '4200*0.15' or "
            "'(5+3+2)/3'). Use this for ALL math instead of computing in your head."
        ),
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
]


def make_dispatch(driver, project_id: int):
    """Return a dispatch(name, args) -> dict the LLM tool loop calls."""

    def dispatch(name: str, args: dict) -> dict:
        try:
            if name == "calculate":
                return {"result": safe_calculate(str(args.get("expression", "")))}
            if name == "query_ontology":
                op = args.get("operation")
                if op == "class_counts":
                    return {"data": class_counts(driver, project_id)}
                if op == "count_by_dimension":
                    return {
                        "data": count_by_dimension(
                            driver,
                            project_id,
                            args.get("source_label"),
                            args.get("dimension_label"),
                        )
                    }
                if op == "count_class":
                    return {"value": count_class(driver, project_id, args.get("label"))}
                if op == "numeric_stats":
                    return {
                        "value": numeric_stats(
                            driver,
                            project_id,
                            args.get("label"),
                            args.get("property"),
                            args.get("op", "sum"),
                        )
                    }
                return {"error": f"unknown operation: {op}"}
            return {"error": f"unknown tool: {name}"}
        except Exception as exc:  # surface the error to the model, never crash
            return {"error": str(exc)}

    return dispatch


# --- Artifact builders -------------------------------------------------------

def bar_artifact(title: str, data: list[dict]) -> dict:
    return {"type": "bar", "title": title, "data": data[:20]}


def metrics_artifact(title: str, items: list[dict]) -> dict:
    return {"type": "metrics", "title": title, "items": items}


# --- Deterministic fallback (no LLM) ----------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[\s_]+", "", s.lower())


def _mentions(name: str, lower: str) -> bool:
    return name.lower() in lower or _norm(name) in _norm(lower)


def deterministic_analytics(driver, project_id: int, query: str) -> dict | None:
    """Best-effort: turn a chart/aggregation request into a canvas artifact with
    no LLM. Returns {content, artifact} or None when no analytic intent matches."""
    classes = [c["label"] for c in class_counts(driver, project_id)]
    if not classes:
        return None
    lower = f" {query.lower()} "

    present = sorted(
        ((lower.find(c.lower()), c) for c in classes if _mentions(c, lower)),
        key=lambda t: (t[0] < 0, t[0]),
    )
    present = [(i, c) for i, c in present if i >= 0]

    wants_stat = any(
        k in lower for k in ["average", " avg", "mean", "sum", "minimum", "maximum", " min ", " max "]
    )
    wants_count = any(k in lower for k in ["how many", "number of", "count of", " count ", "total number"])
    wants_chart = any(
        k in lower
        for k in ["chart", "plot", "graph", "visual", "distribution", "breakdown", " by ", " per ", "group"]
    )

    # group-by: "<source> by <dimension>"
    byidx = max(lower.find(" by "), lower.find(" per "), lower.find(" across "))
    if byidx >= 0 and present:
        after = [c for i, c in present if i > byidx]
        before = [c for i, c in present if i < byidx]
        dim = after[0] if after else present[-1][1]
        src = before[-1] if before else None
        data = count_by_dimension(driver, project_id, src, dim)
        if data:
            title = f"{src or 'Records'} by {dim}"
            return {
                "content": f"{title}: " + ", ".join(f"{d['label']} ({d['value']})" for d in data[:8]) + ".",
                "artifact": bar_artifact(title, data),
            }

    # numeric stat: "average <property> [of <class>]". Scan candidate classes for
    # a numeric property named in the query (the class need not be named).
    if wants_stat:
        op = (
            "average"
            if any(k in lower for k in ["average", "avg", "mean"])
            else "min"
            if "min" in lower
            else "max"
            if "max" in lower
            else "sum"
        )
        candidates = [c for _, c in present] or classes
        for label in candidates:
            props = numeric_properties(driver, project_id, label)
            if not props:
                continue
            prop = next((p for p in props if _mentions(p, lower)), None)
            # If the class was explicitly named, fall back to its first numeric prop.
            if not prop and any(c == label for _, c in present):
                prop = next(iter(props), None)
            if prop:
                val = numeric_stats(driver, project_id, label, prop, op)
                title = f"{op.title()} {prop} ({label})"
                return {
                    "content": f"{title}: {val}.",
                    "artifact": metrics_artifact(
                        title, [{"label": title, "value": val}]
                    ),
                }

    # totals: "how many <class>"
    if wants_count and present:
        label = present[0][1]
        val = count_class(driver, project_id, label)
        title = f"Total {label}"
        return {
            "content": f"There are {val} {label} in this project.",
            "artifact": metrics_artifact(title, [{"label": title, "value": val}]),
        }

    # generic chart request -> overview of entities per class
    if wants_chart:
        data = class_counts(driver, project_id)
        if data:
            return {
                "content": "Entities per class: "
                + ", ".join(f"{d['label']} ({d['value']})" for d in data[:8]) + ".",
                "artifact": bar_artifact("Entities per class", data),
            }

    return None
