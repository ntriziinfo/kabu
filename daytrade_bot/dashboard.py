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
from .health import build_health_report
from .market_calendar import market_status
from .market_test_report import build_market_test_report
from .netstock_highspeed import get_status
from .paper_execution import CONFIRM_FILE
from .paper_summary import build_paper_summary


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
STOP_FILE = ROOT / "STOP_TRADING"
MONITOR_PID_FILE = DATA_DIR / "monitor.pid"
MONITOR_STATUS_FILE = DATA_DIR / "monitor_status.json"
MONITOR_SETTINGS_FILE = DATA_DIR / "monitor_settings.json"
PRICE_FILE = DATA_DIR / "runtime_prices.csv"
DEMO_PRICE_FILE = DATA_DIR / "latest_prices.csv"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_MONITOR_SETTINGS: dict[str, object] = {
    "mode": "demo",
    "interval": 60,
    "delay": 1.5,
    "retries": 2,
    "timeout": 10,
    "min_score": 2.2,
    "max_notional": 500000,
    "lot_size": 100,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "max_daily_loss": 10000,
    "max_trades_per_day": 10,
    "max_losing_streak": 3,
    "require_confirmation": True,
    "paper_auto_execute": True,
}


HTML = r"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>株 自動売買ダッシュボード</title>
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
    input, select {
      height: 32px;
      min-width: 120px;
      border: 1px solid #b8c2d0;
      border-radius: 6px;
      padding: 0 8px;
      background: #fff;
      color: var(--ink);
    }
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
    <h1>株 自動売買ダッシュボード</h1>
    <div class="actions">
      <button class="primary" onclick="postAction('/api/yahoo-demo')">Yahooデモ取得</button>
      <button class="primary" onclick="postAction('/api/scan-candidates')">候補スキャン</button>
      <button onclick="postAction('/api/live-scan-candidates')">実データ取得</button>
      <button onclick="postAction('/api/update-prices')">株価更新</button>
      <button class="primary" onclick="postAction('/api/build-trade-plan')">注文案作成</button>
      <button onclick="postAction('/api/confirm-paper-orders')">紙注文を確認</button>
      <button class="primary" onclick="postAction('/api/execute-paper-orders')">紙トレード実行</button>
      <button class="primary" onclick="postAction('/api/live-paper-autopilot')">市場テスト実行</button>
      <button class="primary" onclick="postAction('/api/start-monitor')">監視開始</button>
      <button onclick="postAction('/api/stop-monitor')">監視停止</button>
      <button class="primary" onclick="postAction('/api/backtest')">検証実行</button>
      <button class="danger" onclick="postAction('/api/stop')">全停止</button>
      <button onclick="postAction('/api/clear-stop')">停止解除</button>
    </div>
  </header>
  <main>
    <div class="stack">
      <section>
        <div class="panel-title">システム <span id="stop-pill" class="pill">...</span></div>
        <div class="panel-body stack">
          <div class="row"><span class="label">NetStock</span><span id="netstock" class="value">...</span></div>
          <div class="row"><span class="label">市場</span><span id="market" class="value">...</span></div>
          <div class="row"><span class="label">監視</span><span id="monitor" class="value">...</span></div>
          <div class="row"><span class="label">最終更新</span><span id="monitor-cycle" class="value">...</span></div>
          <div class="row"><span class="label">実行ファイル</span><span id="exe" class="value">...</span></div>
          <div class="row"><span class="label">画面更新</span><span id="updated" class="value">...</span></div>
        </div>
      </section>
      <section>
        <div class="panel-title">操作ログ</div>
        <div class="panel-body"><code id="message">準備完了</code></div>
      </section>
      <section>
        <div class="panel-title">運用警告 <span id="health-pill" class="pill">...</span></div>
        <div class="panel-body">
          <table>
            <thead><tr><th>種類</th><th>内容</th></tr></thead>
            <tbody id="health"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">監視設定</div>
        <div class="panel-body stack">
          <div class="row"><span class="label">モード</span><select id="setting-mode"><option value="demo">デモ</option><option value="live">実データ</option></select></div>
          <div class="row"><span class="label">監視間隔 秒</span><input id="setting-interval" type="number" min="10" step="5"></div>
          <div class="row"><span class="label">取得待ち 秒</span><input id="setting-delay" type="number" min="0" step="0.5"></div>
          <div class="row"><span class="label">再試行</span><input id="setting-retries" type="number" min="0" step="1"></div>
          <div class="row"><span class="label">タイムアウト 秒</span><input id="setting-timeout" type="number" min="3" step="1"></div>
          <div class="row"><span class="label">最低材料点</span><input id="setting-min-score" type="number" min="0" step="0.1"></div>
          <div class="row"><span class="label">1銘柄上限 円</span><input id="setting-max-notional" type="number" min="10000" step="10000"></div>
          <div class="row"><span class="label">損切り %</span><input id="setting-stop-loss-pct" type="number" min="0.1" step="0.1"></div>
          <div class="row"><span class="label">利確 %</span><input id="setting-take-profit-pct" type="number" min="0.1" step="0.1"></div>
          <div class="row"><span class="label">日次損失上限 円</span><input id="setting-max-daily-loss" type="number" min="1000" step="1000"></div>
          <div class="row"><span class="label">1日取引上限</span><input id="setting-max-trades" type="number" min="1" step="1"></div>
          <div class="row"><span class="label">連敗停止</span><input id="setting-max-losing-streak" type="number" min="1" step="1"></div>
          <div class="row"><span class="label">紙自動処理</span><input id="setting-paper-auto-execute" type="checkbox"></div>
          <div class="row"><span class="label">実行前確認</span><input id="setting-require-confirmation" type="checkbox"></div>
          <div class="actions"><button onclick="saveMonitorSettings()">設定保存</button></div>
        </div>
      </section>
      <section>
        <div class="panel-title">根拠ニュース</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>時刻</th><th>銘柄</th><th>情報元</th><th>タイトル</th><th>信頼度</th></tr></thead>
            <tbody id="evidence"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">最新株価</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>時刻</th><th>銘柄</th><th>名前</th><th>株価</th><th>取得元</th></tr></thead>
            <tbody id="prices"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">取得失敗</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>時刻</th><th>銘柄</th><th>名前</th><th>エラー</th></tr></thead>
            <tbody id="failures"></tbody>
          </table>
        </div>
      </section>
    </div>
    <div class="stack">
      <section>
        <div class="panel-title">検証結果</div>
        <div class="panel-body">
          <div class="grid" id="metrics"></div>
        </div>
      </section>
      <section>
        <div class="panel-title">売買候補</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>銘柄</th><th>名前</th><th>判断</th><th>点数</th><th>件数</th><th>理由</th><th>主な材料</th></tr></thead>
            <tbody id="candidates"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">注文案</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>銘柄</th><th>名前</th><th>状態</th><th>売買</th><th>点数</th><th>株価</th><th>数量</th><th>概算金額</th><th>損切り</th><th>利確</th><th>想定損失</th><th>制限理由</th></tr></thead>
            <tbody id="trade-plan"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">最近のシグナル</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>時刻</th><th>銘柄</th><th>イベント</th><th>判断</th><th>理由</th><th>根拠点</th></tr></thead>
            <tbody id="events"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">紙トレード状況</div>
        <div class="panel-body">
          <div class="grid" id="paper-metrics"></div>
        </div>
      </section>
      <section>
        <div class="panel-title">市場テスト状態</div>
        <div class="panel-body">
          <div class="grid" id="market-test-metrics"></div>
        </div>
      </section>
      <section>
        <div class="panel-title">保有中の紙ポジション</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>銘柄</th><th>名前</th><th>数量</th><th>建値</th><th>損切り</th><th>利確</th><th>想定損失</th><th>理由</th></tr></thead>
            <tbody id="paper-positions"></tbody>
          </table>
        </div>
      </section>
      <section>
        <div class="panel-title">紙トレード履歴</div>
        <div class="panel-body">
          <table>
            <thead><tr><th>時刻</th><th>銘柄</th><th>名前</th><th>売買</th><th>状態</th><th>数量</th><th>価格</th><th>損益</th><th>理由</th></tr></thead>
            <tbody id="paper-orders"></tbody>
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
      document.getElementById('netstock').textContent = data.netstock.is_running ? '起動中' : '未起動';
      document.getElementById('market').textContent = data.market.is_open ? `立会中 ${translate(data.market.phase)}` : translate(data.market.message);
      document.getElementById('monitor').textContent = data.monitor.running ? `監視中 (${translate(data.monitor.mode || 'unknown')})` : '停止中';
      document.getElementById('monitor-cycle').textContent = data.monitor.last_cycle_at || data.monitor.message || '-';
      renderSettings(data.settings);
      document.getElementById('exe').textContent = data.netstock.exe_exists ? data.netstock.exe_path : '見つかりません';
      const stop = document.getElementById('stop-pill');
      stop.textContent = data.stop_trading ? '停止中' : '稼働可';
      stop.className = 'pill ' + (data.stop_trading ? 'sell' : 'buy');
      renderMetrics(data.summary);
      renderCandidates(data.candidates);
      renderTradePlan(data.trade_plan);
      renderEvents(data.events);
      renderEvidence(data.evidence);
      renderFailures(data.failures);
      renderPrices(data.prices);
      renderHealth(data.health);
      renderPaperMetrics(data.paper_state, data.paper_confirmation);
      renderPaperSummary(data.paper_summary);
      renderMarketTest(data.market_test);
      renderPaperPositions(data.paper_positions);
      renderPaperOrders(data.paper_orders);
    }
    function renderMetrics(summary) {
      const labels = {
        closed_trades: '決済数',
        wins: '勝ち',
        losses: '負け',
        win_rate_pct: '勝率',
        realized_pnl: '損益',
        average_win: '平均利益',
        average_loss: '平均損失',
        max_drawdown: '最大下落'
      };
      document.getElementById('metrics').innerHTML = Object.entries(labels).map(([key, label]) => {
        const value = summary[key] ?? 0;
        return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
      }).join('');
    }
    function renderSettings(settings) {
      document.getElementById('setting-mode').value = settings.mode || 'demo';
      document.getElementById('setting-interval').value = settings.interval ?? 60;
      document.getElementById('setting-delay').value = settings.delay ?? 1.5;
      document.getElementById('setting-retries').value = settings.retries ?? 2;
      document.getElementById('setting-timeout').value = settings.timeout ?? 10;
      document.getElementById('setting-min-score').value = settings.min_score ?? 2.2;
      document.getElementById('setting-max-notional').value = settings.max_notional ?? 500000;
      document.getElementById('setting-stop-loss-pct').value = Math.round((settings.stop_loss_pct ?? 0.02) * 1000) / 10;
      document.getElementById('setting-take-profit-pct').value = Math.round((settings.take_profit_pct ?? 0.04) * 1000) / 10;
      document.getElementById('setting-max-daily-loss').value = settings.max_daily_loss ?? 10000;
      document.getElementById('setting-max-trades').value = settings.max_trades_per_day ?? 10;
      document.getElementById('setting-max-losing-streak').value = settings.max_losing_streak ?? 3;
      document.getElementById('setting-paper-auto-execute').checked = settings.paper_auto_execute !== false;
      document.getElementById('setting-require-confirmation').checked = settings.require_confirmation !== false;
    }
    function renderCandidates(items) {
      document.getElementById('candidates').innerHTML = items.map(row => {
        const cls = row.action === 'buy' ? 'buy' : row.action === 'sell' ? 'sell' : '';
        return `<tr><td>${row.symbol}</td><td>${row.name}</td><td><span class="pill ${cls}">${translate(row.action)}</span></td><td class="num">${row.score}</td><td class="num">${row.evidence_count}</td><td>${translate(row.reason)}</td><td>${row.top_titles}</td></tr>`;
      }).join('');
    }
    function renderTradePlan(items) {
      document.getElementById('trade-plan').innerHTML = items.map(row => {
        const cls = row.status === 'ready' ? 'buy' : 'warn';
        return `<tr><td>${row.symbol}</td><td>${row.name}</td><td><span class="pill ${cls}">${translate(row.status)}</span></td><td>${translate(row.side)}</td><td class="num">${row.score}</td><td class="num">${row.price}</td><td class="num">${row.quantity}</td><td class="num">${row.estimated_notional}</td><td class="num">${row.stop_loss_price || ''}</td><td class="num">${row.take_profit_price || ''}</td><td class="num">${row.risk_amount || ''}</td><td>${translate(row.block_reason)}</td></tr>`;
      }).join('');
    }
    function renderEvents(events) {
      document.getElementById('events').innerHTML = events.map(row => {
        const cls = row.action === 'buy' ? 'buy' : row.action === 'sell' ? 'sell' : '';
        return `<tr><td>${row.timestamp}</td><td>${row.symbol}</td><td>${translate(row.event)}</td><td><span class="pill ${cls}">${translate(row.action || row.side || '-')}</span></td><td>${translate(row.reason || '')}</td><td class="num">${row.evidence_score || row.score || ''}</td></tr>`;
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
    function renderPrices(items) {
      document.getElementById('prices').innerHTML = items.map(row => {
        return `<tr><td>${row.timestamp || ''}</td><td>${row.symbol}</td><td>${row.name || ''}</td><td class="num">${row.price}</td><td>${translate(row.source || '')}</td></tr>`;
      }).join('');
    }
    function renderHealth(health) {
      const pill = document.getElementById('health-pill');
      pill.textContent = translate(health.status || 'ok');
      pill.className = 'pill ' + (health.status === 'error' ? 'sell' : health.status === 'warn' ? 'warn' : 'buy');
      const rows = health.warnings && health.warnings.length ? health.warnings : [{ level: 'ok', message: '問題なし' }];
      document.getElementById('health').innerHTML = rows.map(row => {
        return `<tr><td><span class="pill ${row.level === 'error' ? 'sell' : row.level === 'warn' ? 'warn' : 'buy'}">${translate(row.level)}</span></td><td>${row.message}</td></tr>`;
      }).join('');
    }
    function renderPaperMetrics(state, confirmation) {
      const rows = [
        ['日付', state.date || '-'],
        ['実現損益', state.realized_pnl ?? 0],
        ['取引数', state.trade_count ?? 0],
        ['連敗数', state.losing_streak ?? 0],
        ['確認状態', confirmation ? '確認済み' : '未確認'],
        ['状態', state.last_message || '-']
      ];
      document.getElementById('paper-metrics').innerHTML = rows.map(([label, value]) => {
        return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
      }).join('');
    }
    function renderPaperSummary(summary) {
      const rows = [
        ['保有数', summary.position_count ?? 0],
        ['保有株数', summary.total_quantity ?? 0],
        ['投下金額', summary.cost_basis ?? 0],
        ['時価評価', summary.market_value ?? 0],
        ['含み損益', summary.unrealized_pnl ?? 0],
        ['合計損益', summary.total_pnl ?? 0],
        ['想定損失', summary.total_risk_amount ?? 0],
        ['紙勝率', `${summary.win_rate_pct ?? 0}%`]
      ];
      document.getElementById('paper-metrics').innerHTML += rows.map(([label, value]) => {
        return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
      }).join('');
    }
    function renderMarketTest(report) {
      const counts = report.counts || {};
      const summary = report.paper_summary || {};
      const runner = report.runner_status || {};
      const rows = [
        ['状態', translate(report.status || 'unknown')],
        ['停止フラグ', report.stop_trading ? 'あり' : 'なし'],
        ['周回数', runner.cycles ?? 0],
        ['候補', counts.candidates ?? 0],
        ['材料', counts.evidence ?? 0],
        ['価格', counts.prices ?? 0],
        ['注文案', counts.trade_plan ?? 0],
        ['紙ポジション', summary.position_count ?? 0],
        ['市場テストPnL', summary.total_pnl ?? 0],
        ['最終状態', translate(runner.message || '-')]
      ];
      document.getElementById('market-test-metrics').innerHTML = rows.map(([label, value]) => {
        return `<div class="metric"><div class="label">${label}</div><div class="value">${value}</div></div>`;
      }).join('');
    }
    function renderPaperPositions(items) {
      document.getElementById('paper-positions').innerHTML = items.map(row => {
        return `<tr><td>${row.symbol}</td><td>${row.name}</td><td class="num">${row.quantity}</td><td class="num">${row.entry_price}</td><td class="num">${row.stop_loss_price}</td><td class="num">${row.take_profit_price}</td><td class="num">${row.risk_amount}</td><td>${translate(row.reason)}</td></tr>`;
      }).join('');
    }
    function renderPaperOrders(items) {
      document.getElementById('paper-orders').innerHTML = items.map(row => {
        return `<tr><td>${row.timestamp}</td><td>${row.symbol}</td><td>${row.name}</td><td>${row.side}</td><td>${row.status}</td><td class="num">${row.quantity}</td><td class="num">${row.price}</td><td class="num">${row.realized_pnl}</td><td>${translate(row.reason)}</td></tr>`;
      }).join('');
    }
    async function postAction(path) {
      const msg = document.getElementById('message');
      msg.textContent = '実行中: ' + path;
      const res = await fetch(path, { method: 'POST' });
      const data = await res.json();
      msg.textContent = data.message || JSON.stringify(data);
      await loadState();
    }
    async function saveMonitorSettings() {
      const payload = {
        mode: document.getElementById('setting-mode').value,
        interval: Number(document.getElementById('setting-interval').value),
        delay: Number(document.getElementById('setting-delay').value),
        retries: Number(document.getElementById('setting-retries').value),
        timeout: Number(document.getElementById('setting-timeout').value),
        min_score: Number(document.getElementById('setting-min-score').value),
        max_notional: Number(document.getElementById('setting-max-notional').value),
        stop_loss_pct: Number(document.getElementById('setting-stop-loss-pct').value) / 100,
        take_profit_pct: Number(document.getElementById('setting-take-profit-pct').value) / 100,
        max_daily_loss: Number(document.getElementById('setting-max-daily-loss').value),
        max_trades_per_day: Number(document.getElementById('setting-max-trades').value),
        max_losing_streak: Number(document.getElementById('setting-max-losing-streak').value),
        paper_auto_execute: document.getElementById('setting-paper-auto-execute').checked,
        require_confirmation: document.getElementById('setting-require-confirmation').checked
      };
      const msg = document.getElementById('message');
      msg.textContent = '設定を保存中';
      const res = await fetch('/api/save-monitor-settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      msg.textContent = data.message || JSON.stringify(data);
      await loadState();
    }
    function translate(value) {
      const labels = {
        demo: 'デモ',
        live: '実データ',
        unknown: '不明',
        morning: '前場',
        afternoon: '後場',
        pre_open: '寄付き前',
        lunch_break: '昼休み',
        closed: '時間外',
        holiday: '休業日',
        market_open_morning: '前場の立会時間中',
        market_open_afternoon: '後場の立会時間中',
        before_market_open: '立会開始前',
        after_market_close: '立会時間外',
        market_holiday: '休業日',
        buy: '買い',
        sell: '売り',
        hold: '見送り',
        ready: '発注候補',
        blocked: '見送り',
        ok: '問題なし',
        not_buy_candidate: '買い候補ではない',
        score_below_threshold: '点数不足',
        missing_price: '株価未取得',
        max_notional_too_low: '資金上限不足',
        price_not_realtime: 'リアルタイム価格ではない',
        stale_realtime_price: 'リアルタイム価格が古い',
        positive_evidence_cluster: '好材料が集中',
        negative_evidence_cluster: '悪材料が集中',
        insufficient_evidence_score: '材料点が不足',
        price_signal: '価格シグナル',
        evidence_signal: '材料シグナル',
        combined_signal: '総合判断',
        risk_check: 'リスク確認',
        fill: '約定',
        blocked_by_insufficient_evidence: '材料不足で見送り',
        opening_range_vwap_volume_breakout: '寄付き高値・VWAP・出来高を突破',
        force_exit_before_close: '引け前の強制決済',
        take_profit: '利確',
        stop_loss: '損切り',
        trailing_stop: '追跡損切り',
        yahoo: 'Yahoo',
        ok: '正常',
        warn: '注意',
        error: '異常',
        info: '情報',
        holding_position: '保有中',
        building_opening_range: '寄付きレンジ形成中',
        entry_window_closed: 'エントリー時間外',
        one_trade_limit: '1銘柄1回制限',
        insufficient_session_stats: '場中データ不足',
        no_edge: '優位性なし'
      };
      return labels[value] || value || '';
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


def prefer_market_file(market_path: Path, fallback_path: Path) -> Path:
    if not market_path.exists():
        return fallback_path
    if not fallback_path.exists():
        return market_path
    return market_path if market_path.stat().st_mtime >= fallback_path.stat().st_mtime else fallback_path


def monitor_settings() -> dict[str, object]:
    settings = dict(DEFAULT_MONITOR_SETTINGS)
    settings.update(read_json_file(MONITOR_SETTINGS_FILE))
    settings["mode"] = "live" if settings.get("mode") == "live" else "demo"
    settings["interval"] = max(10, int(float(settings.get("interval", 60))))
    settings["delay"] = max(0.0, float(settings.get("delay", 1.5)))
    settings["retries"] = max(0, int(float(settings.get("retries", 2))))
    settings["timeout"] = max(3.0, float(settings.get("timeout", 10)))
    settings["min_score"] = max(0.0, float(settings.get("min_score", 2.2)))
    settings["max_notional"] = max(10000.0, float(settings.get("max_notional", 500000)))
    settings["lot_size"] = max(1, int(float(settings.get("lot_size", 100))))
    settings["stop_loss_pct"] = max(0.001, float(settings.get("stop_loss_pct", 0.02)))
    settings["take_profit_pct"] = max(0.001, float(settings.get("take_profit_pct", 0.04)))
    settings["max_daily_loss"] = max(1000.0, float(settings.get("max_daily_loss", 10000)))
    settings["max_trades_per_day"] = max(1, int(float(settings.get("max_trades_per_day", 10))))
    settings["max_losing_streak"] = max(1, int(float(settings.get("max_losing_streak", 3))))
    settings["require_confirmation"] = bool(settings.get("require_confirmation", True))
    settings["paper_auto_execute"] = bool(settings.get("paper_auto_execute", True))
    return settings


def save_monitor_settings(values: dict[str, object]) -> dict[str, object]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = monitor_settings()
    for key in (
        "mode",
        "interval",
        "delay",
        "retries",
        "timeout",
        "min_score",
        "max_notional",
        "lot_size",
        "stop_loss_pct",
        "take_profit_pct",
        "max_daily_loss",
        "max_trades_per_day",
        "max_losing_streak",
        "require_confirmation",
        "paper_auto_execute",
    ):
        if key in values:
            current[key] = values[key]
    normalized = monitor_settings_from_values(current)
    MONITOR_SETTINGS_FILE.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def monitor_settings_from_values(values: dict[str, object]) -> dict[str, object]:
    return {
        "mode": "live" if values.get("mode") == "live" else "demo",
        "interval": max(10, int(float(values.get("interval", 60)))),
        "delay": max(0.0, float(values.get("delay", 1.5))),
        "retries": max(0, int(float(values.get("retries", 2)))),
        "timeout": max(3.0, float(values.get("timeout", 10))),
        "min_score": max(0.0, float(values.get("min_score", 2.2))),
        "max_notional": max(10000.0, float(values.get("max_notional", 500000))),
        "lot_size": max(1, int(float(values.get("lot_size", 100)))),
        "stop_loss_pct": max(0.001, float(values.get("stop_loss_pct", 0.02))),
        "take_profit_pct": max(0.001, float(values.get("take_profit_pct", 0.04))),
        "max_daily_loss": max(1000.0, float(values.get("max_daily_loss", 10000))),
        "max_trades_per_day": max(1, int(float(values.get("max_trades_per_day", 10)))),
        "max_losing_streak": max(1, int(float(values.get("max_losing_streak", 3)))),
        "require_confirmation": bool(values.get("require_confirmation", True)),
        "paper_auto_execute": bool(values.get("paper_auto_execute", True)),
    }


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


def start_monitor_process() -> dict[str, object]:
    pid = read_monitor_pid()
    if is_pid_running(pid):
        return {"ok": True, "message": f"監視はすでに起動中です pid={pid}"}

    settings = monitor_settings()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        "-m",
        "daytrade_bot.monitor",
        "--symbols",
        str(DATA_DIR / "symbols.csv"),
        "--interval",
        str(settings["interval"]),
        "--delay",
        str(settings["delay"]),
        "--retries",
        str(settings["retries"]),
        "--timeout",
        str(settings["timeout"]),
        "--evidence-output",
        str(DATA_DIR / "scan_evidence.csv"),
        "--candidates-output",
        str(DATA_DIR / "candidates.csv"),
        "--failures-output",
        str(DATA_DIR / "scan_failures.csv"),
        "--prices",
        str(PRICE_FILE),
        "--demo-prices",
        str(DEMO_PRICE_FILE),
        "--trade-plan-output",
        str(DATA_DIR / "trade_plan.csv"),
        "--update-prices",
        "--price-source",
        "yahoo" if settings["mode"] == "demo" else "netstock_csv",
        "--netstock-price-csv",
        str(DATA_DIR / "netstock_export.csv"),
        "--stop-loss-pct",
        str(settings["stop_loss_pct"]),
        "--take-profit-pct",
        str(settings["take_profit_pct"]),
        "--min-score",
        str(settings["min_score"]),
        "--max-notional",
        str(settings["max_notional"]),
        "--lot-size",
        str(settings["lot_size"]),
        "--max-daily-loss",
        str(settings["max_daily_loss"]),
        "--max-trades-per-day",
        str(settings["max_trades_per_day"]),
        "--max-losing-streak",
        str(settings["max_losing_streak"]),
    ]
    if settings["paper_auto_execute"]:
        args.append("--paper-execute")
    if not settings["require_confirmation"]:
        args.append("--paper-no-confirmation-required")
    if settings["mode"] == "demo":
        args.extend(["--demo", "--fetched-at", "2026-07-08T09:12:00"])
    else:
        args.extend(["--require-realtime-prices", "--max-realtime-price-age-seconds", "120"])

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        args,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    MONITOR_PID_FILE.write_text(str(process.pid), encoding="utf-8")
    return {"ok": True, "message": f"監視を開始しました pid={process.pid} mode={settings['mode']}"}


def stop_monitor_process() -> dict[str, object]:
    pid = read_monitor_pid()
    if not pid:
        return {"ok": True, "message": "監視は起動していません"}
    if is_pid_running(pid):
        os.kill(pid, signal.SIGTERM)
    if MONITOR_PID_FILE.exists():
        MONITOR_PID_FILE.unlink()
    status = read_json_file(MONITOR_STATUS_FILE)
    status.update({"running": False, "message": "ダッシュボードから監視停止"})
    MONITOR_STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "message": f"監視を停止しました pid={pid}"}


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
        if path == "/api/save-monitor-settings":
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                values = json.loads(raw_body)
            except json.JSONDecodeError:
                self.send_json({"ok": False, "message": "設定データが不正です"})
                return
            settings = save_monitor_settings(values)
            self.send_json({"ok": True, "message": "監視設定を保存しました", "settings": settings})
            return
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
            self.send_json(command_response(result, "Yahoo材料を更新しました"))
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
            self.send_json(command_response(result, "候補スキャンが完了しました"))
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
            self.send_json(command_response(result, "実データの候補スキャンが完了しました"))
            return
        if path == "/api/update-prices":
            settings = monitor_settings()
            if settings["mode"] == "demo":
                price_args = [
                    "--symbols",
                    str(DATA_DIR / "symbols.csv"),
                    "--output",
                    str(PRICE_FILE),
                    "--delay",
                    str(settings["delay"]),
                    "--timeout",
                    str(settings["timeout"]),
                ]
                price_args.extend(["--demo", "--demo-prices", str(DEMO_PRICE_FILE)])
                result = run_module("daytrade_bot.yahoo_prices", price_args)
            else:
                price_args = [
                    "--input",
                    str(DATA_DIR / "netstock_export.csv"),
                    "--output",
                    str(PRICE_FILE),
                    "--symbols",
                    str(DATA_DIR / "symbols.csv"),
                ]
                result = run_module("daytrade_bot.netstock_prices", price_args)
            self.send_json(command_response(result, "株価を更新しました"))
            return
        if path == "/api/build-trade-plan":
            settings = monitor_settings()
            trade_plan_args = [
                "--candidates",
                str(DATA_DIR / "candidates.csv"),
                "--prices",
                str(PRICE_FILE),
                "--output",
                str(DATA_DIR / "trade_plan.csv"),
                "--min-score",
                str(settings["min_score"]),
                "--max-notional",
                str(settings["max_notional"]),
                "--lot-size",
                str(settings["lot_size"]),
                "--stop-loss-pct",
                str(settings["stop_loss_pct"]),
                "--take-profit-pct",
                str(settings["take_profit_pct"]),
            ]
            if settings["mode"] == "live":
                trade_plan_args.extend(["--require-realtime-prices", "--max-realtime-price-age-seconds", "120"])
            result = run_module(
                "daytrade_bot.trade_plan",
                trade_plan_args,
            )
            self.send_json(command_response(result, "注文案を作成しました"))
            return
        if path == "/api/start-monitor":
            self.send_json(start_monitor_process())
            return
        if path == "/api/confirm-paper-orders":
            CONFIRM_FILE.write_text("confirmed from dashboard\n", encoding="utf-8")
            self.send_json({"ok": True, "message": "紙注文を確認しました"})
            return
        if path == "/api/execute-paper-orders":
            settings = monitor_settings()
            paper_args = [
                "--trade-plan",
                str(DATA_DIR / "trade_plan.csv"),
                    "--prices",
                    str(PRICE_FILE),
                "--positions",
                str(DATA_DIR / "paper_positions.csv"),
                "--orders",
                str(DATA_DIR / "paper_orders.csv"),
                "--state",
                str(DATA_DIR / "paper_state.json"),
                "--max-daily-loss",
                str(settings["max_daily_loss"]),
                "--max-trades-per-day",
                str(settings["max_trades_per_day"]),
                "--max-losing-streak",
                str(settings["max_losing_streak"]),
            ]
            if not settings["require_confirmation"]:
                paper_args.append("--no-confirmation-required")
            result = run_module("daytrade_bot.paper_execution", paper_args)
            response = command_response(result, "紙トレード実行が完了しました")
            if result.returncode == 0 and result.stdout.strip():
                response["message"] = result.stdout.strip()
            self.send_json(response)
            return
        if path == "/api/live-paper-autopilot":
            result = run_module(
                "daytrade_bot.autopilot",
                [
                    "--live",
                    "--confirm-paper-orders",
                    "--require-market-open",
                    "--evidence-output",
                    str(DATA_DIR / "market_scan_evidence.csv"),
                    "--candidates-output",
                    str(DATA_DIR / "market_candidates.csv"),
                    "--failures-output",
                    str(DATA_DIR / "market_scan_failures.csv"),
                    "--prices",
                    str(DATA_DIR / "market_runtime_prices.csv"),
                    "--price-source",
                    "netstock_csv",
                    "--netstock-price-csv",
                    str(DATA_DIR / "netstock_export.csv"),
                    "--trade-plan",
                    str(DATA_DIR / "market_trade_plan.csv"),
                    "--paper-positions",
                    str(DATA_DIR / "market_paper_positions.csv"),
                    "--paper-orders",
                    str(DATA_DIR / "market_paper_orders.csv"),
                    "--paper-state",
                    str(DATA_DIR / "market_paper_state.json"),
                    "--report",
                    str(DATA_DIR / "market_autopilot_report.json"),
                    "--max-notional",
                    "300000",
                    "--max-realtime-price-age-seconds",
                    "120",
                    "--max-daily-loss",
                    "5000",
                    "--max-trades-per-day",
                    "3",
                    "--max-losing-streak",
                    "2",
                ],
            )
            response = command_response(result, "市場テストの紙トレードを実行しました")
            if result.stdout.strip():
                response["stdout"] = result.stdout.strip()
            self.send_json(response)
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
            self.send_json(command_response(result, "検証が完了しました"))
            return
        if path == "/api/stop":
            STOP_FILE.write_text("stop requested from dashboard\n", encoding="utf-8")
            self.send_json({"ok": True, "message": "全停止フラグを作成しました"})
            return
        if path == "/api/clear-stop":
            if STOP_FILE.exists():
                STOP_FILE.unlink()
            self.send_json({"ok": True, "message": "全停止フラグを解除しました"})
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
    return {"ok": False, "message": result.stderr or result.stdout or "コマンドに失敗しました"}


def build_state() -> dict[str, object]:
    status = get_status()
    monitor_status = read_json_file(MONITOR_STATUS_FILE)
    price_path = prefer_market_file(DATA_DIR / "market_runtime_prices.csv", PRICE_FILE if PRICE_FILE.exists() else DEMO_PRICE_FILE)
    trade_plan_path = prefer_market_file(DATA_DIR / "market_trade_plan.csv", DATA_DIR / "trade_plan.csv")
    candidates_path = prefer_market_file(DATA_DIR / "market_candidates.csv", DATA_DIR / "candidates.csv")
    failures_path = prefer_market_file(DATA_DIR / "market_scan_failures.csv", DATA_DIR / "scan_failures.csv")
    paper_positions_path = prefer_market_file(DATA_DIR / "market_paper_positions.csv", DATA_DIR / "paper_positions.csv")
    paper_orders_path = prefer_market_file(DATA_DIR / "market_paper_orders.csv", DATA_DIR / "paper_orders.csv")
    paper_state_path = DATA_DIR / "market_paper_state.json" if (DATA_DIR / "market_paper_state.json").exists() else DATA_DIR / "paper_state.json"
    paper_state = read_json_file(paper_state_path)
    paper_summary = build_paper_summary(
        paper_positions_path,
        paper_orders_path,
        price_path,
        paper_state_path,
    )
    market_test_report = build_market_test_report(DATA_DIR)
    health = build_health_report(
        failures_path,
        trade_plan_path,
        MONITOR_STATUS_FILE,
        paper_state_path,
        price_path,
    )
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
        "market": market_status(),
        "monitor": monitor_status,
        "settings": monitor_settings(),
        "summary": latest_summary(),
        "candidates": read_csv_rows(candidates_path, limit=20),
        "trade_plan": read_csv_rows(trade_plan_path, limit=20),
        "prices": read_csv_rows(price_path, limit=20),
        "health": health,
        "market_test": market_test_report,
        "paper_summary": paper_summary,
        "paper_state": {
            "date": paper_state.get("date", "-"),
            "realized_pnl": paper_state.get("realized_pnl", 0),
            "trade_count": paper_state.get("trade_count", 0),
            "losing_streak": paper_state.get("losing_streak", 0),
            "last_message": paper_state.get("last_message", "準備完了"),
        },
        "paper_confirmation": CONFIRM_FILE.exists(),
        "paper_positions": read_csv_rows(paper_positions_path, limit=20),
        "paper_orders": read_csv_rows(paper_orders_path, limit=20),
        "events": read_csv_rows(log_path, limit=14),
        "evidence": read_csv_rows(DATA_DIR / "yahoo_evidence.csv", limit=10),
        "failures": read_csv_rows(failures_path, limit=10),
    }


def main() -> None:
    server = ThreadingHTTPServer((DEFAULT_HOST, DEFAULT_PORT), DashboardHandler)
    if sys.stdout:
        print(f"dashboard: http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
