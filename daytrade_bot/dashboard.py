from __future__ import annotations

import csv
import json
import os
import signal
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .backtest import summarize
from .netstock_highspeed import get_status


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
STOP_FILE = ROOT / "STOP_TRADING"
MONITOR_PID_FILE = DATA_DIR / "monitor.pid"
MONITOR_STATUS_FILE = DATA_DIR / "monitor_status.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>kabu dashboard</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --surface: #fff;
      --line: #d9dee7;
      --text: #19202a;
      --muted: #637083;
      --buy: #087f5b;
      --sell: #c92a2a;
      --warn: #b7791f;
      --ink: #243043;
      --accent: #1264a3;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Yu Gothic UI", Meiryo, sans-serif;
      background: var(--bg);
      color: var(--text);
      letter-spacing: 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 22px;
      background: var(--surface);
      border-bottom: 1px solid var(--line);
    }
    h1 { margin: 0; font-size: 20px; font-weight: 700; }
    main {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 16px;
      padding: 16px;
      max-width: 1320px;
      margin: 0 auto;
    }
    section {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .panel-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
    }
    .panel-body { padding: 14px; }
    .stack { display: grid; gap: 12px; }
    .row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 30px;
      font-size: 14px;
    }
    .label { color: var(--muted); }
    .value {
      font-variant-numeric: tabular-nums;
      text-align: right;
      overflow-wrap: anywhere;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      height: 24px;
      padding: 0 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f9fafb;
      font-size: 12px;
      font-weight: 700;
    }
    .pill.buy { color: var(--buy); border-color: #b2dfcc; background: #eefaf5; }
    .pill.sell { color: var(--sell); border-color: #ffc9c9; background: #fff5f5; }
    .pill.warn { color: var(--warn); border-color: #f3d49b; background: #fff8e8; }
    button {
      height: 34px;
      padding: 0 12px;
      border: 1px solid #b8c2d0;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      font-weight: 700;
      cursor: pointer;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.danger { background: #c92a2a; border-color: #c92a2a; color: #fff; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 8px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th { color: var(--muted); font-weight: 700; background: #fbfcfe; }
    td.num { text-align: right; font-variant-numeric: tabular-nums; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 12px; }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 74px;
    }
    .metric .label { font-size: 12px; }
    .metric .value { margin-top: 8px; font-size: 20px; font-weight: 800; text-align: left; }
    code { font-family: Consolas, monospace; font-size: 12px; color: var(--muted); }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; padding: 10px; }
      .grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <h1>kabu dashboard</h1>
    <div class="actions">
      <button class="primary" onclick="postAction('/api/yahoo-demo')">Yahoo demo</button>
      <button class="primary" onclick="postAction('/api/scan-candidates')">Scan candidates</button>
      <button onclick="postAction('/api/live-scan-candidates')">Live scan</button>
      <button class="primary" onclick="postAction('/api/start-monitor')">Start monitor</button>
      <button onclick="postAction('/api/stop-monitor')">Stop monitor</button>
      <button class="primary" onclick="postAction('/api/backtest')">Backtest</button>
      <button class="danger" onclick="postAction('/api/stop')">Stop</button>
      <button onclick="postAction('/api/clear-stop')">Clear stop</button>
    </div>
  </header>
  <main>
    <div class="stack">
      <section>
        <div class="panel-title">System <span id="stop-pill" class="pill">...</span></div>
        <div class="panel-body stack">
          <div class="row"><span class="label">NetStock</span><span id="netstock" class="value">...</span></div>
          <div class="row"><span class="label">Monitor</span><span id="monitor" class="value">...</span></div>
          <div class="row"><span class="label">Last cycle</span><span id="monitor-cycle" class="value">...</span></div>
          <div class="row"><span class="label">Executable</span><span id="exe" class="value">...</span></div>
          <div class="row"><span class="label">Updated</span><span id="updated" class="value">...</span></div>
        </div>
      </section>
      <section>
        <div class="panel-title">Action log</div>
        <div class="panel-body"><code id="message">ready</code></div>
      </section>
      <section>
        <div class="panel-title">Evidence</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>Time</th><th>Symbol</th><th>Source</th><th>Title</th><th>Confidence</th></tr></thead>
            <tbody id="evidence"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">Fetch failures</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>Time</th><th>Symbol</th><th>Name</th><th>Error</th></tr></thead>
            <tbody id="failures"></tbody>
          </table>
        </div>
      </section>
    </div>
    <div class="stack">
      <section>
        <div class="panel-title">Backtest summary</div>
        <div class="panel-body">
          <div class="grid" id="metrics"></div>
        </div>
      </section>
      <section>
        <div class="panel-title">Candidates</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>Symbol</th><th>Name</th><th>Action</th><th>Score</th><th>Items</th><th>Reason</th><th>Top titles</th></tr></thead>
            <tbody id="candidates"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">Recent signals</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>Time</th><th>Symbol</th><th>Event</th><th>Action</th><th>Reason</th><th>Evidence</th></tr></thead>
            <tbody id="events"></tbody>
          </table>
        </div>
      </section>
    </div>
  </main>
  <script>
    async function loadState() {
      const res = await fetch('/api/state');
      const data = await res.json();
      document.getElementById('updated').textContent = data.updated_at;
      document.getElementById('netstock').textContent = data.netstock.is_running ? 'Running' : 'Not running';
      document.getElementById('monitor').textContent = data.monitor.running ? `Running (${data.monitor.mode || 'unknown'})` : 'Stopped';
      document.getElementById('monitor-cycle').textContent = data.monitor.last_cycle_at || data.monitor.message || '-';
      document.getElementById('exe').textContent = data.netstock.exe_exists ? data.netstock.exe_path : 'Not found';
      const stop = document.getElementById('stop-pill');
      stop.textContent = data.stop_trading ? 'Stopped' : 'Ready';
      stop.className = 'pill ' + (data.stop_trading ? 'sell' : 'buy');
      renderMetrics(data.summary);
      renderCandidates(data.candidates);
      renderEvents(data.events);
      renderEvidence(data.evidence);
      renderFailures(data.failures);
    }
    function renderMetrics(summary) {
      const labels = {
        closed_trades: 'Closed trades',
        wins: 'Wins',
        losses: 'Losses',
        win_rate_pct: 'Win rate',
        realized_pnl: 'Realized PnL',
        average_win: 'Average win',
        average_loss: 'Average loss',
        max_drawdown: 'Max DD'
      };
      document.getElementById('metrics').innerHTML = Object.entries(labels).map(([key, label]) => {
        const value = summary[key] ?? 0;
        return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
      }).join('');
    }
    function renderCandidates(items) {
      document.getElementById('candidates').innerHTML = items.map(row => {
        const cls = row.action === 'buy' ? 'buy' : row.action === 'sell' ? 'sell' : '';
        return `<tr><td>${row.symbol}</td><td>${row.name}</td><td><span class="pill ${cls}">${row.action}</span></td><td class="num">${row.score}</td><td class="num">${row.evidence_count}</td><td>${row.reason}</td><td>${row.top_titles}</td></tr>`;
      }).join('');
    }
    function renderEvents(events) {
      document.getElementById('events').innerHTML = events.map(row => {
        const cls = row.action === 'buy' ? 'buy' : row.action === 'sell' ? 'sell' : '';
        return `<tr><td>${row.timestamp}</td><td>${row.symbol}</td><td>${row.event}</td><td><span class="pill ${cls}">${row.action || row.side || '-'}</span></td><td>${row.reason || ''}</td><td class="num">${row.evidence_score || row.score || ''}</td></tr>`;
      }).join('');
    }
    function renderEvidence(items) {
      document.getElementById('evidence').innerHTML = items.map(row => {
        return `<tr><td>${row.timestamp}</td><td>${row.symbol}</td><td>${row.source}</td><td>${row.title}</td><td class="num">${row.confidence}</td></tr>`;
      }).join('');
    }
    function renderFailures(items) {
      document.getElementById('failures').innerHTML = items.map(row => {
        return `<tr><td>${row.timestamp}</td><td>${row.symbol}</td><td>${row.name}</td><td>${row.error}</td></tr>`;
      }).join('');
    }
    async function postAction(path) {
      const msg = document.getElementById('message');
      msg.textContent = 'running ' + path;
      const res = await fetch(path, { method: 'POST' });
      const data = await res.json();
      msg.textContent = data.message || JSON.stringify(data);
      await loadState();
    }
    loadState();
    setInterval(loadState, 5000);
  </script>
</body>
</html>"""


def latest_summary() -> dict[str, float | int]:
    candidates = [
        LOG_DIR / "dashboard_backtest_events.csv",
        LOG_DIR / "yahoo_backtest_events.csv",
        LOG_DIR / "backtest_events.csv",
    ]
    for path in candidates:
        if path.exists():
            return summarize(path)
    return {
        "closed_trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate_pct": 0.0,
        "realized_pnl": 0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "max_drawdown": 0.0,
    }


def read_csv_rows(path: Path, limit: int = 12) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-limit:]


def run_module(module: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def read_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_monitor_pid() -> int | None:
    if not MONITOR_PID_FILE.exists():
        return None
    try:
        return int(MONITOR_PID_FILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_monitor_process(demo: bool = True) -> dict[str, object]:
    pid = read_monitor_pid()
    if is_pid_running(pid):
        return {"ok": True, "message": f"Monitor already running pid={pid}"}

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        "-m",
        "daytrade_bot.monitor",
        "--symbols",
        str(DATA_DIR / "symbols.csv"),
        "--interval",
        "60",
        "--delay",
        "1.5",
        "--retries",
        "2",
        "--timeout",
        "10",
        "--evidence-output",
        str(DATA_DIR / "scan_evidence.csv"),
        "--candidates-output",
        str(DATA_DIR / "candidates.csv"),
        "--failures-output",
        str(DATA_DIR / "scan_failures.csv"),
    ]
    if demo:
        args.extend(["--demo", "--fetched-at", "2026-07-08T09:12:00"])

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    MONITOR_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return {"ok": True, "message": f"Monitor started pid={process.pid}"}


def stop_monitor_process() -> dict[str, object]:
    pid = read_monitor_pid()
    if not pid:
        return {"ok": True, "message": "Monitor was not running"}
    if is_pid_running(pid):
        os.kill(pid, signal.SIGTERM)
    if MONITOR_PID_FILE.exists():
        MONITOR_PID_FILE.unlink()
    status = read_json_file(MONITOR_STATUS_FILE)
    status.update({"running": False, "message": "monitor stopped from dashboard"})
    MONITOR_STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"Monitor stopped pid={pid}"}


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self.send_html(HTML)
            return
        if path == "/api/state":
            self.send_json(build_state())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/yahoo-demo":
            result = run_module(
                "daytrade_bot.yahoo_finance",
                [
                    "--symbol",
                    "7203",
                    "--html-file",
                    str(DATA_DIR / "sample_yahoo_finance_7203.html"),
                    "--fetched-at",
                    "2026-07-08T09:12:00",
                    "--overwrite",
                    "--output",
                    str(DATA_DIR / "yahoo_evidence.csv"),
                ],
            )
            self.send_json(command_response(result, "Yahoo evidence updated"))
            return
        if path == "/api/scan-candidates":
            result = run_module(
                "daytrade_bot.scanner",
                [
                    "--symbols",
                    str(DATA_DIR / "symbols.csv"),
                    "--demo",
                    "--fetched-at",
                    "2026-07-08T09:12:00",
                    "--evidence-output",
                    str(DATA_DIR / "scan_evidence.csv"),
                    "--candidates-output",
                    str(DATA_DIR / "candidates.csv"),
                    "--failures-output",
                    str(DATA_DIR / "scan_failures.csv"),
                ],
            )
            self.send_json(command_response(result, "Candidate scan finished"))
            return
        if path == "/api/live-scan-candidates":
            result = run_module(
                "daytrade_bot.scanner",
                [
                    "--symbols",
                    str(DATA_DIR / "symbols.csv"),
                    "--delay",
                    "1.5",
                    "--retries",
                    "2",
                    "--timeout",
                    "10",
                    "--evidence-output",
                    str(DATA_DIR / "scan_evidence.csv"),
                    "--candidates-output",
                    str(DATA_DIR / "candidates.csv"),
                    "--failures-output",
                    str(DATA_DIR / "scan_failures.csv"),
                ],
            )
            self.send_json(command_response(result, "Live candidate scan finished"))
            return
        if path == "/api/start-monitor":
            self.send_json(start_monitor_process(demo=True))
            return
        if path == "/api/stop-monitor":
            self.send_json(stop_monitor_process())
            return
        if path == "/api/backtest":
            result = run_module(
                "daytrade_bot.backtest",
                [
                    "--ticks",
                    str(DATA_DIR / "sample_ticks.csv"),
                    "--evidence",
                    str(DATA_DIR / "yahoo_evidence.csv"),
                    "--log",
                    str(LOG_DIR / "dashboard_backtest_events.csv"),
                ],
            )
            self.send_json(command_response(result, "Backtest finished"))
            return
        if path == "/api/stop":
            STOP_FILE.write_text("stop requested from dashboard\n", encoding="utf-8")
            self.send_json({"ok": True, "message": "STOP_TRADING created"})
            return
        if path == "/api/clear-stop":
            if STOP_FILE.exists():
                STOP_FILE.unlink()
            self.send_json({"ok": True, "message": "STOP_TRADING cleared"})
            return
        self.send_error(404)

    def send_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data: dict[str, object]) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def command_response(result: subprocess.CompletedProcess[str], success_message: str) -> dict[str, object]:
    if result.returncode == 0:
        return {"ok": True, "message": success_message, "stdout": result.stdout}
    return {"ok": False, "message": result.stderr or result.stdout or "command failed"}


def build_state() -> dict[str, object]:
    status = get_status()
    monitor_status = read_json_file(MONITOR_STATUS_FILE)
    monitor_pid = read_monitor_pid()
    monitor_running = is_pid_running(monitor_pid)
    monitor_status["running"] = monitor_running
    if monitor_pid:
        monitor_status["pid"] = monitor_pid
    log_path = LOG_DIR / "dashboard_backtest_events.csv"
    if not log_path.exists():
        log_path = LOG_DIR / "yahoo_backtest_events.csv"
    return {
        "updated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stop_trading": STOP_FILE.exists(),
        "netstock": {
            "exe_exists": status.exe_exists,
            "shortcut_exists": status.shortcut_exists,
            "is_running": status.is_running,
            "exe_path": str(status.exe_path),
        },
        "monitor": monitor_status,
        "summary": latest_summary(),
        "candidates": read_csv_rows(DATA_DIR / "candidates.csv", limit=20),
        "events": read_csv_rows(log_path, limit=14),
        "evidence": read_csv_rows(DATA_DIR / "yahoo_evidence.csv", limit=10),
        "failures": read_csv_rows(DATA_DIR / "scan_failures.csv", limit=10),
    }


def main() -> None:
    server = ThreadingHTTPServer((DEFAULT_HOST, DEFAULT_PORT), DashboardHandler)
    print(f"dashboard: http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
