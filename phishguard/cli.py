"""Command line interface for PhishGuard."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

from . import __version__
from .model import evaluate_model, train_model
from .predict import predict, predict_from_file

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PhishGuard phishing detector")
    parser.add_argument("--version", action="version", version=f"PhishGuard {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser("train", help="Train the phishing model")
    train_parser.add_argument("--data", type=Path, default=Path("data/emails.csv"))

    eval_parser = subparsers.add_parser("evaluate", help="Evaluate the trained model")
    eval_parser.add_argument("--data", type=Path, default=Path("data/emails.csv"))

    predict_parser = subparsers.add_parser("predict", help="Predict a single email from CLI inputs")
    predict_parser.add_argument("--subject", required=True)
    predict_parser.add_argument("--body", required=True)
    predict_parser.add_argument("--from_address", required=True)
    predict_parser.add_argument("--to_address", default="")
    predict_parser.add_argument("--cc", default="")
    predict_parser.add_argument("--bcc", default="")
    predict_parser.add_argument("--received_at", default="")
    predict_parser.add_argument("--has_attachments", type=int, default=0)
    predict_parser.add_argument("--num_links", type=int, default=0)
    predict_parser.add_argument("--num_images", type=int, default=0)
    predict_parser.add_argument("--domain_reputation", type=float, default=0.5)
    predict_parser.add_argument("--spf_pass", type=int, default=1)
    predict_parser.add_argument("--dkim_pass", type=int, default=1)
    predict_parser.add_argument("--dmarc_pass", type=int, default=1)
    predict_parser.add_argument("--json", action="store_true", help="Output JSON")

    predict_file_parser = subparsers.add_parser("predict-file", help="Predict using an .eml file")
    predict_file_parser.add_argument("--path", type=Path, required=True)

    return parser.parse_args()


def handle_train(args: argparse.Namespace) -> None:
    artifacts, evaluation = train_model(args.data)
    LOGGER.info("Best model: %s", artifacts.model_name)
    LOGGER.info(
        "Test metrics: accuracy=%.3f precision=%.3f recall=%.3f f1=%.3f roc_auc=%.3f",
        evaluation.accuracy,
        evaluation.precision,
        evaluation.recall,
        evaluation.f1,
        evaluation.roc_auc,
    )
    LOGGER.info("Confusion matrix:\n%s", evaluation.confusion)


def handle_evaluate(args: argparse.Namespace) -> None:
    result = evaluate_model(args.data)
    LOGGER.info(
        "Evaluation: accuracy=%.3f precision=%.3f recall=%.3f f1=%.3f roc_auc=%.3f",
        result.accuracy,
        result.precision,
        result.recall,
        result.f1,
        result.roc_auc,
    )
    LOGGER.info("Confusion matrix:\n%s", result.confusion)


def handle_predict(args: argparse.Namespace) -> None:
    payload = {
        "subject": args.subject,
        "body": args.body,
        "from_address": args.from_address,
        "to_address": args.to_address,
        "cc": args.cc,
        "bcc": args.bcc,
        "received_at": args.received_at,
        "has_attachments": args.has_attachments,
        "num_links": args.num_links,
        "num_images": args.num_images,
        "domain_reputation": args.domain_reputation,
        "spf_pass": args.spf_pass,
        "dkim_pass": args.dkim_pass,
        "dmarc_pass": args.dmarc_pass,
    }
    result = predict([payload])[0]
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"label={result['label']} ml_prob={result['ml_prob']:.3f} "
            f"rule_score={result['rule_score']:.3f} final={result['final_score']:.3f}"
        )
        for reason in result["top_reasons"]:
            print(f" - {reason}")


def handle_predict_file(args: argparse.Namespace) -> None:
    result = predict_from_file(args.path)
    print(json.dumps(result, indent=2))


def main() -> None:
    args = _parse_args()
    command = args.command
    if command == "train":
        handle_train(args)
    elif command == "evaluate":
        handle_evaluate(args)
    elif command == "predict":
        handle_predict(args)
    elif command == "predict-file":
        handle_predict_file(args)
    else:  # pragma: no cover - defensive
        raise ValueError(f"Unknown command {command}")


if __name__ == "__main__":  # pragma: no cover
    main()
