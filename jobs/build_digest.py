from __future__ import annotations

# Load .env before other imports that use env vars
from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import os

from datetime import date, datetime, timezone
from src.db import get_conn, init_db
from src.repo import (
    get_news_items_by_date,
    get_run_by_day,
    insert_run_artifact,
    get_cached_summary,
    insert_cached_summary,
    update_run_llm_stats,
    get_active_source_weights,
)
from src.scoring import RankConfig, rank_items
from src.explain import explain_item
from src.artifacts import render_digest_html
from src.clients.llm_openai import summarize, MODEL
from src.grounding import validate_grounding
from src.cache_utils import compute_cache_key
from src.llm_schemas.summary import SummaryResult
from src.logging_utils import log_event



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

        # Load dynamic source weights (Milestone 3b)
        source_weights = get_active_source_weights(conn)
        cfg = RankConfig(source_weights=source_weights)
        ranked = rank_items(items, now=now, top_n=top_n, cfg=cfg)
        explanations = [explain_item(it, now=now, cfg=cfg) for it in ranked]

        # Initialize run-level stats
        llm_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "saved_cost_usd": 0.0,
            "total_latency_ms": 0,
        }
        # Summarize each item and validate grounding
        summaries = []
        for item in ranked:
            #Compute cache key from model + evidence
            evidence = item.evidence or ""
            cache_key = compute_cache_key(MODEL, evidence)

            #Check Cache first
            cached = get_cached_summary(conn, cache_key=cache_key)
            if cached:
                # CACHE HIT - deserialize and use
                cached_data = json.loads(cached["summary_json"])
                result = SummaryResult(**cached_data)
                log_event("llm_cache_hit", cache_key=cache_key, saved_cost_usd=cached["cost_usd"], saved_latency_ms=cached["latency_ms"])
                #Update run stats
                llm_stats["cache_hits"] +=1
                llm_stats["saved_cost_usd"] += cached["cost_usd"]
            else:
                #CACHE MISS - call LLM
                raw_result, usage = summarize(item, item.evidence)
                validated = validate_grounding(raw_result, item.evidence)

                #ONLY cache successful grounded results (no refusales)
                if validated.refusal is None:
                    insert_cached_summary(
                        conn,
                        cache_key=cache_key,
                        model_name=MODEL,
                        summary_json=json.dumps(validated.model_dump()),
                        prompt_tokens=usage["prompt_tokens"],
                        completion_tokens=usage["completion_tokens"],
                        cost_usd=usage["cost_usd"],
                        latency_ms=usage["latency_ms"],
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                result = validated
                log_event("llm_cache_miss", cache_key=cache_key, cost_usd=usage["cost_usd"], latency_ms=usage["latency_ms"], was_cached=validated.refusal is None)
                #update run stats
                llm_stats["cache_misses"] += 1
                llm_stats["total_prompt_tokens"] += usage["prompt_tokens"]
                llm_stats["total_completion_tokens"] += usage["completion_tokens"]
                llm_stats["total_cost_usd"] += usage["cost_usd"]
                llm_stats["total_latency_ms"] += usage["latency_ms"]
            
            summaries.append(result)

        log_event("run_llm_stats", **llm_stats)

        # Persist LLM stats to run record (Day 20)
        if run:
            update_run_llm_stats(
                conn,
                run["run_id"],
                cache_hits=llm_stats["cache_hits"],
                cache_misses=llm_stats["cache_misses"],
                total_cost_usd=llm_stats["total_cost_usd"],
                saved_cost_usd=llm_stats["saved_cost_usd"],
                total_latency_ms=llm_stats["total_latency_ms"],
            )

        html_text = render_digest_html(day=day, run=run, ranked_items=ranked, explanations=explanations, summaries=summaries, cfg=cfg, now=now, top_n=top_n)    
    
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
