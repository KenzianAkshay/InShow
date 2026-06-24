from app.ontology import (
    build_graph,
    infer_combined_ontology,
    infer_ontology,
    instantiate_ontology,
    retrieve_context,
    sanitize_label,
    sanitize_rel,
)

ROWS = [
    {"exhibitor": "Acme", "booth": "A12", "city": "Berlin", "stage": "Won"},
    {"exhibitor": "Globex", "booth": "B07", "city": "Berlin", "stage": "Proposal"},
    {"exhibitor": "Initech", "booth": "C03", "city": "Munich", "stage": "Won"},
    {"exhibitor": "Umbrella", "booth": "D21", "city": "Munich", "stage": "Lost"},
]


def test_sanitizers():
    assert sanitize_label("trade show!") == "TradeShow"
    assert sanitize_label("123abc").startswith("C")
    assert sanitize_rel("has city") == "HAS_CITY"
    assert sanitize_rel("").startswith("REL_")


def test_infer_ontology_shape():
    spec = infer_ontology(ROWS, "exhibitors")
    assert spec["primary"] == "Exhibitors"
    assert "City" in spec["classes"] and "Stage" in spec["classes"]
    assert set(spec["relations"]) == {"HAS_CITY", "HAS_STAGE"}
    # 4 records + 2 cities (Berlin, Munich) + 3 stages (Won, Proposal, Lost)
    assert len(spec["nodes"]) == 9
    assert len(spec["edges"]) == 8  # each record -> its city + its stage


def test_infer_ontology_evolution_is_superset():
    a = {n["uid"] for n in infer_ontology(ROWS, "exhibitors")["nodes"]}
    rows2 = ROWS + [{"exhibitor": "Stark", "booth": "E1", "city": "Paris", "stage": "Won"}]
    b = {n["uid"] for n in infer_ontology(rows2, "exhibitors")["nodes"]}
    assert a <= b
    assert "City:Paris" in b and "City:Paris" not in a


def test_instantiate_ontology_with_mapping():
    mapping = {
        "classes": [
            {"name": "Exhibitor", "key_column": "exhibitor", "property_columns": ["booth"]},
            {"name": "City", "key_column": "city"},
        ],
        "relationships": [{"name": "LOCATED_IN", "from": "Exhibitor", "to": "City"}],
    }
    spec = instantiate_ontology(mapping, ROWS, "exhibitors")
    assert set(spec["classes"]) == {"Exhibitor", "City"}
    assert spec["relations"] == ["LOCATED_IN"]
    acme = next(n for n in spec["nodes"] if n["uid"] == "Exhibitor:Acme")
    assert acme["properties"]["booth"] == "A12"
    assert len(spec["edges"]) == 4


def test_instantiate_empty_mapping_falls_back():
    spec = instantiate_ontology({"classes": []}, ROWS, "exhibitors")
    assert spec["nodes"]  # fell back to inference


def test_combined_ontology_links_tabs_by_shared_dimension():
    sheets = {
        "Exhibitors": [
            {"exhibitor": "Acme", "city": "Berlin"},
            {"exhibitor": "Globex", "city": "Berlin"},
            {"exhibitor": "Initech", "city": "Munich"},
        ],
        "Sessions": [
            {"session": "Keynote", "city": "Berlin"},
            {"session": "Workshop", "city": "Berlin"},
            {"session": "Panel", "city": "Munich"},
        ],
    }
    spec = infer_combined_ontology(sheets, "expo")
    # each tab is its own class, sharing the City dimension
    assert {"Exhibitors", "Sessions", "City"} <= set(spec["classes"])
    uids = {n["uid"] for n in spec["nodes"]}
    assert "City:Berlin" in uids
    # exactly one shared City:Berlin node, linked from both tabs
    assert sum(1 for n in spec["nodes"] if n["uid"] == "City:Berlin") == 1
    froms = {
        e["from"].split(":")[0] for e in spec["edges"] if e["to"] == "City:Berlin"
    }
    assert {"Exhibitors", "Sessions"} <= froms


class _Session:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, query, **kw):
        self.log.append((query, kw))
        return []


class _Driver:
    def __init__(self):
        self.log = []

    def session(self):
        return _Session(self.log)


def test_build_graph_uses_merge_and_provenance():
    spec = infer_ontology(ROWS, "exhibitors")
    driver = _Driver()
    summary = build_graph(driver, spec, source_id=7, project_id=3)
    assert summary["nodes"] == len(spec["nodes"])
    qs = [q for q, _ in driver.log]
    assert any("MERGE (c:OntologyClass" in q for q in qs)
    assert any("e.source_id = $sid" in q and "e.ingested_at" in q for q in qs)
    node_writes = [kw for q, kw in driver.log if "MERGE (e:Entity" in q]
    assert node_writes and all(kw["sid"] == 7 for kw in node_writes)
    # every entity is scoped to its Show Project
    assert all(kw["pid"] == 3 for kw in node_writes)


class _CtxDriver:
    def session(self):
        return _CtxSession()


class _CtxSession:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, query, **kw):
        class R:
            def data(self_inner):
                return [
                    {"uid": "City:Berlin", "label": "City",
                     "rels": [{"to": "Exhibitor:Acme", "type": "HAS_CITY"}]}
                ]
        return R()


def test_retrieve_context_builds_traversal():
    out = retrieve_context(_CtxDriver(), "where is berlin", project_id=1)
    assert "City:Berlin" in out["context"]
    assert "City:Berlin" in out["traversal"]["nodes"]
    assert out["traversal"]["edges"][0]["type"] == "HAS_CITY"


def test_retrieve_context_empty_query():
    out = retrieve_context(_CtxDriver(), "a", project_id=1)  # too short for terms
    assert out == {"context": "", "traversal": {"nodes": [], "edges": []}}
