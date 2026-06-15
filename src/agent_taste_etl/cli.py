from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .etl import run_pipeline, write_result
from .evaluate import assert_thresholds, evaluate_files
from .io import load_chat_history

DEFAULT_INPUT = Path("examples/chat_history.json")
DEFAULT_GOLDEN = Path("examples/golden_signals.jsonl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="taste-etl")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run ETL on a chat history file.")
    run_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    run_parser.add_argument("--out", type=Path, default=Path("out/sample"))

    eval_parser = subparsers.add_parser("evaluate", help="Evaluate predicted signals against golden signals.")
    eval_parser.add_argument("--predictions", type=Path, required=True)
    eval_parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)

    verify_parser = subparsers.add_parser("verify", help="Run ETL and enforce quality thresholds.")
    verify_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    verify_parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    verify_parser.add_argument("--out", type=Path, default=Path("out/verify"))
    verify_parser.add_argument("--min-f1", type=float, default=0.8)
    verify_parser.add_argument("--max-hallucination-rate", type=float, default=0.2)

    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_pipeline(load_chat_history(args.input))
        write_result(result, args.out)
        print(json.dumps(result.manifest, indent=2, sort_keys=True))
        return 0
    if args.command == "evaluate":
        result = evaluate_files(args.predictions, args.golden)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "verify":
        pipeline_result = run_pipeline(load_chat_history(args.input))
        write_result(pipeline_result, args.out)
        evaluation = evaluate_files(args.out / "signals.jsonl", args.golden)
        assert_thresholds(evaluation, args.min_f1, args.max_hallucination_rate)
        print(json.dumps({"manifest": pipeline_result.manifest, "evaluation": evaluation.to_dict()}, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

