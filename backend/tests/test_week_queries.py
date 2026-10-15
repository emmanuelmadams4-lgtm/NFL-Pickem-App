"""The Week endpoint reads predictions a constant number of times, not once per game or per history (step 13b)."""

from sqlalchemy import event

from nflpi import models  # noqa: F401  (registers every table for the shared truncate)
from nflpi.db import get_engine
from tests.conftest import CURRENT

MAX_PREDICTION_QUERIES = 3


def test_week_endpoint_prediction_queries_are_at_most_three(loaded, client):
    seen: list[str] = []

    def count(conn, cursor, statement, *rest):
        if statement.lstrip().startswith("SELECT predictions."):
            seen.append(statement)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", count)
    try:
        assert client.get(f"/api/weeks/{CURRENT}/4").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert 1 <= len(seen) <= MAX_PREDICTION_QUERIES, len(seen)
