from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from jobs.build_digest import main
from src.db import get_conn, init_db
from src.repo import start_run, finish_run_ok, insert_news_items
from src.schemas import NewsItem


@pytest.fixture
def chdir_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("NEWS_DB_PATH", str(db_path))
    return db_path


def seed_db(day: str):
    conn = get_conn()
    try:
        init_db(conn)
        run_id = "r1"
        started_at = f"{day}T00:00:00+00:00"
        start_run(conn, run_id, started_at, received=2)
        finish_run_ok(
            conn,
            run_id,
            f"{day}T00:01:00+00:00",
            after_dedupe=2,
            inserted=2,
            duplicates=0,
        )

        items = [
            NewsItem(
                source="reuters",
                url="https://example.com/a",
                published_at=datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
                title="AI merger talk",
                evidence="merger rumor",
            ),
            NewsItem(
                source="reuters",
                url="https://example.com/b",
                published_at=datetime(2026, 1, 14, 11, 0, tzinfo=timezone.utc),
                title="Semiconductor update",
                evidence="chips",
            ),
        ]
        insert_news_items(conn, items)
    finally:
        conn.close()


def test_build_digest_writes_file_and_prints_line(chdir_tmp, tmp_db_path, capsys):
    day = "2026-01-14"
    seed_db(day)

    rc = main(["--date", day, "--top-n", "2"])
    assert rc == 0

    out = capsys.readouterr().out
    assert f"WROTE path=artifacts{os.sep}digest_{day}.html" in out
    assert "count=2" in out

    assert os.path.exists(os.path.join("artifacts", f"digest_{day}.html"))


def test_digest_contains_run_header(chdir_tmp, tmp_db_path):
    day = "2026-01-14"
    seed_db(day)

    main(["--date", day, "--top-n", "2"])

    path = os.path.join("artifacts", f"digest_{day}.html")
    text = open(path, "r", encoding="utf-8").read()
    assert f"Digest for {day}" in text
    assert "run_id:" in text


def test_digest_contains_why_ranked_section(chdir_tmp, tmp_db_path):
    day = "2026-01-14"
    seed_db(day)

    main(["--date", day, "--top-n", "2"])

    path = os.path.join("artifacts", f"digest_{day}.html")
    text = open(path, "r", encoding="utf-8").read()
    assert "Why ranked" in text
    assert 'class="why"' in text


def test_digest_is_deterministic_bytes(chdir_tmp, tmp_db_path):
    day = "2026-01-14"
    seed_db(day)

    main(["--date", day, "--top-n", "2"])
    path = os.path.join("artifacts", f"digest_{day}.html")
    b1 = open(path, "rb").read()

    main(["--date", day, "--top-n", "2"])
    b2 = open(path, "rb").read()

    assert b1 == b2
