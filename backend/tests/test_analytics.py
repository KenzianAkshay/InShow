import pytest

from app import analytics


class _Sess:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, q, **kw):
        if "RETURN label, count(*) AS value" in q:
            return [
                {"label": "Exhibitors", "value": 5},
                {"label": "City", "value": 3},
                {"label": None, "value": 1},  # filtered out
            ]
        if "count(DISTINCT" in q:
            return [
                {"label": "Berlin", "value": 3},
                {"label": "Munich", "value": 2},
            ]
        if "RETURN count(e) AS value" in q:
            return [{"value": 5}]
        if "properties(e) AS props" in q:
            return [
                {"props": {"booth_size": "10", "name": "A"}},
                {"props": {"booth_size": "20", "name": "B"}},
            ]
        return []


class _Driver:
    def session(self):
        return _Sess()


D = _Driver()


def test_safe_calculate_valid():
    assert analytics.safe_calculate("2 + 3 * 4") == 14
    assert analytics.safe_calculate("(5 + 3 + 2) / 3") == pytest.approx(3.3333, rel=1e-3)
    assert analytics.safe_calculate("round(10/3, 2)") == 3.33
    assert analytics.safe_calculate("2 ** 10") == 1024
    assert analytics.safe_calculate("-5 + 8") == 3


def test_safe_calculate_rejects_unsafe():
    for expr in ["__import__('os')", "a + 1", "open('x')", "1; 2", "lambda: 1"]:
        with pytest.raises(Exception):
            analytics.safe_calculate(expr)


def test_class_counts_filters_none():
    out = analytics.class_counts(D, 1)
    assert out == [
        {"label": "Exhibitors", "value": 5},
        {"label": "City", "value": 3},
    ]


def test_count_by_dimension():
    out = analytics.count_by_dimension(D, 1, "Exhibitors", "City")
    assert out == [
        {"label": "Berlin", "value": 3},
        {"label": "Munich", "value": 2},
    ]
    assert analytics.count_by_dimension(D, 1, None, None) == []


def test_count_class_and_numeric_stats():
    assert analytics.count_class(D, 1, "Exhibitors") == 5
    assert analytics.numeric_stats(D, 1, "Exhibitors", "booth_size", "average") == 15.0
    assert analytics.numeric_stats(D, 1, "Exhibitors", "booth_size", "sum") == 30.0
    assert analytics.numeric_stats(D, 1, "Exhibitors", "missing", "sum") == 0


def test_dispatch():
    dispatch = analytics.make_dispatch(D, 1)
    assert dispatch("calculate", {"expression": "6*7"}) == {"result": 42}
    assert dispatch("query_ontology", {"operation": "class_counts"})["data"]
    assert dispatch("query_ontology", {"operation": "count_class", "label": "Exhibitors"}) == {
        "value": 5
    }
    assert "error" in dispatch("nope", {})


def test_deterministic_group_by():
    out = analytics.deterministic_analytics(D, 1, "chart exhibitors by city")
    assert out and out["artifact"]["type"] == "bar"
    assert out["artifact"]["data"][0]["label"] == "Berlin"
    assert "by" in out["content"].lower()


def test_deterministic_count():
    out = analytics.deterministic_analytics(D, 1, "how many exhibitors are there?")
    assert out and out["artifact"]["type"] == "metrics"
    assert out["artifact"]["items"][0]["value"] == 5


def test_deterministic_no_intent_returns_none():
    assert analytics.deterministic_analytics(D, 1, "hello, who are you") is None


class _SchemaSess:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, q, **kw):
        if "RETURN name, count(*) AS count" in q:
            return [{"name": "Exhibitors", "count": 5}, {"name": "City", "count": 3}]
        if "RETURN frm AS from" in q:
            return [{"from": "Exhibitors", "to": "City", "type": "HAS_CITY", "count": 7}]
        return []


class _SchemaDriver:
    def session(self):
        return _SchemaSess()


SD = _SchemaDriver()


def test_suggest_followups_from_schema():
    out = analytics.suggest_followups(SD, 1)
    assert "Chart Exhibitors by City" in out
    assert any(s.startswith("How many") for s in out)
    assert "Show entities per class" in out


def test_suggest_followups_is_intent_aware():
    out = analytics.suggest_followups(SD, 1, "how many exhibitors are there")
    # already asked about Exhibitors counts -> suggest a different class instead
    assert "How many Exhibitors?" not in out
    assert out  # still offers other angles (charts, overview)


def test_suggest_followups_empty_without_ontology():
    class _Empty:
        def session(self):
            class _S:
                def __enter__(self_):
                    return self_

                def __exit__(self_, *a):
                    return False

                def run(self_, *a, **k):
                    return []

            return _S()

    assert analytics.suggest_followups(_Empty(), 1) == []
