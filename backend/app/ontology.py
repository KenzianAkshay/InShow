import hashlib
import re
from datetime import datetime, timezone

from neo4j import Driver


def sanitize_label(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", name)
    label = "".join(p[:1].upper() + p[1:] for p in parts) or "Entity"
    return "C" + label if label[0].isdigit() else label


def sanitize_rel(name: str) -> str:
    rel = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    if not rel or rel[0].isdigit():
        rel = "REL_" + rel
    return rel


def infer_ontology(records: list[dict], source_name: str) -> dict:
    """Infer a graph model from tabular/record data.

    Low-cardinality columns become shared dimension entities (so records link
    to common nodes, forming a connected ontology); the rest become properties
    on the record node. Deterministic, so re-running merges rather than
    duplicates.
    """
    records = [r for r in records if isinstance(r, dict)]
    columns: list[str] = []
    for record in records:
        for key in record:
            if key not in columns:
                columns.append(key)

    n = len(records)
    distinct: dict[str, set[str]] = {c: set() for c in columns}
    for record in records:
        for c in columns:
            value = record.get(c)
            if value is not None and str(value).strip() != "":
                distinct[c].add(str(value))

    dimension_cols, property_cols = [], []
    for c in columns:
        d = len(distinct[c])
        if 0 < d < n and d <= max(3, n // 2):
            dimension_cols.append(c)
        else:
            property_cols.append(c)

    primary = sanitize_label(source_name)
    classes = {primary}
    relations: set[str] = set()
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}

    for record in records:
        props = {
            c: record[c]
            for c in property_cols
            if record.get(c) not in (None, "")
        }
        row_key = hashlib.md5(
            repr(sorted(record.items())).encode()
        ).hexdigest()[:16]
        record_uid = f"{primary}:{row_key}"
        nodes[record_uid] = {"label": primary, "uid": record_uid, "properties": props}

        for c in dimension_cols:
            value = record.get(c)
            if value is None or str(value).strip() == "":
                continue
            dim_label = sanitize_label(c)
            dim_uid = f"{dim_label}:{value}"
            rel = sanitize_rel(f"HAS_{c}")
            classes.add(dim_label)
            relations.add(rel)
            nodes[dim_uid] = {
                "label": dim_label,
                "uid": dim_uid,
                "properties": {"value": str(value)},
            }
            edges[(record_uid, dim_uid, rel)] = {
                "from": record_uid,
                "to": dim_uid,
                "type": rel,
            }

    return {
        "primary": primary,
        "classes": sorted(classes),
        "relations": sorted(relations),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def instantiate_ontology(mapping: dict, records: list[dict], source_name: str) -> dict:
    """Turn an LLM-proposed schema into a graph spec, then instantiate it from
    the rows deterministically. The LLM decides the model (classes, which column
    keys each, properties, relationships); instantiation is mechanical and safe."""
    class_defs: dict[str, dict] = {}
    for c in mapping.get("classes", []):
        name = sanitize_label(str(c.get("name", "")))
        key = c.get("key_column")
        if not name or not key:
            continue
        class_defs[name] = {
            "key": key,
            "props": [p for p in (c.get("property_columns") or []) if p != key],
        }
    if not class_defs:
        return infer_ontology(records, source_name)

    relations: set[str] = set()
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}

    for record in records:
        present: dict[str, str] = {}
        for cname, info in class_defs.items():
            value = record.get(info["key"])
            if value is None or str(value).strip() == "":
                continue
            uid = f"{cname}:{value}"
            props = {
                p: record[p] for p in info["props"] if record.get(p) not in (None, "")
            }
            nodes[uid] = {"label": cname, "uid": uid, "properties": props}
            present[cname] = uid

        for rel in mapping.get("relationships", []):
            frm = sanitize_label(str(rel.get("from", "")))
            to = sanitize_label(str(rel.get("to", "")))
            name = sanitize_rel(str(rel.get("name", "")))
            if frm in present and to in present and name:
                relations.add(name)
                edges[(present[frm], present[to], name)] = {
                    "from": present[frm],
                    "to": present[to],
                    "type": name,
                }

    return {
        "primary": sanitize_label(source_name),
        "classes": sorted(class_defs),
        "relations": sorted(relations),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def merge_specs(specs: list[dict], source_name: str) -> dict:
    """Union several ontology specs into one. Nodes are merged by uid and edges
    by (from, to, type), so dimension nodes shared across tabs (e.g. the same
    City:Berlin) collapse into one node that links every tab referencing it."""
    classes: set[str] = set()
    relations: set[str] = set()
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    for spec in specs:
        classes.update(spec["classes"])
        relations.update(spec["relations"])
        for node in spec["nodes"]:
            nodes[node["uid"]] = node
        for edge in spec["edges"]:
            edges[(edge["from"], edge["to"], edge["type"])] = edge
    return {
        "primary": sanitize_label(source_name),
        "classes": sorted(classes),
        "relations": sorted(relations),
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
    }


def infer_combined_ontology(sheets: dict[str, list[dict]], source_name: str) -> dict:
    """Build one ontology spanning every tab/sheet. Each tab becomes its own
    entity class (keyed by tab name); tabs are linked automatically wherever they
    share dimension values. Falls back to a single empty spec if no tab has rows.
    """
    specs = [
        infer_ontology(records, sheet_name)
        for sheet_name, records in sheets.items()
        if records
    ]
    if not specs:
        return infer_ontology([], source_name)
    return merge_specs(specs, source_name)


def build_graph(driver: Driver, spec: dict, source_id: int, project_id: int) -> dict:
    """Write the inferred ontology into Neo4j, scoped to a Show Project. MERGE
    makes this idempotent and additive: re-ingesting (or adding another data set
    to the same project) evolves the project's existing ontology with provenance.
    Entities are keyed per project so two projects never collide on the same uid.
    """
    ingested_at = datetime.now(timezone.utc).isoformat()
    with driver.session() as session:
        for name in spec["classes"]:
            session.run(
                "MERGE (c:OntologyClass {name: $name, project_id: $pid})",
                name=name, pid=project_id,
            )
        for name in spec["relations"]:
            session.run(
                "MERGE (r:OntologyRelation {name: $name, project_id: $pid})",
                name=name, pid=project_id,
            )
        for node in spec["nodes"]:
            session.run(
                f"MERGE (e:Entity:`{node['label']}` {{uid: $uid, project_id: $pid}}) "
                "SET e += $props, e.source_id = $sid, e.ingested_at = $ts",
                uid=node["uid"], props=node["properties"],
                sid=source_id, pid=project_id, ts=ingested_at,
            )
        for edge in spec["edges"]:
            session.run(
                "MATCH (a:Entity {uid: $from_uid, project_id: $pid}), "
                "(b:Entity {uid: $to_uid, project_id: $pid}) "
                f"MERGE (a)-[r:`{edge['type']}`]->(b) SET r.source_id = $sid",
                from_uid=edge["from"], to_uid=edge["to"],
                sid=source_id, pid=project_id,
            )
    return {
        "classes": len(spec["classes"]),
        "relations": len(spec["relations"]),
        "nodes": len(spec["nodes"]),
        "edges": len(spec["edges"]),
    }


def retrieve_context(
    driver: Driver, query: str, project_id: int, limit: int = 8
) -> dict:
    """Ground a prompt on the project's ontology: find entities matching the
    query and their immediate neighbourhood. Returns a context string for the LLM
    and the traversal path (nodes + edges touched) for the live visualization to
    animate. Scoped to the Show Project so traversal stays relevant.
    """
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", query.lower()) if len(t) > 2]
    empty = {"context": "", "traversal": {"nodes": [], "edges": []}}
    if not terms:
        return empty

    with driver.session() as session:
        records = session.run(
            "MATCH (e:Entity {project_id: $pid}) "
            "WHERE any(t IN $terms WHERE toLower(e.uid) CONTAINS t "
            "OR toLower(coalesce(e.value, '')) CONTAINS t) "
            "OPTIONAL MATCH (e)-[r]-(n:Entity {project_id: $pid}) "
            "RETURN e.uid AS uid, "
            "[l IN labels(e) WHERE l <> 'Entity'][0] AS label, "
            "collect(DISTINCT {to: n.uid, type: type(r)})[..5] AS rels "
            "LIMIT $limit",
            terms=terms, pid=project_id, limit=limit,
        ).data()

    nodes: list[str] = []
    edges: list[dict] = []
    lines: list[str] = []
    for record in records:
        uid = record["uid"]
        nodes.append(uid)
        related = []
        for rel in record["rels"]:
            if rel.get("to") is None:
                continue
            nodes.append(rel["to"])
            edges.append({"from": uid, "to": rel["to"], "type": rel["type"]})
            related.append(f"{rel['type']} {rel['to']}")
        suffix = f" ({'; '.join(related)})" if related else ""
        lines.append(f"- {record['label']} {uid}{suffix}")

    return {
        "context": "\n".join(lines),
        "traversal": {"nodes": list(dict.fromkeys(nodes)), "edges": edges},
    }


def read_ontology(driver: Driver, project_id: int, limit: int = 250) -> dict:
    """Read a single Show Project's evolving ontology graph."""
    with driver.session() as session:
        classes = [
            r["name"]
            for r in session.run(
                "MATCH (c:OntologyClass {project_id: $pid}) "
                "RETURN c.name AS name ORDER BY name",
                pid=project_id,
            )
        ]
        relations = [
            r["name"]
            for r in session.run(
                "MATCH (r:OntologyRelation {project_id: $pid}) "
                "RETURN r.name AS name ORDER BY name",
                pid=project_id,
            )
        ]
        nodes = [
            {"uid": r["uid"], "label": r["label"], "source_id": r["sid"]}
            for r in session.run(
                "MATCH (e:Entity {project_id: $pid}) RETURN e.uid AS uid, "
                "[l IN labels(e) WHERE l <> 'Entity'][0] AS label, "
                "e.source_id AS sid LIMIT $limit",
                pid=project_id, limit=limit,
            )
        ]
        edges = [
            {"from": r["f"], "to": r["t"], "type": r["ty"]}
            for r in session.run(
                "MATCH (a:Entity {project_id: $pid})-[r]->(b:Entity {project_id: $pid}) "
                "RETURN a.uid AS f, b.uid AS t, type(r) AS ty LIMIT $limit",
                pid=project_id, limit=limit,
            )
        ]
    return {
        "classes": classes,
        "relations": relations,
        "nodes": nodes,
        "edges": edges,
    }
