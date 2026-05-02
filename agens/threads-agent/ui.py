"""
Threads 自動運用システム - Web UI (v2)
起動: python ui.py
ブラウザで http://localhost:5000 を開く
"""
import os
os.environ.pop("SSLKEYLOGFILE", None)
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
DATA_DIR = BASE_DIR / "data"

ACCOUNTS = {
    "account1": "あとむ（AI×医療）",
    "account2": "ゆな（セルフケア）",
    "account3": "ぺたろう（ペット×楽天）",
}

def get_data_dir(account='account1'):
    return BASE_DIR / "data" / account

_run_log = []
_run_lock = threading.Lock()
_agent_done = True
_daily_writer_done_date = None


def load_json(path, default):
    p = Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_agent(agent, extra_args=None, account='account1'):
    global _agent_done
    cmd = [sys.executable, "-u", str(BASE_DIR / "main.py"), "--agent", agent, "--account", account]
    if extra_args:
        cmd += extra_args
    with _run_lock:
        _run_log.clear()
        _run_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ▶ {agent} 開始")
    _agent_done = False
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(BASE_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", bufsize=1,
            errors="replace", env=env
        )
        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            line = line.rstrip()
            if line:
                with _run_lock:
                    _run_log.append(line)
        proc.wait()
        with _run_lock:
            _run_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 完了")
    except Exception as e:
        with _run_lock:
            _run_log.append(f"❌ エラー: {e}")
    finally:
        _agent_done = True


def _check_scheduled_posts():
    if not _agent_done:
        return
    now = datetime.now()
    for account in ACCOUNTS:
        data_dir = get_data_dir(account)
        queue = load_json(data_dir / "queue.json", [])
        for p in queue:
            if p.get("status") != "queued":
                continue
            sa = p.get("scheduled_at")
            if not sa:
                continue
            try:
                if datetime.fromisoformat(sa) <= now:
                    threading.Thread(
                        target=run_agent, args=("poster", ["--force"], account), daemon=True
                    ).start()
                    return
            except (ValueError, TypeError):
                pass


def _scheduler_loop():
    global _daily_writer_done_date
    while True:
        try:
            now = datetime.now()
            today = now.date()
            if now.hour == 3 and now.minute < 5 and _daily_writer_done_date != today:
                _daily_writer_done_date = today
                threading.Thread(
                    target=run_agent,
                    args=("writer", ["--mode", "review", "--writer-batch", "5"]),
                    daemon=True
                ).start()
            _check_scheduled_posts()
        except Exception:
            pass
        time.sleep(60)


threading.Thread(target=_scheduler_loop, daemon=True).start()


# ======================================================
# HTML テンプレート（完全リニューアル版）
# ======================================================
HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Threads 運用</title>
<style>
/* ===== リセット & ベース ===== */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:      #0d0d0d;
  --surface: #161616;
  --surface2:#1e1e1e;
  --border:  #262626;
  --border2: #333;
  --accent:  #6366f1;
  --accent2: #818cf8;
  --green:   #22c55e;
  --yellow:  #f59e0b;
  --red:     #ef4444;
  --text:    #f0f0f0;
  --muted:   #737373;
  --muted2:  #525252;
}
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans JP', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 14px;
}

/* ===== ヘッダー ===== */
.header {
  position: sticky; top: 0; z-index: 100;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
  display: flex; align-items: center; height: 52px; gap: 16px;
}
.header-logo {
  font-size: 16px; font-weight: 700; color: var(--text);
  display: flex; align-items: center; gap: 8px;
  white-space: nowrap;
}
.header-logo span { font-size: 20px; }
.kill-badge {
  background: #450a0a; color: var(--red); border: 1px solid #7f1d1d;
  font-size: 11px; padding: 2px 10px; border-radius: 99px; font-weight: 600;
  display: none;
}
.kill-badge.active { display: inline-block; }
.header-right {
  margin-left: auto;
  display: flex; align-items: center; gap: 10px;
}
.spinner-wrap {
  display: none; align-items: center; gap: 8px;
  color: var(--accent2); font-size: 13px;
}
.spinner-wrap.active { display: flex; }
.spinner {
  width: 16px; height: 16px;
  border: 2px solid var(--border2);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ===== ナビゲーション ===== */
.nav {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex; gap: 2px; padding: 0 16px; overflow-x: auto;
}
.nav-btn {
  padding: 12px 16px;
  border: none; background: none;
  color: var(--muted); cursor: pointer;
  font-size: 13px; font-weight: 500;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
  display: flex; align-items: center; gap: 6px;
}
.nav-btn:hover { color: var(--text); }
.nav-btn.active { color: var(--accent2); border-bottom-color: var(--accent); }
.nav-btn .badge {
  background: #3730a3; color: var(--accent2);
  font-size: 10px; padding: 1px 6px; border-radius: 99px; font-weight: 700;
}

/* ===== メインコンテンツ ===== */
.main { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.page { display: none; }
.page.active { display: block; }

/* ===== 汎用コンポーネント ===== */
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px;
}
.card + .card { margin-top: 12px; }
.card-title {
  font-size: 13px; font-weight: 600; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.05em;
  margin-bottom: 14px;
}

/* ボタン */
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 8px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 500;
  transition: opacity 0.15s, transform 0.1s;
  white-space: nowrap;
}
.btn:active { transform: scale(0.97); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover:not(:disabled) { background: var(--accent2); }
.btn-green  { background: #14532d; color: var(--green); border: 1px solid #166534; }
.btn-green:hover:not(:disabled)  { background: #166534; }
.btn-red    { background: #450a0a; color: var(--red); border: 1px solid #7f1d1d; }
.btn-red:hover:not(:disabled)    { background: #7f1d1d; }
.btn-yellow { background: #422006; color: var(--yellow); border: 1px solid #78350f; }
.btn-yellow:hover:not(:disabled) { background: #78350f; }
.btn-ghost  { background: var(--surface2); color: var(--muted); border: 1px solid var(--border2); }
.btn-ghost:hover:not(:disabled)  { color: var(--text); }
.btn-sm { padding: 5px 12px; font-size: 12px; }
.btn-row { display: flex; gap: 8px; flex-wrap: wrap; }

/* ===== ダッシュボード ===== */
.stat-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px; margin-bottom: 12px;
}
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px;
}
.stat-label { font-size: 11px; color: var(--muted); margin-bottom: 6px; }
.stat-value { font-size: 30px; font-weight: 700; line-height: 1; }
.stat-sub { font-size: 11px; color: var(--muted2); margin-top: 4px; }
.api-row { display: flex; flex-wrap: wrap; gap: 14px; }
.api-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-green { background: var(--green); box-shadow: 0 0 5px var(--green); }
.dot-red   { background: var(--red); }
.dot-yellow{ background: var(--yellow); }

/* ===== ログボックス ===== */
.logbox {
  background: #080808; border: 1px solid var(--border);
  border-radius: 8px; padding: 14px;
  font-family: 'Courier New', monospace; font-size: 12px;
  color: var(--muted); max-height: 280px; overflow-y: auto;
  white-space: pre-wrap; word-break: break-all; line-height: 1.6;
}
.logbox.tall { max-height: 480px; }
.log-ok  { color: var(--green); }
.log-err { color: var(--red); }
.log-warn{ color: var(--yellow); }
.log-info{ color: var(--accent2); }

/* ===== 下書きページ ===== */
.page-header {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 20px; flex-wrap: wrap;
}
.page-header h2 { font-size: 20px; font-weight: 700; flex: 1; }
.tab-row {
  display: flex; gap: 4px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 4px; margin-bottom: 16px;
}
.tab {
  padding: 6px 16px; border-radius: 6px; border: none;
  cursor: pointer; font-size: 13px; color: var(--muted);
  background: transparent; transition: all 0.15s; white-space: nowrap;
}
.tab:hover { color: var(--text); }
.tab.active { background: var(--accent); color: #fff; }

/* 下書きカード */
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 12px;
}
.draft-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px; margin-bottom: 12px;
  transition: border-color 0.15s;
}
.draft-card:hover { border-color: var(--border2); }
.draft-card.is-today { border-left: 3px solid var(--green); }
.draft-meta {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 12px; flex-wrap: wrap;
}
.score-pill {
  padding: 3px 10px; border-radius: 99px; font-size: 12px; font-weight: 700;
}
.score-high { background: #14532d; color: var(--green); }
.score-mid  { background: #422006; color: var(--yellow); }
.tag {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: var(--surface2); color: var(--muted); border: 1px solid var(--border);
}
.tag-today { background: #052e16; color: var(--green); border-color: #166534; font-weight: 600; }
.draft-body {
  font-size: 14px; line-height: 1.9; color: #d4d4d4;
  background: #0a0a0a; border-radius: 8px; padding: 14px;
  white-space: pre-wrap; border: 1px solid var(--border);
  cursor: pointer; position: relative; margin-bottom: 12px;
  transition: border-color 0.15s;
}
.draft-body:hover { border-color: var(--accent); }
.edit-hint {
  position: absolute; top: 8px; right: 10px;
  font-size: 10px; color: var(--muted2);
}
.draft-textarea {
  display: none; width: 100%;
  background: #0a0a0a; border: 1px solid var(--accent);
  border-radius: 8px; color: #d4d4d4; padding: 14px;
  font-size: 14px; line-height: 1.9; min-height: 160px;
  resize: vertical; font-family: inherit; margin-bottom: 8px;
}
.draft-textarea:focus { outline: none; border-color: var(--accent2); }
.edit-actions { display: none; gap: 6px; margin-bottom: 10px; }

/* スケジュール */
.schedule-box {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; padding: 12px; margin-bottom: 12px;
}
.schedule-label { font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.schedule-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.dt-input {
  background: var(--surface); border: 1px solid var(--border2);
  color: var(--text); padding: 7px 12px; border-radius: 6px; font-size: 13px;
}
.dt-input:focus { outline: none; border-color: var(--accent); }
input[type="datetime-local"]::-webkit-calendar-picker-indicator {
  filter: invert(0.6); cursor: pointer;
}
.draft-actions { display: flex; gap: 8px; flex-wrap: wrap; }

/* ===== POST1/POST2 ペア表示 ===== */
.post-pair-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  color: var(--muted2); text-transform: uppercase; margin-bottom: 6px;
}
.post-pair-label.p1 { color: var(--accent); }
.post-pair-label.p2 { color: var(--accent2); }
.post-pair-sep {
  display: flex; align-items: center; gap: 8px;
  margin: 10px 0; color: var(--muted2); font-size: 11px;
}
.post-pair-sep::before, .post-pair-sep::after {
  content: ''; flex: 1; height: 1px; background: var(--border);
}
.post-hook {
  font-size: 15px; font-weight: 600; line-height: 1.7; color: #f0f0f0;
  background: #0f0f1a; border-radius: 8px; padding: 14px;
  white-space: pre-wrap; border: 1px solid #2d2d5a;
  cursor: pointer; position: relative; margin-bottom: 4px;
  transition: border-color 0.15s;
}
.post-hook:hover { border-color: var(--accent); }
.post-body {
  font-size: 13px; line-height: 1.9; color: #b0b0b0;
  background: #0a0a0a; border-radius: 8px; padding: 14px;
  white-space: pre-wrap; border: 1px solid var(--border);
  cursor: pointer; position: relative; margin-bottom: 4px;
  transition: border-color 0.15s;
}
.post-body:hover { border-color: var(--accent2); }
.hook-textarea {
  display: none; width: 100%;
  background: #0f0f1a; border: 1px solid var(--accent);
  border-radius: 8px; color: #f0f0f0; padding: 14px;
  font-size: 15px; font-weight: 600; line-height: 1.7;
  min-height: 80px; resize: vertical; font-family: inherit; margin-bottom: 6px;
}
.hook-textarea:focus { outline: none; border-color: #7c6fff; }

/* ===== キューページ ===== */
.queue-item {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px; margin-bottom: 8px;
  display: flex; align-items: flex-start; gap: 14px;
}
.queue-time {
  font-size: 13px; font-weight: 600; color: var(--accent2);
  min-width: 120px; padding-top: 2px;
}
.queue-text { font-size: 13px; color: #aaa; flex: 1; }
.queue-meta { font-size: 11px; color: var(--muted2); margin-top: 4px; }

/* ===== 履歴テーブル ===== */
.table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th {
  text-align: left; padding: 10px 14px;
  color: var(--muted); font-weight: 500; font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border); white-space: nowrap;
  background: var(--surface);
}
td { padding: 10px 14px; border-bottom: 1px solid var(--border); color: #ccc; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--surface2); }
.st-posted  { color: var(--green); }
.st-queued  { color: var(--accent2); }
.st-draft   { color: var(--yellow); }
.st-skipped { color: var(--muted2); }

/* ===== エージェントグリッド ===== */
.agent-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.agent-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px;
}
.agent-name { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.agent-desc { font-size: 12px; color: var(--muted); margin-bottom: 12px; }
.mode-toggle {
  display: flex; gap: 4px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; padding: 4px; width: fit-content; margin-bottom: 16px;
}
.mode-btn {
  padding: 6px 18px; border-radius: 6px; border: none;
  cursor: pointer; font-size: 13px; color: var(--muted); background: transparent;
  transition: all 0.15s;
}
.mode-btn.active { background: var(--accent); color: #fff; }

/* ===== 空状態 ===== */
.empty {
  text-align: center; padding: 50px 20px; color: var(--muted);
}
.empty-icon { font-size: 40px; margin-bottom: 12px; }
.empty h3 { font-size: 15px; color: #aaa; margin-bottom: 8px; }
.empty p { font-size: 13px; margin-bottom: 16px; }

/* ===== 今すぐ原稿生成バナー ===== */
.writer-banner {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
  border: 1px solid #4338ca; border-radius: 12px;
  padding: 16px 20px; margin-bottom: 16px;
  display: flex; align-items: center; gap: 14px;
}
.writer-banner-text h3 { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.writer-banner-text p { font-size: 12px; color: #a5b4fc; }
.writer-banner .btn { margin-left: auto; flex-shrink: 0; }

/* ===== アカウント切り替え ===== */
.account-switcher {
  display: flex; gap: 4px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; padding: 3px;
}
.account-btn {
  padding: 4px 12px; border-radius: 6px; border: none;
  cursor: pointer; font-size: 12px; font-weight: 500;
  color: var(--muted); background: transparent;
  transition: all 0.15s; white-space: nowrap;
}
.account-btn:hover { color: var(--text); }
.account-btn.active { background: var(--accent); color: #fff; }
.account-label {
  font-size: 11px; color: var(--muted2); margin-left: 4px;
}

/* ===== ASP ===== */
.asp-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 14px;
}
.asp-rank {
  width: 30px; height: 30px; border-radius: 50%;
  background: var(--surface2); display: flex; align-items: center;
  justify-content: center; font-size: 12px; font-weight: 700;
  color: var(--muted); flex-shrink: 0;
}
.asp-info { flex: 1; }
.asp-name { font-size: 14px; font-weight: 600; }
.asp-reward { font-size: 12px; color: var(--green); margin-top: 2px; }
.asp-approval { font-size: 11px; color: var(--muted); margin-top: 2px; }
</style>
</head>
<body>

<!-- ヘッダー -->
<div class="header">
  <div class="header-logo">
    <span>🧵</span> Threads 運用
  </div>
  <div class="account-switcher">
    <button class="account-btn active" id="acc-btn-account1" onclick="switchAccount('account1')">あとむ</button>
    <button class="account-btn" id="acc-btn-account2" onclick="switchAccount('account2')">ゆな</button>
    <button class="account-btn" id="acc-btn-account3" onclick="switchAccount('account3')">ぺたろう</button>
  </div>
  <span class="account-label" id="account-label">AI×医療</span>
  <div class="kill-badge" id="kill-badge">⛔ KILL SWITCH ON</div>
  <div class="header-right">
    <div class="spinner-wrap" id="spinner-wrap">
      <div class="spinner"></div>
      <span id="spinner-label">実行中...</span>
    </div>
  </div>
</div>

<!-- ナビゲーション -->
<nav class="nav">
  <button class="nav-btn active" data-page="dashboard" onclick="goto('dashboard',this)">📊 ホーム</button>
  <button class="nav-btn" data-page="review" onclick="goto('review',this)">
    ✍️ 下書き
    <span class="badge" id="draft-badge" style="display:none">0</span>
  </button>
  <button class="nav-btn" data-page="queue" onclick="goto('queue',this)">📋 キュー</button>
  <button class="nav-btn" data-page="history" onclick="goto('history',this)">📈 履歴</button>
  <button class="nav-btn" data-page="agents" onclick="goto('agents',this)">⚡ エージェント</button>
  <button class="nav-btn" data-page="logs" onclick="goto('logs',this)">📄 ログ</button>
</nav>

<div class="main">

  <!-- ===== ダッシュボード ===== -->
  <div class="page active" id="page-dashboard">

    <!-- 原稿生成バナー -->
    <div class="writer-banner" id="writer-banner">
      <div>✍️</div>
      <div class="writer-banner-text">
        <h3>今日の原稿を生成する</h3>
        <p>毎朝3時に自動生成。いつでも手動で実行できます</p>
      </div>
      <button class="btn btn-primary" id="btn-write-home" onclick="runWriterNow('btn-write-home')">
        今すぐ生成
      </button>
    </div>

    <!-- ステータスカード -->
    <div class="stat-grid" id="stat-grid"></div>

    <!-- APIキー -->
    <div class="card" style="margin-bottom:12px;">
      <div class="card-title">APIキー</div>
      <div class="api-row" id="api-row"></div>
    </div>

    <!-- クイックアクション -->
    <div class="card" style="margin-bottom:12px;">
      <div class="card-title">クイックアクション</div>
      <div class="btn-row">
        <button class="btn btn-primary" onclick="runAgent('all')">▶ 全実行</button>
        <button class="btn btn-ghost" onclick="goto('review')">✍️ 下書きレビュー</button>
        <button class="btn btn-yellow" onclick="runAgent('poster',['--force'])">⚡ 今すぐ投稿</button>
        <button class="btn btn-red" onclick="doKill()">🛑 緊急停止</button>
        <button class="btn btn-green" onclick="doKillOff()" style="display:none" id="btn-kill-off">✅ 停止解除</button>
      </div>
    </div>

    <!-- ログ -->
    <div class="card">
      <div class="card-title">実行ログ</div>
      <div class="logbox" id="log-home">待機中...</div>
    </div>
  </div>

  <!-- ===== 下書きレビュー ===== -->
  <div class="page" id="page-review">
    <div class="page-header">
      <h2>下書きレビュー</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost btn-sm" onclick="loadReview()">🔄 更新</button>
        <button class="btn btn-primary" id="btn-write-review" onclick="runWriterNow('btn-write-review')">
          ✍️ 今すぐ原稿生成
        </button>
      </div>
    </div>

    <div class="tab-row">
      <button class="tab active" onclick="setTab('today',this)">📅 今日 <span id="cnt-today"></span></button>
      <button class="tab" onclick="setTab('all',this)">📄 全て <span id="cnt-all"></span></button>
      <button class="tab" onclick="setTab('scheduled',this)">🕐 スケジュール <span id="cnt-sched"></span></button>
    </div>

    <div id="drafts-container"></div>
    <div id="sched-container" style="display:none"></div>
  </div>

  <!-- ===== キュー ===== -->
  <div class="page" id="page-queue">
    <div class="page-header">
      <h2>投稿キュー</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost btn-sm" onclick="loadQueue()">更新</button>
        <button class="btn btn-sm" style="background:#ef4444;color:#fff;border:none" onclick="clearQueue()">🗑 全削除</button>
      </div>
    </div>
    <div id="queue-container"></div>
  </div>

  <!-- ===== 履歴 ===== -->
  <div class="page" id="page-history">
    <div class="page-header">
      <h2>投稿履歴</h2>
      <button class="btn btn-ghost btn-sm" onclick="loadHistory()">更新</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>日時</th><th>テーマ</th><th>パターン</th><th>スコア</th>
            <th>👁 閲覧</th><th>❤️ いいね</th><th>💬 返信</th><th>状態</th>
          </tr>
        </thead>
        <tbody id="history-body"></tbody>
      </table>
    </div>
  </div>

  <!-- ===== エージェント ===== -->
  <div class="page" id="page-agents">
    <div class="page-header">
      <h2>エージェント実行</h2>
    </div>

    <div class="card" style="margin-bottom:12px;">
      <div class="card-title">運用モード</div>
      <div class="mode-toggle">
        <button class="mode-btn" onclick="setMode('auto',this)">🤖 完全自動</button>
        <button class="mode-btn active" onclick="setMode('review',this)">👁 5%人間</button>
      </div>
      <p style="font-size:12px;color:var(--muted);">
        <b style="color:#a5b4fc;">5%人間モード</b>: WriterがDraftsに保存 → あなたがレビュー → キューに追加<br>
        <b style="color:#a5b4fc;">完全自動モード</b>: Writerが直接キューに追加して自動投稿
      </p>
    </div>

    <div class="agent-grid">
      <div class="agent-card">
        <div class="agent-name">🔍 Researcher</div>
        <div class="agent-desc">YouTubeからネタ収集</div>
        <button class="btn btn-primary" style="width:100%" onclick="runAgent('researcher')">実行</button>
      </div>
      <div class="agent-card">
        <div class="agent-name">📊 Analyst</div>
        <div class="agent-desc">投稿データを分析してフィードバック生成</div>
        <button class="btn btn-primary" style="width:100%" onclick="runAgent('analyst')">実行</button>
      </div>
      <div class="agent-card">
        <div class="agent-name">✍️ Writer</div>
        <div class="agent-desc">採点付き投稿文を生成</div>
        <button class="btn btn-primary" style="width:100%" id="btn-write-agent" onclick="runWriterNow('btn-write-agent')">実行（5件生成）</button>
      </div>
      <div class="agent-card">
        <div class="agent-name">📤 Poster</div>
        <div class="agent-desc">Threads APIで投稿</div>
        <div class="btn-row" style="flex-direction:column;gap:6px;">
          <button class="btn btn-primary" style="width:100%" onclick="runAgent('poster')">スロット投稿</button>
          <button class="btn btn-yellow" style="width:100%" onclick="runAgent('poster',['--force'])">⚡ 今すぐ強制投稿</button>
        </div>
      </div>
      <div class="agent-card">
        <div class="agent-name">📈 Fetcher</div>
        <div class="agent-desc">24h後のメトリクスを取得</div>
        <button class="btn btn-primary" style="width:100%" onclick="runAgent('fetcher')">実行</button>
      </div>
      <div class="agent-card">
        <div class="agent-name">💰 ASP</div>
        <div class="agent-desc">A8.netからアフィリ案件リサーチ</div>
        <button class="btn btn-primary" style="width:100%" onclick="runAgent('asp')">実行</button>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="card-title">実行ログ</div>
      <div class="logbox" id="log-agents">待機中...</div>
    </div>
  </div>

  <!-- ===== ログ ===== -->
  <div class="page" id="page-logs">
    <div class="page-header">
      <h2>実行ログ</h2>
      <button class="btn btn-ghost btn-sm" onclick="loadLogs()">更新</button>
    </div>
    <div class="card">
      <div class="logbox tall" id="log-full">読み込み中...</div>
    </div>
  </div>

</div><!-- /main -->

<script>
'use strict';

// ===== 状態 =====
let currentMode = 'review';
let pollTimer = null;
let runningAgent = null;
let currentTab = 'today';
let allDrafts = [];
let currentAccount = 'account1';

const ACCOUNT_LABELS = {
  'account1': 'あとむ｜AI×医療',
  'account2': 'ゆな｜からだケア',
  'account3': 'ぺたろう｜ペット×楽天',
};

function switchAccount(account) {
  currentAccount = account;
  document.querySelectorAll('.account-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('acc-btn-' + account);
  if (btn) btn.classList.add('active');
  const label = document.getElementById('account-label');
  if (label) label.textContent = ACCOUNT_LABELS[account] || account;
  // 現在のページを再読み込み
  const activePage = document.querySelector('.page.active');
  if (!activePage) return;
  const pageId = activePage.id.replace('page-', '');
  if (pageId === 'dashboard') loadDashboard();
  else if (pageId === 'review') loadReview();
  else if (pageId === 'queue') loadQueue();
  else if (pageId === 'history') loadHistory();
  else if (pageId === 'logs') loadLogs();
}

// ===== ユーティリティ =====
function esc(s) {
  return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function colorLine(line) {
  const s = esc(line);
  if (/ERROR|エラー|❌/.test(s)) return '<span class="log-err">' + s + '</span>';
  if (/WARNING|警告/.test(s))    return '<span class="log-warn">' + s + '</span>';
  if (/完了|✅|Posted|AVAILABLE/.test(s)) return '<span class="log-ok">' + s + '</span>';
  if (/INFO|▶|実行|開始/.test(s))  return '<span class="log-info">' + s + '</span>';
  return s;
}

function setLogAll(html) {
  ['log-home','log-agents'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.innerHTML = html; el.scrollTop = el.scrollHeight; }
  });
}

function defaultDt() {
  const d = new Date();
  d.setMinutes(0); d.setSeconds(0);
  d.setHours(d.getHours() + 1);
  const pad = n => String(n).padStart(2,'0');
  return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())
    +'T'+pad(d.getHours())+':00';
}

// ===== ナビゲーション =====
function goto(page, btn) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  if (btn) {
    btn.classList.add('active');
  } else {
    const target = document.querySelector('[data-page="' + page + '"]');
    if (target) target.classList.add('active');
  }
  if (page === 'dashboard') loadDashboard();
  if (page === 'review')    loadReview();
  if (page === 'queue')     loadQueue();
  if (page === 'history')   loadHistory();
  if (page === 'logs')      loadLogs();
}

// ===== エージェント実行 =====
function startSpinner(label) {
  document.getElementById('spinner-wrap').classList.add('active');
  document.getElementById('spinner-label').textContent = label || '実行中...';
}
function stopSpinner() {
  document.getElementById('spinner-wrap').classList.remove('active');
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  runningAgent = null;
}

async function runAgent(agent, extraArgs) {
  if (runningAgent) stopSpinner();
  runningAgent = agent;
  startSpinner(agent + ' 実行中...');
  setLogAll('<span class="log-info">▶ ' + esc(agent) + ' を実行中...</span>');

  try {
    const body = { agent, mode: currentMode, account: currentAccount, extra_args: extraArgs || [] };
    const r = await fetch('/api/run', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);

    let maxPoll = 600;
    pollTimer = setInterval(async () => {
      if (--maxPoll <= 0) { stopSpinner(); return; }
      try {
        const res = await fetch('/api/log');
        const data = await res.json();
        if (data.lines && data.lines.length) {
          setLogAll(data.lines.map(colorLine).join('<br>'));
        }
        if (data.done) {
          stopSpinner();
          loadDashboard();
          const revPage = document.getElementById('page-review');
          if (revPage && revPage.classList.contains('active')) loadReview();
        }
      } catch(e) {}
    }, 800);
  } catch(e) {
    stopSpinner();
    setLogAll('<span class="log-err">❌ エラー: ' + esc(e.message) + '</span>');
  }
}

async function runWriterNow(btnId) {
  const btn = btnId ? document.getElementById(btnId) : null;
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 生成中...'; }
  await runAgent('writer', ['--mode', 'review', '--writer-batch', '5']);
  setTimeout(() => {
    if (btn) { btn.disabled = false; btn.textContent = btnId === 'btn-write-review' ? '✍️ 今すぐ原稿生成' : (btnId === 'btn-write-home' ? '今すぐ生成' : '実行（5件生成）'); }
    loadReview();
  }, 2000);
}

// ===== ダッシュボード =====
async function loadDashboard() {
  try {
    const d = await (await fetch('/api/status?account=' + currentAccount)).json();

    // Kill switch
    const kb = document.getElementById('kill-badge');
    const kbtn = document.getElementById('btn-kill-off');
    if (d.kill_switch) {
      kb.classList.add('active');
      if (kbtn) kbtn.style.display = 'inline-flex';
    } else {
      kb.classList.remove('active');
      if (kbtn) kbtn.style.display = 'none';
    }

    // モードバッジ
    currentMode = d.mode || 'review';

    // 下書きバッジ
    const db = document.getElementById('draft-badge');
    if (d.draft_count > 0) {
      db.textContent = d.draft_count; db.style.display = 'inline-block';
    } else {
      db.style.display = 'none';
    }

    // 統計カード
    const stats = [
      { label: '下書き', value: d.draft_count, sub: 'レビュー待ち', color: d.draft_count > 0 ? 'var(--yellow)' : 'var(--muted)' },
      { label: 'キュー', value: d.queue_count, sub: '投稿待ち', color: d.queue_count > 0 ? 'var(--accent2)' : 'var(--muted)' },
      { label: 'スケジュール', value: d.scheduled_count, sub: '時刻指定済み', color: d.scheduled_count > 0 ? '#c084fc' : 'var(--muted)' },
      { label: '今日', value: d.today_posts, sub: '/ ' + d.max_daily + '件', color: 'var(--green)' },
      { label: '累計投稿', value: d.total_posts, sub: '件', color: 'var(--text)' },
    ];
    document.getElementById('stat-grid').innerHTML = stats.map(s =>
      '<div class="stat-card"><div class="stat-label">'+s.label+'</div>'
      +'<div class="stat-value" style="color:'+s.color+'">'+s.value+'</div>'
      +'<div class="stat-sub">'+s.sub+'</div></div>'
    ).join('');

    // APIキー
    document.getElementById('api-row').innerHTML = Object.entries(d.api_keys).map(([k, v]) =>
      '<div class="api-item"><div class="dot '+(v?'dot-green':'dot-red')+'"></div>'
      +k.toUpperCase()+': '+(v?'OK':'未設定')+'</div>'
    ).join('');
  } catch(e) { console.error('loadDashboard:', e); }
}

// ===== モード切替 =====
function setMode(mode, btn) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  fetch('/api/set_mode', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode })
  }).catch(() => {});
}

// ===== 下書きレビュー =====
function setTab(tab, btn) {
  currentTab = tab;
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderTab();
}

async function loadReview() {
  try {
    allDrafts = await (await fetch('/api/drafts?account=' + currentAccount)).json();
    const today = new Date().toISOString().slice(0,10);
    const pending = allDrafts.filter(d => d.status === 'draft');
    const todayN  = pending.filter(d => (d.created_at||'').startsWith(today)).length;
    document.getElementById('cnt-today').textContent = todayN > 0 ? '('+todayN+')' : '';
    document.getElementById('cnt-all').textContent   = pending.length > 0 ? '('+pending.length+')' : '';

    const q = await (await fetch('/api/queue?account=' + currentAccount)).json();
    const schedN = q.filter(p => p.status==='queued' && p.scheduled_at).length;
    document.getElementById('cnt-sched').textContent = schedN > 0 ? '('+schedN+')' : '';

    renderTab();
  } catch(e) { console.error('loadReview:', e); }
}

function renderTab() {
  const dc = document.getElementById('drafts-container');
  const sc = document.getElementById('sched-container');
  if (currentTab === 'scheduled') {
    dc.style.display = 'none'; sc.style.display = 'block';
    renderScheduled();
    return;
  }
  dc.style.display = 'block'; sc.style.display = 'none';
  const today = new Date().toISOString().slice(0,10);
  let list = allDrafts.filter(d => d.status === 'draft');
  if (currentTab === 'today') list = list.filter(d => (d.created_at||'').startsWith(today));
  if (list.length === 0) {
    dc.innerHTML = '<div class="empty">'
      +'<div class="empty-icon">📝</div>'
      +'<h3>原稿がありません</h3>'
      +'<p>Writerを実行して原稿を生成してください</p>'
      +'<button class="btn btn-primary" onclick="runWriterNow(\'btn-write-review\')">✍️ 今すぐ原稿生成</button>'
      +'</div>';
    return;
  }
  const bulkBar = `<div class="bulk-bar" id="bulk-bar">
    <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;">
      <input type="checkbox" id="check-all" onchange="toggleCheckAll(this.checked)"> 全選択
    </label>
    <span id="bulk-count" style="font-size:12px;color:var(--muted2)">0件選択中</span>
    <button class="btn btn-red btn-sm" onclick="bulkReject()" id="btn-bulk-reject" disabled>✗ 選択を削除</button>
  </div>`;
  dc.innerHTML = bulkBar + list.map(d => renderDraftCard(d, today)).join('');
}

function renderDraftCard(d, today) {
  const score = d.score || 0;
  const scoreClass = score >= 8 ? 'score-high' : 'score-mid';
  const isToday = (d.created_at||'').startsWith(today);
  const timeStr = d.created_at ? d.created_at.slice(11,16) : '';
  const defDt = defaultDt();

  // hook/body ペア形式か旧形式かを判定
  const hasPair = !!(d.hook);
  const hookEsc = esc(d.hook || '');
  const bodyEsc = esc(d.body || d.content || '');

  // POST3以降（thread_replies）
  const replies = d.thread_replies || [];
  const repliesHtml = replies.map((r, i) => {
    const rid = d.id + '-r' + i;
    const rEsc = esc(r);
    return `
  <div class="post-pair-sep">↓ スレッド返信</div>
  <div class="post-pair-label p2">POST ${i+3} — スレッド返信</div>
  <div class="post-body" id="reply-${rid}" onclick="toggleReplyEdit('${rid}')">
    <span class="edit-hint">クリックで編集</span>${rEsc}
  </div>
  <textarea class="draft-textarea" id="rta-${rid}">${rEsc}</textarea>
  <div class="edit-actions" id="rea-${rid}">
    <button class="btn btn-primary btn-sm" onclick="saveReplyEdit('${d.id}', ${i})">保存</button>
    <button class="btn btn-ghost btn-sm" onclick="cancelReplyEdit('${rid}')">キャンセル</button>
  </div>`;
  }).join('');

  const pairHtml = hasPair ? `
  <div class="post-pair-label p1">POST 1 — フック（止まらせる）</div>
  <div class="post-hook" id="hook-${d.id}" onclick="toggleHookEdit('${d.id}')">
    <span class="edit-hint">クリックで編集</span>${hookEsc}
  </div>
  <textarea class="hook-textarea" id="hta-${d.id}">${hookEsc}</textarea>
  <div class="edit-actions" id="hea-${d.id}">
    <button class="btn btn-primary btn-sm" onclick="saveHookEdit('${d.id}')">保存</button>
    <button class="btn btn-ghost btn-sm" onclick="cancelHookEdit('${d.id}')">キャンセル</button>
  </div>

  <div class="post-pair-sep">↓ スレッド返信</div>

  <div class="post-pair-label p2">POST 2 — 本文</div>
  <div class="post-body" id="body-${d.id}" onclick="toggleEdit('${d.id}')">
    <span class="edit-hint">クリックで編集</span>${bodyEsc}
  </div>
  <textarea class="draft-textarea" id="ta-${d.id}">${bodyEsc}</textarea>
  <div class="edit-actions" id="ea-${d.id}">
    <button class="btn btn-primary btn-sm" onclick="saveEdit('${d.id}')">保存</button>
    <button class="btn btn-ghost btn-sm" onclick="cancelEdit('${d.id}')">キャンセル</button>
  </div>` : `
  <div class="draft-body" id="body-${d.id}" onclick="toggleEdit('${d.id}')">
    <span class="edit-hint">クリックで編集</span>${bodyEsc}
  </div>
  <textarea class="draft-textarea" id="ta-${d.id}">${bodyEsc}</textarea>
  <div class="edit-actions" id="ea-${d.id}">
    <button class="btn btn-primary btn-sm" onclick="saveEdit('${d.id}')">保存</button>
    <button class="btn btn-ghost btn-sm" onclick="cancelEdit('${d.id}')">キャンセル</button>
  </div>`;

  return `<div class="draft-card${isToday?' is-today':''}" id="dc-${d.id}">
  <div class="draft-meta">
    <input type="checkbox" class="draft-checkbox" data-id="${d.id}" onchange="updateBulkCount()" style="width:16px;height:16px;cursor:pointer;flex-shrink:0;">
    <span class="score-pill ${scoreClass}">★ ${score}</span>
    ${isToday?'<span class="tag tag-today">今日</span>':''}
    ${hasPair?`<span class="tag" style="background:#1a1a3a;color:#7c6fff;border-color:#3d3d8a">${replies.length>0?replies.length+2:2}投稿セット</span>`:''}

    <span class="tag">${esc(d.pattern||'-')}</span>
    <span class="tag">${esc(d.theme||'-')}</span>
    ${timeStr?`<span style="font-size:11px;color:var(--muted2)">${timeStr}生成</span>`:''}
  </div>

  ${pairHtml}
  ${repliesHtml}

  <div class="schedule-box" style="margin-top:12px">
    <div class="schedule-label">📅 投稿日時を指定（未指定でスロット自動投稿）</div>
    <div class="schedule-row">
      <input type="datetime-local" class="dt-input" id="dt-${d.id}" value="${defDt}">
      <button class="btn btn-ghost btn-sm" onclick="document.getElementById('dt-${d.id}').value=''">指定なし</button>
    </div>
  </div>

  <div class="draft-actions">
    <button class="btn btn-green" onclick="approveDraft('${d.id}')">✓ 承認</button>
    <button class="btn btn-red btn-sm" onclick="rejectDraft('${d.id}')">✗ 否決</button>
    <button class="btn btn-ghost btn-sm" onclick="skipDraft('${d.id}')">→ 後で</button>
  </div>
</div>`;
}

function toggleHookEdit(id) {
  const hook = document.getElementById('hook-'+id);
  const ta   = document.getElementById('hta-'+id);
  const ea   = document.getElementById('hea-'+id);
  if (ta.style.display === 'block') { cancelHookEdit(id); return; }
  hook.style.display = 'none';
  ta.style.display = 'block';
  ea.style.display = 'flex';
  ta.focus();
}

function cancelHookEdit(id) {
  document.getElementById('hook-'+id).style.display = 'block';
  document.getElementById('hta-'+id).style.display = 'none';
  document.getElementById('hea-'+id).style.display = 'none';
}

async function saveHookEdit(id) {
  const ta = document.getElementById('hta-'+id);
  const newHook = ta.value;
  await fetch('/api/draft/edit_full', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, hook: newHook, account: currentAccount })
  });
  const hookEl = document.getElementById('hook-'+id);
  hookEl.innerHTML = '<span class="edit-hint">クリックで編集</span>' + esc(newHook);
  cancelHookEdit(id);
}

function toggleEdit(id) {
  const body = document.getElementById('body-'+id);
  const ta   = document.getElementById('ta-'+id);
  const ea   = document.getElementById('ea-'+id);
  if (ta.style.display === 'block') { cancelEdit(id); return; }
  body.style.display = 'none';
  ta.style.display = 'block';
  ea.style.display = 'flex';
  ta.focus();
}

function cancelEdit(id) {
  document.getElementById('body-'+id).style.display = 'block';
  document.getElementById('ta-'+id).style.display = 'none';
  document.getElementById('ea-'+id).style.display = 'none';
}

// ===== スレッド返信（POST3以降）編集 =====
function toggleReplyEdit(rid) {
  const el = document.getElementById('reply-'+rid);
  const ta = document.getElementById('rta-'+rid);
  const ea = document.getElementById('rea-'+rid);
  if (ta.style.display === 'block') { cancelReplyEdit(rid); return; }
  el.style.display = 'none';
  ta.style.display = 'block';
  ea.style.display = 'flex';
  ta.focus();
}

function cancelReplyEdit(rid) {
  document.getElementById('reply-'+rid).style.display = 'block';
  document.getElementById('rta-'+rid).style.display = 'none';
  document.getElementById('rea-'+rid).style.display = 'none';
}

async function saveReplyEdit(draftId, replyIndex) {
  const rid = draftId + '-r' + replyIndex;
  const newText = document.getElementById('rta-'+rid).value;
  // 対象下書きの thread_replies を全部取得して該当インデックスだけ差し替える
  const draft = allDrafts.find(d => d.id === draftId);
  const replies = draft ? [...(draft.thread_replies || [])] : [];
  replies[replyIndex] = newText;
  const r = await fetch('/api/draft/edit_full', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: draftId, thread_replies: replies, account: currentAccount })
  });
  if ((await r.json()).ok) {
    if (draft) draft.thread_replies = replies;
    const el = document.getElementById('reply-'+rid);
    el.innerHTML = '<span class="edit-hint">クリックで編集</span>' + esc(newText);
    cancelReplyEdit(rid);
  }
}

async function saveEdit(id) {
  const ta = document.getElementById('ta-'+id);
  const newContent = ta.value;
  await fetch('/api/draft/edit_full', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, body: newContent, account: currentAccount })
  });
  const bodyEl = document.getElementById('body-'+id);
  bodyEl.innerHTML = '<span class="edit-hint">クリックで編集</span>' + esc(newContent);
  cancelEdit(id);
}

async function approveDraft(id) {
  const dtEl = document.getElementById('dt-'+id);
  const scheduledAt = dtEl ? dtEl.value : '';
  await fetch('/api/draft/approve', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, scheduled_at: scheduledAt || null, account: currentAccount })
  });
  const el = document.getElementById('dc-'+id);
  if (el) {
    el.style.opacity = '0.4';
    el.innerHTML = '<div style="padding:12px;color:var(--green);font-size:13px;">✓ 承認済み'
      + (scheduledAt ? ' — ' + scheduledAt.replace('T',' ') : ' — キューに追加') + '</div>';
    setTimeout(() => { el.remove(); loadReview(); }, 1200);
  }
}

function toggleCheckAll(checked) {
  document.querySelectorAll('.draft-checkbox').forEach(cb => cb.checked = checked);
  updateBulkCount();
}

function updateBulkCount() {
  const checked = document.querySelectorAll('.draft-checkbox:checked');
  const count = checked.length;
  const el = document.getElementById('bulk-count');
  const btn = document.getElementById('btn-bulk-reject');
  const all = document.getElementById('check-all');
  if (el) el.textContent = count + '件選択中';
  if (btn) btn.disabled = count === 0;
  if (all) {
    const total = document.querySelectorAll('.draft-checkbox').length;
    all.indeterminate = count > 0 && count < total;
    all.checked = total > 0 && count === total;
  }
}

async function bulkReject() {
  const checked = document.querySelectorAll('.draft-checkbox:checked');
  const ids = Array.from(checked).map(cb => cb.dataset.id);
  if (ids.length === 0) return;
  if (!confirm(ids.length + '件の下書きを削除しますか？')) return;
  await fetch('/api/draft/bulk_reject', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ids, account: currentAccount })
  });
  ids.forEach(id => {
    const el = document.getElementById('dc-' + id);
    if (el) el.remove();
  });
  loadReview();
}

async function rejectDraft(id) {
  if (!confirm('この原稿を否決（削除）しますか？')) return;
  await fetch('/api/draft/reject', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, account: currentAccount })
  });
  const el = document.getElementById('dc-'+id);
  if (el) {
    el.style.opacity = '0.3';
    el.innerHTML = '<div style="padding:12px;color:var(--red);font-size:13px;">✗ 否決しました</div>';
    setTimeout(() => { el.remove(); loadReview(); }, 800);
  }
}

async function skipDraft(id) {
  await fetch('/api/draft/skip', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, account: currentAccount })
  });
  const el = document.getElementById('dc-'+id);
  if (el) { el.style.opacity = '0.3'; setTimeout(() => { el.remove(); loadReview(); }, 400); }
}

async function renderScheduled() {
  const sc = document.getElementById('sched-container');
  const q = await (await fetch('/api/queue?account=' + currentAccount)).json();
  const list = q.filter(p => p.status==='queued' && p.scheduled_at)
                 .sort((a,b) => a.scheduled_at.localeCompare(b.scheduled_at));
  if (list.length === 0) {
    sc.innerHTML = '<div class="empty"><div class="empty-icon">🕐</div><h3>スケジュール済みの投稿はありません</h3><p>承認時に投稿日時を指定するとここに表示されます</p></div>';
    return;
  }
  sc.innerHTML = list.map(p => {
    const dt = (p.scheduled_at||'').replace('T',' ').slice(0,16);
    const preview = esc((p.content||'').replace(/\n/g,' ').slice(0,60));
    return `<div class="queue-item" id="qi-${p.id}">
      <div class="queue-time">📅 ${dt}</div>
      <div style="flex:1">
        <div class="queue-text">${preview}…</div>
        <div class="queue-meta">${esc(p.pattern||'-')} | ${esc(p.theme||'-')}${p.score?' ★'+p.score:''}</div>
      </div>
      <button class="btn btn-ghost btn-sm" onclick="cancelSched('${p.id}')">取消</button>
    </div>`;
  }).join('');
}

async function cancelSched(id) {
  if (!confirm('スケジュールを取り消しますか？（キューに残ります）')) return;
  await fetch('/api/queue/cancel_scheduled', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, account: currentAccount })
  });
  loadReview(); loadDashboard();
}

// ===== キュー =====
async function loadQueue() {
  const q = await (await fetch('/api/queue?account=' + currentAccount)).json();
  const pending = q.filter(p => p.status === 'queued');
  const qc = document.getElementById('queue-container');
  if (pending.length === 0) {
    qc.innerHTML = '<div class="empty"><div class="empty-icon">📋</div><h3>キューは空です</h3><p>下書きを承認するとキューに追加されます</p></div>';
    return;
  }
  qc.innerHTML = pending.map(p => {
    const dt = p.scheduled_at ? '📅 ' + p.scheduled_at.replace('T',' ').slice(0,16) : '⏳ 次のスロット待ち';
    const preview = esc((p.content||'').replace(/\n/g,' ').slice(0,70));
    return `<div class="queue-item" data-id="${esc(p.id||'')}">
      <div class="queue-time">${dt}</div>
      <div style="flex:1">
        <div class="queue-text">${preview}…</div>
        <div class="queue-meta">${esc(p.theme||'-')} | ${esc(p.pattern||'-')}${p.score?' ★'+p.score:''}</div>
      </div>
      <button class="q-del-btn" data-id="${esc(p.id||'')}" style="background:none;border:none;color:#ef4444;font-size:20px;cursor:pointer;padding:0 6px;line-height:1;flex-shrink:0" title="削除">✕</button>
    </div>`;
  }).join('');

  // イベント委譲でクリックを処理（inline onclickより確実）
  qc.querySelectorAll('.q-del-btn').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = btn.getAttribute('data-id');
      if (!id) return;
      const r = await fetch('/api/queue/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, account: currentAccount })
      });
      if ((await r.json()).ok) {
        btn.closest('.queue-item').remove();
        if (!qc.querySelector('.queue-item'))
          qc.innerHTML = '<div class="empty"><div class="empty-icon">📋</div><h3>キューは空です</h3><p>下書きを承認するとキューに追加されます</p></div>';
      }
    });
  });
}

async function clearQueue() {
  if (!confirm('キューの投稿をすべて削除します。よろしいですか？')) return;
  const r = await fetch('/api/queue/clear', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: currentAccount })
  });
  if ((await r.json()).ok) loadQueue();
}

// ===== 履歴 =====
async function loadHistory() {
  const posts = await (await fetch('/api/history?account=' + currentAccount)).json();
  const rows = posts.slice().reverse().map(p => {
    const dt = (p.posted_at||p.created_at||'').slice(0,16).replace('T',' ');
    const m = p.metrics_24h || p.metrics_1h || p.metrics || {};
    return `<tr>
      <td>${esc(dt)}</td>
      <td>${esc(p.theme||'-')}</td>
      <td>${esc(p.pattern||'-')}</td>
      <td>${p.score||'-'}</td>
      <td>${m.views||'-'}</td>
      <td>${m.likes||'-'}</td>
      <td>${m.replies||'-'}</td>
      <td class="st-${p.status||'queued'}">${esc(p.status||'-')}</td>
    </tr>`;
  }).join('');
  document.getElementById('history-body').innerHTML = rows ||
    '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:30px">履歴がありません</td></tr>';
}

// ===== ログ =====
async function loadLogs() {
  const data = await (await fetch('/api/runlog?account=' + currentAccount)).json();
  const el = document.getElementById('log-full');
  el.innerHTML = (data.lines||[]).map(colorLine).join('<br>') || '（ログなし）';
  el.scrollTop = el.scrollHeight;
}

// ===== KILL SWITCH =====
async function doKill() {
  if (!confirm('緊急停止します。全投稿が止まります。よろしいですか？')) return;
  await fetch('/api/kill', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: currentAccount })
  });
  loadDashboard();
}
async function doKillOff() {
  await fetch('/api/kill_off', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: currentAccount })
  });
  loadDashboard();
}

// ===== 初期化 =====
loadDashboard();
setInterval(() => {
  loadDashboard();
  const revPage = document.getElementById('page-review');
  if (revPage && revPage.classList.contains('active')) loadReview();
}, 30000);
</script>
</body>
</html>"""


# ======================================================
# API Routes（変更なし）
# ======================================================

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/status")
def api_status():
    account  = request.args.get("account", "account1")
    data_dir = get_data_dir(account)
    queue   = load_json(data_dir / "queue.json", [])
    drafts  = load_json(data_dir / "drafts.json", [])
    history = load_json(data_dir / "post_history.json", [])
    today   = datetime.now().date().isoformat()
    today_posts = [p for p in history if p.get("posted_at","").startswith(today)]
    scheduled_count = sum(1 for p in queue if p.get("status")=="queued" and p.get("scheduled_at"))

    # アカウントごとにenvから直接読む（スレッド競合回避）
    from dotenv import load_dotenv
    load_dotenv(override=False)
    if account == "account1":
        th_token  = os.environ.get("THREADS_ACCESS_TOKEN")
        th_userid = os.environ.get("THREADS_USER_ID")
    else:
        suffix = f"_{account.upper()}"
        th_token  = os.environ.get(f"THREADS_ACCESS_TOKEN{suffix}")
        th_userid = os.environ.get(f"THREADS_USER_ID{suffix}")
    keys = {
        "threads":   bool(th_token and th_userid),
        "youtube":   bool(os.environ.get("YOUTUBE_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }

    return jsonify({
        "queue_count":     len([p for p in queue if p.get("status")=="queued"]),
        "draft_count":     len([p for p in drafts if p.get("status")=="draft"]),
        "scheduled_count": scheduled_count,
        "today_posts":     len(today_posts),
        "total_posts":     len(history),
        "max_daily":       10,
        "kill_switch":     (data_dir / "KILL_SWITCH").exists(),
        "mode":            os.environ.get("OPERATION_MODE","review"),
        "api_keys":        keys,
        "_debug_token":    bool(th_token),
        "_debug_userid":   bool(th_userid),
    })


@app.route("/api/debug-env")
def api_debug_env():
    from dotenv import load_dotenv
    env_path = BASE_DIR / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    return jsonify({
        "env_path": str(env_path),
        "env_exists": env_path.exists(),
        "THREADS_ACCESS_TOKEN_ACCOUNT2": bool(os.environ.get("THREADS_ACCESS_TOKEN_ACCOUNT2")),
        "THREADS_USER_ID_ACCOUNT2": os.environ.get("THREADS_USER_ID_ACCOUNT2"),
    })


@app.route("/api/set_mode", methods=["POST"])
def api_set_mode():
    os.environ["OPERATION_MODE"] = request.json.get("mode","review")
    return jsonify({"ok": True})


_agent_thread = None


@app.route("/api/run", methods=["POST"])
def api_run():
    global _agent_thread, _agent_done
    data       = request.json
    agent      = data.get("agent","all")
    mode       = data.get("mode","review")
    account    = data.get("account","account1")
    extra_args = data.get("extra_args",[])
    _agent_done = False
    _agent_thread = threading.Thread(
        target=run_agent,
        args=(agent, extra_args + ["--mode", mode], account),
        daemon=True
    )
    _agent_thread.start()
    return jsonify({"ok": True})


@app.route("/api/log")
def api_log():
    with _run_lock:
        lines = list(_run_log)
    return jsonify({"lines": lines, "done": _agent_done})


@app.route("/api/runlog")
def api_runlog():
    account  = request.args.get("account", "account1")
    log_path = get_data_dir(account) / "run.log"
    if not log_path.exists():
        return jsonify({"lines": []})
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return jsonify({"lines": [l.rstrip() for l in lines[-50:]]})


@app.route("/api/drafts")
def api_drafts():
    account = request.args.get("account", "account1")
    return jsonify(load_json(get_data_dir(account) / "drafts.json", []))


@app.route("/api/draft/approve", methods=["POST"])
def api_approve():
    data         = request.json
    post_id      = data["id"]
    scheduled_at = data.get("scheduled_at")
    account      = data.get("account", "account1")
    data_dir     = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    queue  = load_json(data_dir / "queue.json", [])
    existing_ids = {q["id"] for q in queue}
    for d in drafts:
        if d["id"] == post_id:
            d["status"] = "approved"
            if post_id not in existing_ids:
                approved = dict(d)
                approved["status"] = "queued"
                approved["approved_at"] = datetime.now().isoformat()
                if scheduled_at:
                    approved["scheduled_at"] = scheduled_at
                queue.append(approved)
    save_json(data_dir / "drafts.json", drafts)
    save_json(data_dir / "queue.json", queue)
    return jsonify({"ok": True})


@app.route("/api/draft/skip", methods=["POST"])
def api_skip():
    data     = request.json
    post_id  = data["id"]
    account  = data.get("account", "account1")
    data_dir = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    for d in drafts:
        if d["id"] == post_id:
            d["status"] = "skipped"
    save_json(data_dir / "drafts.json", drafts)
    return jsonify({"ok": True})


@app.route("/api/draft/reject", methods=["POST"])
def api_reject():
    data     = request.json
    post_id  = data["id"]
    account  = data.get("account", "account1")
    data_dir = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    for d in drafts:
        if d["id"] == post_id:
            d["status"] = "rejected"
            d["rejected_at"] = datetime.now().isoformat()
    save_json(data_dir / "drafts.json", drafts)
    return jsonify({"ok": True})


@app.route("/api/draft/bulk_reject", methods=["POST"])
def api_bulk_reject():
    data     = request.json
    ids      = data.get("ids", [])
    account  = data.get("account", "account1")
    data_dir = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    for d in drafts:
        if d["id"] in ids:
            d["status"] = "rejected"
            d["rejected_at"] = datetime.now().isoformat()
    save_json(data_dir / "drafts.json", drafts)
    return jsonify({"ok": True, "count": len(ids)})


@app.route("/api/draft/edit", methods=["POST"])
def api_edit():
    data      = request.json
    post_id   = data["id"]
    new_first = data.get("new_first_line","")
    account   = data.get("account", "account1")
    data_dir  = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    for d in drafts:
        if d["id"] == post_id:
            lines = d.get("content","").split("\n")
            if lines: lines[0] = new_first
            d["content"] = "\n".join(lines)
            d["edited"] = True
    save_json(data_dir / "drafts.json", drafts)
    return jsonify({"ok": True})


@app.route("/api/draft/edit_full", methods=["POST"])
def api_edit_full():
    data     = request.json
    post_id  = data["id"]
    account  = data.get("account", "account1")
    data_dir = get_data_dir(account)
    drafts = load_json(data_dir / "drafts.json", [])
    for d in drafts:
        if d["id"] != post_id:
            continue
        # hook/body ペア形式
        if "hook" in data:
            d["hook"] = data["hook"]
        if "body" in data:
            d["body"] = data["body"]
            d["content"] = (d.get("hook","") + "\n\n" + data["body"]).strip()
        # thread_replies（POST3以降）
        if "thread_replies" in data:
            replies = data["thread_replies"]
            if isinstance(replies, list):
                d["thread_replies"] = [str(r) for r in replies]
        # 旧形式（content のみ）
        if "content" in data and "hook" not in data and "body" not in data:
            d["content"] = data["content"]
        d["edited"]    = True
        d["edited_at"] = datetime.now().isoformat()
    save_json(data_dir / "drafts.json", drafts)
    return jsonify({"ok": True})


@app.route("/api/queue")
def api_queue():
    account = request.args.get("account", "account1")
    return jsonify(load_json(get_data_dir(account) / "queue.json", []))


@app.route("/api/queue/cancel_scheduled", methods=["POST"])
def api_cancel_scheduled():
    data     = request.json
    post_id  = data["id"]
    account  = data.get("account", "account1")
    data_dir = get_data_dir(account)
    queue = load_json(data_dir / "queue.json", [])
    for p in queue:
        if p["id"] == post_id:
            p.pop("scheduled_at", None)
    save_json(data_dir / "queue.json", queue)
    return jsonify({"ok": True})


@app.route("/api/history")
def api_history():
    account = request.args.get("account", "account1")
    return jsonify(load_json(get_data_dir(account) / "post_history.json", []))


@app.route("/api/asp")
def api_asp():
    account = request.args.get("account", "account1")
    return jsonify(load_json(get_data_dir(account) / "asp_recommendations.json", {}))


@app.route("/api/queue/delete", methods=["POST"])
def api_queue_delete():
    data = request.json or {}
    account = data.get("account", "account1")
    post_id = data.get("id")
    path = get_data_dir(account) / "queue.json"
    queue = load_json(path, [])
    queue = [p for p in queue if p.get("id") != post_id]
    save_json(path, queue)
    return jsonify({"ok": True})


@app.route("/api/queue/clear", methods=["POST"])
def api_queue_clear():
    account = (request.json or {}).get("account", "account1")
    path = get_data_dir(account) / "queue.json"
    queue = load_json(path, [])
    # queued状態のみ削除。posted/failedは残す
    queue = [p for p in queue if p.get("status") != "queued"]
    save_json(path, queue)
    return jsonify({"ok": True})


@app.route("/api/kill", methods=["POST"])
def api_kill():
    account = request.json.get("account", "account1")
    (get_data_dir(account) / "KILL_SWITCH").write_text("killed", encoding="utf-8")
    return jsonify({"ok": True})


@app.route("/api/kill_off", methods=["POST"])
def api_kill_off():
    account = request.json.get("account", "account1") if request.json else "account1"
    p = get_data_dir(account) / "KILL_SWITCH"
    if p.exists():
        p.unlink()
    return jsonify({"ok": True})


def _fetcher_scheduler():
    """Background thread: run Fetcher for each account every hour."""
    import config as cfg
    from agents.fetcher import FetcherAgent

    # Wait 10s after startup before first run
    time.sleep(10)
    while True:
        for account in ACCOUNTS:
            try:
                data_dir = get_data_dir(account)
                if (data_dir / "KILL_SWITCH").exists():
                    continue
                cfg.switch_account(account)
                agent = FetcherAgent(cfg, cfg.KNOWLEDGE_DIR, cfg.DATA_DIR)
                agent.run()
            except Exception:
                pass  # Fetcher failure should never crash the UI
        time.sleep(60 * 60)  # 1 hour


if __name__ == "__main__":
    print("=" * 50)
    print("  Threads 運用 Web UI v2")
    print("  http://localhost:5000")
    print("=" * 50)

    t = threading.Thread(target=_fetcher_scheduler, daemon=True, name="fetcher-scheduler")
    t.start()
    print("  Fetcher: 1時間ごとに自動実行中")

    app.run(debug=False, port=5000, use_reloader=False)
