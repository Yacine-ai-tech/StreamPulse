"""Real, end-to-end test of the dlt webhook pipeline -- no mocking of dlt itself.

Runs an actual dlt pipeline against a local DuckDB file (no external server
needed) and asserts genuine incremental-load / dedup behavior: re-running with
an overlapping record set never produces duplicate rows, and new records are
picked up. Skips (rather than fails) if dlt isn't installed, matching the
graceful-degradation pattern the module itself uses.
"""
import shutil
import uuid

import pytest

dlt = pytest.importorskip("dlt")

from ingestion.dlt_sources import run_webhook_pipeline  # noqa: E402


@pytest.fixture
def dlt_pipeline_name():
    # Unique per test run so parallel/successive runs never share pipeline state.
    name = f"test_streampulse_{uuid.uuid4().hex[:8]}"
    yield name
    shutil.rmtree(f"{name}.duckdb", ignore_errors=True)
    shutil.rmtree(name, ignore_errors=True)


def test_webhook_pipeline_loads_records(dlt_pipeline_name):
    records = [
        {"id": "a1", "metric": "revenue", "raw": "Q1 revenue $1.2M"},
        {"id": "a2", "metric": "churn", "raw": "monthly churn 3.1%"},
    ]
    info = run_webhook_pipeline(records, pipeline_name=dlt_pipeline_name)
    assert info is not None

    pipeline = dlt.pipeline(pipeline_name=dlt_pipeline_name, destination="duckdb")
    with pipeline.sql_client() as client:
        rows = client.execute_sql(
            f"SELECT _record_id, metric FROM {pipeline.dataset_name}.webhook_records ORDER BY _record_id"
        )
    assert len(rows) == 2
    assert {r[0] for r in rows} == {"a1", "a2"}


def test_webhook_pipeline_dedupes_on_rerun(dlt_pipeline_name):
    """The actual behavior dlt's merge write disposition is for: running the
    same source twice with an overlapping id set must not double the row
    count -- that would mean this is decorative dlt usage, not real incremental
    loading."""
    first = [{"id": "b1", "metric": "revenue", "raw": "v1"}]
    run_webhook_pipeline(first, pipeline_name=dlt_pipeline_name)

    # Same id, changed content (simulates a corrected/updated record) + one new id.
    second = [
        {"id": "b1", "metric": "revenue", "raw": "v2-corrected"},
        {"id": "b2", "metric": "headcount", "raw": "new record"},
    ]
    run_webhook_pipeline(second, pipeline_name=dlt_pipeline_name)

    pipeline = dlt.pipeline(pipeline_name=dlt_pipeline_name, destination="duckdb")
    with pipeline.sql_client() as client:
        rows = client.execute_sql(
            f"SELECT _record_id, raw FROM {pipeline.dataset_name}.webhook_records ORDER BY _record_id"
        )
    assert len(rows) == 2, f"expected 2 deduped rows, got {len(rows)}: {rows}"
    by_id = {r[0]: r[1] for r in rows}
    assert by_id["b1"] == "v2-corrected", "merge should have updated b1's content, not duplicated it"
    assert by_id["b2"] == "new record"
