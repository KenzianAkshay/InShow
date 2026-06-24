from neo4j import Driver

# The ontology is built and evolved at ingestion time (Part 7). This is the
# fixed scaffolding it grows within:
#   - OntologyClass / OntologyRelation: the meta-layer describing the current
#     schema (which entity types and relationship types exist).
#   - Entity: base label on every instance node, carrying a unique `uid` and
#     provenance (`source_id`, `ingested_at`) so the graph can evolve and so
#     traversals can be highlighted back to the data that produced them.
#
# Uniqueness is scoped to the Show Project: the same class name or entity uid
# may legitimately appear in two different projects, so every key is composite
# with `project_id`.

# Older databases carried global (single-property) constraints; drop them so the
# composite ones below can take over.
LEGACY_CONSTRAINTS = [
    "DROP CONSTRAINT ontology_class_name IF EXISTS",
    "DROP CONSTRAINT ontology_relation_name IF EXISTS",
    "DROP CONSTRAINT entity_uid IF EXISTS",
]

CONSTRAINTS = [
    "CREATE CONSTRAINT ontology_class_name IF NOT EXISTS "
    "FOR (c:OntologyClass) REQUIRE (c.name, c.project_id) IS UNIQUE",
    "CREATE CONSTRAINT ontology_relation_name IF NOT EXISTS "
    "FOR (r:OntologyRelation) REQUIRE (r.name, r.project_id) IS UNIQUE",
    "CREATE CONSTRAINT entity_uid IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE (e.uid, e.project_id) IS UNIQUE",
    "CREATE INDEX entity_source IF NOT EXISTS "
    "FOR (e:Entity) ON (e.source_id)",
    "CREATE INDEX entity_project IF NOT EXISTS "
    "FOR (e:Entity) ON (e.project_id)",
]


def init_graph(driver: Driver) -> None:
    with driver.session() as session:
        for statement in LEGACY_CONSTRAINTS:
            session.run(statement)
        for statement in CONSTRAINTS:
            session.run(statement)
