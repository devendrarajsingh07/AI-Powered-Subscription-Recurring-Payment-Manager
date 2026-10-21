"""Operator CLI: python -m app.llm_admin status|kill|restore. Prints counts and flags only."""

import argparse
import json

from app.db import get_engine
from app.services import llm_controls as controls


def main():
    parser = argparse.ArgumentParser(description="Live-AI kill switch and usage counters")
    parser.add_argument("command", choices=["status", "kill", "restore"])
    command = parser.parse_args().command
    engine = get_engine()
    if command != "status":
        controls.set_switch(engine, command == "kill")
    print(
        json.dumps(
            dict(offline_forced=controls.forced_offline(engine), usage_today=controls.usage(engine))
        )
    )


if __name__ == "__main__":
    main()
