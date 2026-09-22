"""CLI for the one-shot two-round intake."""
from __future__ import annotations

import argparse
import json
import sys

from intake.constants import DEPTH_CHOICES, ENHANCEMENTS
from intake.prefs import load_prefs
from intake.prompts import PROMPT_SCRIPT
from intake.session import run_intake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduEvidence two-round intake")
    parser.add_argument("--question", default=None, help="research question")
    parser.add_argument("--depth", default=None,
                        choices=list(DEPTH_CHOICES) + ["quick", "standard", "deep"],
                        help="S/M/L/auto (or legacy quick/standard/deep)")
    parser.add_argument("--enhancement", action="append", default=None,
                        choices=list(ENHANCEMENTS),
                        help="execution enhancement (repeatable)")
    parser.add_argument("--domain", default="education")
    parser.add_argument("--yes", action="store_true",
                        help="skip prompts; use prefs + explicit flags (unattended)")
    parser.add_argument("--print-prompts", action="store_true",
                        help="print the fixed two-round prompt script and exit")
    parser.add_argument("--show-prefs", action="store_true",
                        help="print current prefs.json and exit")
    args = parser.parse_args(argv)

    if args.print_prompts:
        sys.stdout.write(PROMPT_SCRIPT)
        return 0
    if args.show_prefs:
        print(json.dumps(load_prefs(), ensure_ascii=False, indent=2))
        return 0

    record = run_intake(
        question=args.question,
        depth=args.depth,
        enhancements=args.enhancement,
        domain=args.domain,
        assume_yes=args.yes,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0
