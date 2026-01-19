from __future__ import annotations

import argparse
import os

from datetime import date, datetime, timezone
from src.db import get_conn, init_db
from src.repo import get_news_items_by_date, get_run_by_day, insert_run_artifact
from src.scoring import RankConfig, rank_items
from src.explain import explain_item
from src.artifacts import render_digest_html


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--top-n", type=int, default=10)
    args = p.parse_args(argv)

    day = date.fromisoformat(args.date).isoformat()
    top_n = int(args.top_n)

    now = datetime.now(timezone.utc)

    # 1. Fetch data
    conn = get_conn()
    try:
        init_db(conn)
        run = get_run_by_day(conn, day=day)
        items = get_news_items_by_date(conn, day=day)

        cfg = RankConfig()
        ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg)
        explanations = [explain_item(it, now=now, cfg=cfg) for it in ranked]
        html_text = render_digest_html(day=day, run=run, ranked_items=ranked, explanations=explanations, cfg=cfg, now=now, top_n=top_n)
    finally:
        conn.close()

    # 2. Write file
    os.makedirs("artifacts", exist_ok=True)
    path = os.path.join("artifacts", f"digest_{day}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_text)

    # 3. Record artifact (fresh connection)
    if run:
        conn2 = get_conn()
        try:
            init_db(conn2)
            insert_run_artifact(conn2, run_id=run["run_id"], kind="digest", path=path)
        finally:
            conn2.close()

    print(f"WROTE path={path} count={len(ranked)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
