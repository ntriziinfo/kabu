from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from .netstock_highspeed import DEFAULT_CONFIG, get_status, launch, load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check or launch NetStock High Speed")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--launch", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)

    if args.launch:
        launch(config)

    status = get_status(config)
    for key, value in asdict(status).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

