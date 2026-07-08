from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "netstock_highspeed.json"


@dataclass(frozen=True)
class NetStockHighSpeedConfig:
    app_name: str
    exe_path: Path
    working_directory: Path
    process_name: str
    shortcut_path: Path
    live_trading_enabled: bool = False


@dataclass(frozen=True)
class NetStockHighSpeedStatus:
    exe_exists: bool
    shortcut_exists: bool
    is_running: bool
    exe_path: Path
    working_directory: Path
    process_name: str


def load_config(path: Path = DEFAULT_CONFIG) -> NetStockHighSpeedConfig:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return NetStockHighSpeedConfig(
        app_name=data["app_name"],
        exe_path=Path(data["exe_path"]),
        working_directory=Path(data["working_directory"]),
        process_name=data["process_name"],
        shortcut_path=Path(data["shortcut_path"]),
        live_trading_enabled=bool(data.get("live_trading_enabled", False)),
    )


def get_status(config: NetStockHighSpeedConfig | None = None) -> NetStockHighSpeedStatus:
    config = config or load_config()
    return NetStockHighSpeedStatus(
        exe_exists=config.exe_path.exists(),
        shortcut_exists=config.shortcut_path.exists(),
        is_running=_is_process_running(config.process_name),
        exe_path=config.exe_path,
        working_directory=config.working_directory,
        process_name=config.process_name,
    )


def launch(config: NetStockHighSpeedConfig | None = None) -> None:
    config = config or load_config()
    if not config.exe_path.exists():
        raise FileNotFoundError(f"NetStock High Speed executable was not found: {config.exe_path}")

    os.startfile(config.exe_path, cwd=config.working_directory)  # type: ignore[attr-defined]


def _is_process_running(process_name: str) -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    return process_name.lower() in result.stdout.lower()

