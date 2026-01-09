import argparse
from datetime import date


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    date.fromisoformat(args.date)

    print(f"[EVAL] date={args.date} score=1.00 (placeholder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
