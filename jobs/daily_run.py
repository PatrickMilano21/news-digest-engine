from __future__ import annotations

# Load .env file BEFORE other imports (so env vars are available)
from dotenv import load_dotenv
load_dotenv()

import argparse
import json
import os
import time
import uuid
from datetime import date, datetime, timezone

from src.db import get_conn, init_db
from src.error_codes import PARSE_ERROR
from src.feeds import FEEDS
from src.logging_utils import log_event
from src.normalize import normalize_and_dedupe
from src.rss_fetch import fetch_rss_with_retry
from src.rss_parse import parse_rss
from src.weekly_report import write_weekly_report

# Ranking + explanation
from src.scoring import RankConfig, rank_items
from src.explain import explain_item

# LLM summarization + caching
from src.clients.llm_openai import summarize, MODEL
from src.grounding import validate_grounding
from src.cache_utils import compute_cache_key
from src.llm_schemas.summary import SummaryResult

# Artifact generation
from src.artifacts import render_digest_html

# Eval harness
from evals.runner import run_all as run_ranking_evals, write_eval_report
from evals.summary_runner import run_all_cases as run_summary_evals, summarize_results as summarize_summary_evals

# Repo functions (consolidated)
from src.repo import (
    start_run,
    finish_run_ok,
    finish_run_error,
    get_run_by_day,
    insert_news_items,
    upsert_run_failures,
    write_audit_log,
    get_cached_summary,
    insert_cached_summary,
    insert_run_artifact,
    update_run_llm_stats,
)

TOP_N = 10  # Number of items to rank and summarize


FIXTURE_FEEDS = [
    {"path": "fixtures/feeds/daily_run_fixture.xml", "source": "fixture"},
]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--mode", default="fixtures", choices=["fixtures", "prod"])
    p.add_argument("--force", action="store_true", help="Override idempotency check")
    args = p.parse_args()

    # Validate date
    date.fromisoformat(args.date)
    day = args.date

    failures: dict[str, int] = {}
    failed_sources: dict[str, list[str]] = {}  # {error_code: [path_or_url, ...]}
    stage_failures: dict[str, str] = {}
    t0: float = 0.0
    run_id = ""

    conn = get_conn()
    try:
        init_db(conn)

        # Idempotency: skip if already have successful run for this day
        existing_run = get_run_by_day(conn, day=day)
        if existing_run and not args.force:
            run_id = uuid.uuid4().hex
            log_event("daily_run_skipped", run_id=run_id, day=day, reason="already_ok")
            print(f"SKIP day={day} reason=already_ok (use --force to override)")
            return 0
        if existing_run and args.force:
            log_event("daily_run_force", day=day, existing_run_id=existing_run["run_id"])
            print(f"FORCE day={day} overriding existing run")

        # Start run
        run_id = uuid.uuid4().hex
        t0 = time.perf_counter()
        now = datetime.now(timezone.utc)
        log_event("daily_run_started", run_id=run_id, day=day, mode=args.mode)

        run_day = date.fromisoformat(day)
        started_at = datetime.combine(run_day, now.time(), tzinfo=timezone.utc).isoformat()
        start_run(conn, run_id=run_id, started_at=started_at, received=0)
        write_audit_log(conn, event_type="RUN_STARTED", ts=started_at, run_id=run_id, day=day, details={})

        # =====================================================================
        # Stage 1: INGEST
        # =====================================================================
        all_items = []

        if args.mode == "fixtures":
            # Load from local fixture files
            for feed in FIXTURE_FEEDS:
                path = feed["path"]
                source = feed["source"]
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        xml_content = f.read()
                    items = parse_rss(xml_content, source=source)
                    all_items.extend(items)
                    log_event("fixture_loaded", run_id=run_id, path=path, items=len(items))
                except FileNotFoundError:
                    log_event("fixture_not_found", run_id=run_id, path=path)
                    print(f"FIXTURE_NOT_FOUND path={path}")
                    failures["FIXTURE_NOT_FOUND"] = failures.get("FIXTURE_NOT_FOUND", 0) + 1
                    failed_sources.setdefault("FIXTURE_NOT_FOUND", []).append(path)
                except Exception as exc:
                    log_event("fixture_parse_failed", run_id=run_id, path=path, error=str(exc))
                    failures[PARSE_ERROR] = failures.get(PARSE_ERROR, 0) + 1
                    failed_sources.setdefault(PARSE_ERROR, []).append(path)
        else:
            # Production mode: fetch from real RSS feeds
            for feed in FEEDS:
                url = feed["url"]
                source = feed["source"]

                result = fetch_rss_with_retry(url)

                if not result.ok:
                    log_event(
                        "feed_fetch_failed",
                        run_id=run_id,
                        url=url,
                        error_code=result.error_code,
                        error_message=result.error_message,
                    )
                    code = result.error_code or "UNKNOWN"
                    failures[code] = failures.get(code, 0) + 1
                    failed_sources.setdefault(code, []).append(url)
                    continue

                try:
                    items = parse_rss(result.content, source=source)
                    all_items.extend(items)
                    log_event("feed_fetch_ok", run_id=run_id, url=url, items=len(items))
                except Exception as exc:
                    log_event(
                        "feed_parse_failed",
                        run_id=run_id,
                        url=url,
                        error=str(exc),
                    )
                    failures[PARSE_ERROR] = failures.get(PARSE_ERROR, 0) + 1
                    failed_sources.setdefault(PARSE_ERROR, []).append(url)
                    continue

        # =====================================================================
        # Stage 2: DEDUPE
        # =====================================================================
        received = len(all_items)

        # Early exit if no items received
        if received == 0:
            log_event("daily_run_no_items", run_id=run_id, day=day, mode=args.mode)
            print(f"NO_ITEMS day={day} mode={args.mode} (no items received from feeds)")
            # Still finish the run so we have a record
            finished_at = datetime.now(timezone.utc).isoformat()
            finish_run_ok(conn, run_id=run_id, finished_at=finished_at, after_dedupe=0, inserted=0, duplicates=0)
            return 0

        deduped = normalize_and_dedupe(all_items)
        after_dedupe = len(deduped)

        if deduped:
            result = insert_news_items(conn, deduped)
            inserted = result["inserted"]
            duplicates = (received - after_dedupe) + result["duplicates"]
        else:
            inserted = 0
            duplicates = 0

        # Store ingest failures (with which feeds failed)
        if failures:
            upsert_run_failures(conn, run_id=run_id, breakdown=failures, sources=failed_sources)

        # Update received count
        conn.execute("UPDATE runs SET received = ? WHERE run_id = ?", (received, run_id))
        conn.commit()

        log_event("dedupe_complete", run_id=run_id, received=received, after_dedupe=after_dedupe, inserted=inserted)    

        # =====================================================================
        # Stage 3: RANK
        # =====================================================================
        ranked = []
        explanations = []
        cfg = RankConfig()
        try:
            ranked = rank_items(deduped, now=now, top_n=TOP_N, cfg=cfg)
            explanations = [explain_item(it, now=now, cfg=cfg) for it in ranked]
            log_event("rank_complete", run_id=run_id, ranked_count=len(ranked))
        except Exception as e:
            log_event("rank_error", run_id=run_id, error=str(e))
            stage_failures["rank"] = str(e)

        # =====================================================================
        # Stage 4: SUMMARIZE (per-item isolation)
        # =====================================================================
        summaries = []
        llm_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cost_usd": 0.0,
            "saved_cost_usd": 0.0,
            "summary_failures": 0,
            "llm_refusals": 0,
        }
        refusal_breakdown: dict[str, int] = {}

        for item in ranked:
            try:
                evidence = item.evidence or ""
                cache_key = compute_cache_key(MODEL, evidence)
                cached = get_cached_summary(conn, cache_key=cache_key)

                if cached:
                    result = SummaryResult(**json.loads(cached["summary_json"]))
                    llm_stats["cache_hits"] += 1
                    llm_stats["saved_cost_usd"] += cached["cost_usd"]
                else:
                    raw_result, usage = summarize(item, item.evidence)
                    validated = validate_grounding(raw_result, item.evidence)

                    if validated.refusal is None:
                        insert_cached_summary(
                            conn,
                            cache_key=cache_key,
                            model_name=MODEL,
                            summary_json=validated.model_dump_json(),
                            prompt_tokens=usage["prompt_tokens"],
                            completion_tokens=usage["completion_tokens"],
                            cost_usd=usage["cost_usd"],
                            latency_ms=usage["latency_ms"],
                            created_at=datetime.now(timezone.utc).isoformat(),
                        )
                    else:
                        # Track refusals (LLM_DISABLED, LLM_API_FAIL, grounding failures, etc.)
                        llm_stats["llm_refusals"] += 1
                        refusal_code = validated.refusal
                        refusal_breakdown[refusal_code] = refusal_breakdown.get(refusal_code, 0) + 1
                        log_event("llm_refusal",
                            run_id=run_id,
                            item_url=str(item.url),
                            refusal_code=refusal_code
                        )

                    result = validated
                    llm_stats["cache_misses"] += 1
                    llm_stats["total_prompt_tokens"] += usage["prompt_tokens"]
                    llm_stats["total_completion_tokens"] += usage["completion_tokens"]
                    llm_stats["total_cost_usd"] += usage["cost_usd"]

            except Exception as e:
                log_event("summarize_item_error",
                    run_id=run_id,
                    item_url=str(item.url),
                    error_type=type(e).__name__,
                    error=str(e)
                )
                result = SummaryResult(refusal="PIPELINE_ERROR")
                llm_stats["summary_failures"] += 1

            summaries.append(result)

        # Store LLM refusals in run_failures table
        if refusal_breakdown:
            upsert_run_failures(conn, run_id=run_id, breakdown=refusal_breakdown)

        log_event("summarize_complete", run_id=run_id, **llm_stats, refusal_breakdown=refusal_breakdown)

        # =====================================================================
        # Stage 5: DIGEST
        # =====================================================================
        digest_path = None
        try:
            os.makedirs("artifacts", exist_ok=True)
            html = render_digest_html(
                day=day,
                run={
                    "run_id": run_id,
                    "status": "ok",
                    "started_at": started_at,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "received": received,
                    "after_dedupe": after_dedupe,
                    "inserted": inserted,
                    "duplicates": duplicates,
                },
                ranked_items=ranked,
                explanations=explanations,
                summaries=summaries,
                cfg=cfg,
                now=now,
                top_n=TOP_N
            )
            digest_path = f"artifacts/digest_{day}.html"
            with open(digest_path, "w", encoding="utf-8") as f:
                f.write(html)
            insert_run_artifact(conn, run_id=run_id, kind="digest", path=digest_path)
            log_event("digest_complete", run_id=run_id, path=digest_path)
        except Exception as e:
            log_event("digest_error", run_id=run_id, error=str(e))
            stage_failures["digest"] = str(e)

        # =====================================================================
        # Stage 6: EVAL (automatic quality checks)
        # =====================================================================
        eval_stats = {
            "ranking_total": 0,
            "ranking_passed": 0,
            "ranking_failed": 0,
            "summary_total": 0,
            "summary_passed": 0,
            "summary_failed": 0,
            "overall_pass": True,
        }
        eval_report_path = None
        try:
            # Run ranking evals
            ranking_results = run_ranking_evals(now=now)
            eval_stats["ranking_total"] = ranking_results["total"]
            eval_stats["ranking_passed"] = ranking_results["passed"]
            eval_stats["ranking_failed"] = ranking_results["failed"]

            # Run summary quality evals
            summary_results = run_summary_evals()
            summary_stats = summarize_summary_evals(summary_results)
            eval_stats["summary_total"] = summary_stats["total"]
            eval_stats["summary_passed"] = summary_stats["passed"]
            eval_stats["summary_failed"] = summary_stats["failed"]

            # Determine overall pass/fail
            total_failed = eval_stats["ranking_failed"] + eval_stats["summary_failed"]
            eval_stats["overall_pass"] = (total_failed == 0)

            # Write eval report
            eval_report_path = write_eval_report(ranking_results, day=day, run_id=run_id)
            insert_run_artifact(conn, run_id=run_id, kind="eval_report", path=eval_report_path)

            log_event("eval_complete",
                run_id=run_id,
                **eval_stats,
                report_path=eval_report_path
            )
        except Exception as e:
            log_event("eval_error", run_id=run_id, error=str(e))
            stage_failures["eval"] = str(e)
            eval_stats["overall_pass"] = False

        # =====================================================================
        # Stage 7: COMPLETE
        # =====================================================================
        finished_at = datetime.combine(
            run_day, datetime.now(timezone.utc).time(), tzinfo=timezone.utc
        ).isoformat()

        # Persist LLM stats to run record
        update_run_llm_stats(
            conn,
            run_id=run_id,
            cache_hits=llm_stats["cache_hits"],
            cache_misses=llm_stats["cache_misses"],
            total_cost_usd=llm_stats["total_cost_usd"],
            saved_cost_usd=llm_stats["saved_cost_usd"],
            total_latency_ms=llm_stats.get("total_latency_ms", 0),
        )

        finish_run_ok(
            conn,
            run_id=run_id,
            finished_at=finished_at,
            after_dedupe=after_dedupe,
            inserted=inserted,
            duplicates=duplicates,
        )
        write_audit_log(
            conn, 
            event_type="RUN_FINISHED_OK", 
            ts=finished_at, 
            run_id=run_id, 
            day=day, 
            details={
                "inserted": inserted,
                "duplicates": duplicates,
                "ranked": len(ranked),
                "summaries": len(summaries),
                "llm_stats": llm_stats,
                "stage_failures": stage_failures,
                "refusal_breakdown": refusal_breakdown,
            }
        )

        # Weekly report (best-effort)
        try:
            write_weekly_report(conn=conn, end_day=day)
        except Exception as e:
            log_event("weekly_report_failed", error=str(e))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        log_event(
            "run_end",
            run_id=run_id,
            run_type="daily",
            status="ok",
            elapsed_ms=elapsed_ms,
            failures_by_code=failures,
            stage_failures=stage_failures,
            llm_stats=llm_stats,
            eval_stats=eval_stats,
            counts={
                "received": received,
                "after_dedupe": after_dedupe,
                "inserted": inserted,
                "duplicates": duplicates,
                "ranked": len(ranked),
                "summaries": len(summaries),
            },
        )

        eval_status = "PASS" if eval_stats["overall_pass"] else "FAIL"
        print(f"OK day={day} run_id={run_id} received={received} ranked={len(ranked)} summaries={len(summaries)} evals={eval_status}")      
        return 0

    except Exception as exc:
        # Unexpected error — mark run as failed
        finished_at = datetime.now(timezone.utc).isoformat()
        error_type = type(exc).__name__
        try:
            finish_run_error(
                conn,
                run_id=run_id,
                finished_at=finished_at,
                error_type=error_type,
                error_message=str(exc),
            )
            write_audit_log(
                conn,
                event_type="RUN_FINISHED_ERROR", 
                ts=finished_at, 
                run_id=run_id, 
                day=day,
                details={"error_type": error_type, "error_message": str(exc)}
            )
        except:
            pass
        elapsed_ms = int((time.perf_counter() - t0) * 1000) if t0 else 0
        log_event(
            "run_end",
            run_id=run_id,
            run_type="daily",
            status="error",
            elapsed_ms=elapsed_ms,
            failures_by_code=failures,
            stage_failures=stage_failures,
            error=str(exc),
        )
        print(f"ERROR day={day} run_id={run_id} error={exc}")
        return 1

    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
