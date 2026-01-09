import argparse
from datetime import date


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    # fast fail if date format is wrong
    date.fromisoformat(args.date)

    print(f"[RUN] date={args.date} status=ok (placeholder)")
    print(f"[RUN] date={args.date} mode=placeholder status=ok (placeholder)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
