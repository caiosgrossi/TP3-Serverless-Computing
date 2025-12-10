"""Helper script to seed Redis with mock metrics for the Streamlit dashboard."""

import argparse
import json
import os

import redis
from dotenv import load_dotenv

# Load local .env if present so the script mirrors app.py behavior.
load_dotenv(".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Redis with mock metrics JSON.")
    parser.add_argument(
        "--host",
        default=os.environ.get("REDIS_HOST", "localhost"),
        help="Redis host (default: env REDIS_HOST or localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("REDIS_PORT", "6379")),
        help="Redis port (default: env REDIS_PORT or 6379)",
    )
    parser.add_argument(
        "--db",
        type=int,
        default=int(os.environ.get("REDIS_DB", "0")),
        help="Redis logical DB (default: env REDIS_DB or 0)",
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("REDIS_KEY", "2023001654-proj3-output"),
        help="Redis key to set (default: env REDIS_KEY or ifs4-proj3-output)",
    )
    return parser.parse_args()


def build_mock_payload() -> dict:
    # Simple static payload; tweak as desired for testing.
    return {
        "percent-network-egress": 100.00,
        "percent-memory-cache": 100.00,
        "avg-util-cpu0-60sec": 25.45,
        "avg-util-cpu1-60sec": 25.89,
        "avg-util-cpu2-60sec": 0.34,
        "avg-util-cpu3-60sec": 1.12,
    }


def main() -> None:
    args = parse_args()
    payload = build_mock_payload()

    client = redis.Redis(
        host=args.host,
        port=args.port,
        db=args.db,
        decode_responses=True,
    )

    client.set(args.key, json.dumps(payload))
    print(f"Seeded key '{args.key}' on {args.host}:{args.port}/{args.db}")
    print("Payload:")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
