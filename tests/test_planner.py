import pytest
from app.schemas import PlannerOutput, SubQuery

def test_planner_output_valid() -> None:    # verify PlannerOutput accepts valid data
    data = {
        "technology_a": "DuckDB",
        "technology_b": "ClickHouse",
        "axes": ["Performance", "Memory", "License"],
        "sub_queries": [
            {"axis": "Performance", "query": "DuckDB vs ClickHouse benchmark 2025"},
            {"axis": "Memory", "query": "ClickHouse memory footprint"},
            {"axis": "License", "query": "DuckDB vs ClickHouse license comparison"},
        ],
    }
    result = PlannerOutput.model_validate(data)
    assert result.technology_a == "DuckDB"
    assert result.technology_b == "ClickHouse"
    assert len(result.axes) == 3
    assert len(result.sub_queries) == 3
    assert result.sub_queries[0].axis == "Performance"


def test_planner_output_rejects_too_few_axes() -> None:     # verify PlannerOutput rejects fewer than 2 axes
    data = {
        "technology_a": "DuckDB",
        "technology_b": "ClickHouse",
        "axes": ["Performance"],
        "sub_queries": [
            {"axis": "Performance", "query": "benchmark"},
        ],
    }
    with pytest.raises(Exception):
        PlannerOutput.model_validate(data)


def test_planner_output_rejects_too_many_axes() -> None:        # verify PlannerOutput rejects more than 6 axes
    data = {
        "technology_a": "A",
        "technology_b": "B",
        "axes": ["A", "B", "C", "D", "E", "F", "G"],
        "sub_queries": [
            {"axis": "A", "query": "q"},
            {"axis": "B", "query": "q"},
            {"axis": "C", "query": "q"},
            {"axis": "D", "query": "q"},
            {"axis": "E", "query": "q"},
            {"axis": "F", "query": "q"},
            {"axis": "G", "query": "q"},
        ],
    }
    with pytest.raises(Exception):
        PlannerOutput.model_validate(data)


def test_subquery_requires_axis_and_query() -> None:        # verify SubQuery rejects missing fields
    with pytest.raises(Exception):
        SubQuery.model_validate({"axis": "Performance"})