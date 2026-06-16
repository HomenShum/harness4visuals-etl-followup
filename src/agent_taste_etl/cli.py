from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .etl import run_pipeline, write_result
from .evaluate import assert_thresholds, evaluate_files
from .integrations import DEFAULT_PIONEER_BASE_MODEL, build_clickhouse_rows, write_clickhouse_export, write_pioneer_export
from .io import load_chat_history
from .omnigent import load_omnigent_chat_history, write_omnigent_chat_history

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

    clickhouse_parser = subparsers.add_parser("export-clickhouse", help="Run ETL and write ClickHouse JSONEachRow import files.")
    clickhouse_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    clickhouse_parser.add_argument("--out", type=Path, default=Path("out/clickhouse"))
    clickhouse_parser.add_argument("--conversation-id", default="conv_harness4visuals_followup")
    clickhouse_parser.add_argument("--user-id", default="user_demo")
    clickhouse_parser.add_argument("--dataset-name", default="harness4visuals_preference_sft")

    pioneer_parser = subparsers.add_parser("export-pioneer", help="Run ETL and write Pioneer/Fastino decoder SFT artifacts.")
    pioneer_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    pioneer_parser.add_argument("--out", type=Path, default=Path("out/pioneer"))
    pioneer_parser.add_argument("--dataset-name", default="harness4visuals_preference_sft")
    pioneer_parser.add_argument("--model-name", default="harness4visuals-preference-prompt-adapter")
    pioneer_parser.add_argument("--base-model", default=DEFAULT_PIONEER_BASE_MODEL)

    omnigent_parser = subparsers.add_parser("normalize-omnigent", help="Convert Omnigent session events into ETL chat history.")
    omnigent_parser.add_argument("--input", type=Path, required=True)
    omnigent_parser.add_argument("--out", type=Path, default=Path("out/omnigent/chat_history.json"))

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
    if args.command == "export-clickhouse":
        pipeline_result = run_pipeline(load_chat_history(args.input))
        rows = build_clickhouse_rows(
            pipeline_result,
            conversation_id=args.conversation_id,
            user_id=args.user_id,
            dataset_name=args.dataset_name,
        )
        write_clickhouse_export(rows, args.out)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "files": {name: len(file_rows) for name, file_rows in rows.items()},
                    "run_fingerprint": pipeline_result.manifest["run_fingerprint"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "export-pioneer":
        pipeline_result = run_pipeline(load_chat_history(args.input))
        write_pioneer_export(
            pipeline_result,
            args.out,
            dataset_name=args.dataset_name,
            model_name=args.model_name,
            base_model=args.base_model,
        )
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "dataset_name": args.dataset_name,
                    "model_name": args.model_name,
                    "base_model": args.base_model,
                    "run_fingerprint": pipeline_result.manifest["run_fingerprint"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "normalize-omnigent":
        chat_history = load_omnigent_chat_history(args.input)
        write_omnigent_chat_history(chat_history, args.out)
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "conversation_id": chat_history["conversation_id"],
                    "message_count": len(chat_history["messages"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
