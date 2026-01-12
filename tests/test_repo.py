# tests/test_repo.py
from src.db import get_conn, init_db
from src.repo import insert_news_items
from src.schemas import NewsItem


def test_insert_news_items_is_idempotent(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_file))

    conn = get_conn()
    try:
        init_db(conn)

        item = NewsItem(
            source="example",
            url="https://example.com/news?id=1#section",
            published_at="2026-01-10T12:00:00Z",
            title="Hello   world",
            evidence="Some snippet",
        )

        r1 = insert_news_items(conn, [item])
        r2 = insert_news_items(conn, [item])

        assert r1["inserted"] == 1
        assert r1["duplicates"] == 0
        assert r2["inserted"] == 0
        assert r2["duplicates"] == 1

        count = conn.execute("SELECT COUNT(*) FROM news_items;").fetchone()[0]
        assert count == 1
    finally:
        conn.close()
