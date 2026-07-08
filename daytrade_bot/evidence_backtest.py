from __future__ import annotations

import argparse
from pathlib import Path

from .evidence import EvidenceScorer, read_evidence
from .market import read_ticks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score evidence items against tick timestamps")
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scorer = EvidenceScorer()
    evidence_items = sorted(read_evidence(args.evidence), key=lambda item: item.timestamp)
    evidence_index = 0

    for tick in read_ticks(args.ticks):
        while evidence_index < len(evidence_items) and evidence_items[evidence_index].timestamp <= tick.timestamp:
            scorer.add(evidence_items[evidence_index])
            evidence_index += 1

        signal = scorer.signal_for(tick.symbol, tick.timestamp)
        if signal.evidence_count:
            print(
                f"{signal.timestamp.isoformat()} {signal.symbol} "
                f"action={signal.action.value} score={signal.score} "
                f"items={signal.evidence_count} reason={signal.reason}"
            )


if __name__ == "__main__":
    main()
