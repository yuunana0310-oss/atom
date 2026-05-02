
let currentMode = 'review';
let runningAgent = null;
let pollInterval = null;

// ---- ナビゲーション ----
function navigate(page, clickedEl) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  if (clickedEl) clickedEl.classList.add('active');
  if (page === 'dashboard') loadDashboard();
  else if (page === 'review') loadDrafts();
  else if (page === 'history') loadHistory();
  else if (page === 'asp') loadASP();
  else if (page === 'logs') loadLogs();
}

function setMode(mode, btn) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  document.getElementById('mode-badge').textContent = mode.toUpperCase();
  fetch('/api/set_mode', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode})}).catch(()=>{});
}

// ---- エージェント実行 ----
function setLog(html) {
  ['quick-log','agent-log'].forEach(id => {
    const el = document.getElementById(id);
    if (el) { el.innerHTML = html; el.scrollTop = el.scrollHeight; }
  });
}

function stopRunning() {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  runningAgent = null;
  const ind = document.getElementById('running-indicator');
  if (ind) ind.classList.remove('active');
}

async function runAgent(agent, extraArgs) {
  if (runningAgent) {
    // 前回が詰まっていたらリセットして続行
    stopRunning();
  }
  runningAgent = agent;
  document.getElementById('running-indicator').classList.add('active');
  document.getElementById('running-label').textContent = agent + ' 実行中...';
  setLog('<span style="color:#6c9cff">▶ ' + agent + ' を実行中...</span>');

  try {
    const body = {agent: agent, mode: currentMode, extra_args: extraArgs || []};
    const r = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);

    let maxPolls = 600; // 最大8分
    pollInterval = setInterval(async () => {
      maxPolls--;
      if (maxPolls <= 0) { stopRunning(); return; }
      try {
        const resp = await fetch('/api/log');
        const data = await resp.json();
        if (data.lines && data.lines.length > 0) {
          setLog(data.lines.map(colorLine).join('<br>'));
        }
        if (data.done) {
          stopRunning();
          loadDashboard();
          if (document.getElementById('page-asp').classList.contains('active')) loadASP();
        }
      } catch(e) { /* ポーリングエラーは無視して継続 */ }
    }, 800);

  } catch(e) {
    stopRunning();
    setLog('<span style="color:#f87171">❌ エラー: ' + e.message + '<br>Flaskが起動しているか確認してください</span>');
  }
}

function colorLine(line) {
  const e = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  if (e.includes('ERROR') || e.includes('エラー') || e.includes('❌')) return '<span class="log-line-error">' + e + '</span>';
  if (e.includes('WARNING') || e.includes('警告')) return '<span class="log-line-warn">' + e + '</span>';
  if (e.includes('完了') || e.includes('AVAILABLE') || e.includes('✅') || e.includes('Posted')) return '<span class="log-line-ok">' + e + '</span>';
  if (e.includes('INFO') || e.includes('▶') || e.includes('実行')) return '<span class="log-line-info">' + e + '</span>';
  return e;
}

// ---- ダッシュボード ----
async function loadDashboard() {
  try {
    const resp = await fetch('/api/status');
    const d = await resp.json();

    document.getElementById('mode-badge').textContent = d.mode.toUpperCase();

    const cards = [
      {label:'キュー', value: d.queue_count, sub:'投稿待ち', color: d.queue_count > 0 ? '#6c9cff' : '#555'},
      {label:'下書き', value: d.draft_count, sub:'レビュー待ち', color: d.draft_count > 0 ? '#fbbf24' : '#555'},
      {label:'今日の投稿', value: d.today_posts, sub:'/ ' + d.max_daily + '件', color:'#4ade80'},
      {label:'総投稿数', value: d.total_posts, sub:'累計', color:'#e0e0e0'},
    ];
    document.getElementById('stat-cards').innerHTML = cards.map(c =>
      '<div class="card"><div class="card-label">' + c.label + '</div><div class="card-value" style="color:' + c.color + '">' + c.value + '</div><div class="card-sub">' + c.sub + '</div></div>'
    ).join('');

    const apiItems = Object.entries(d.api_keys).map(function(kv) {
      return '<div class="api-item"><span class="status-dot ' + (kv[1] ? 'dot-green' : 'dot-red') + '"></span>' + kv[0].toUpperCase() + ': ' + (kv[1] ? 'OK' : 'MISSING') + '</div>';
    }).join('');
    document.getElementById('api-status').innerHTML = apiItems;

    const draftBadge = document.getElementById('draft-count-badge');
    if (d.draft_count > 0) {
      draftBadge.textContent = d.draft_count;
      draftBadge.style.display = 'inline';
    } else {
      draftBadge.style.display = 'none';
    }
  } catch(e) {
    console.error('loadDashboard error:', e);
  }
}

// ---- 下書きレビュー ----
async function loadDrafts() {
  try {
    const resp = await fetch('/api/drafts');
    const drafts = await resp.json();
    const pending = drafts.filter(function(d) { return d.status === 'draft'; });
    document.getElementById('review-count').textContent = pending.length > 0 ? '（' + pending.length + '件）' : '（なし）';

    if (pending.length === 0) {
      document.getElementById('drafts-container').innerHTML = '<div class="empty-state"><div class="empty-icon">✅</div>レビュー待ちの下書きはありません<br><br><button class="btn btn-primary" onclick="runAgent('writer')">Writerを実行して生成</button></div>';
      return;
    }

    document.getElementById('drafts-container').innerHTML = pending.map(function(d) {
      const score = d.score || 0;
      const scoreClass = score >= 8 ? 'score-high' : 'score-mid';
      const firstLine = (d.content || '').split('\n')[0].replace(/"/g, '&quot;');
      return '<div class="draft-card" id="draft-' + d.id + '">'
        + '<div class="draft-meta">'
        + '<span class="score-badge ' + scoreClass + '">★ ' + score + '</span>'
        + '<span class="tag">' + (d.pattern || '-') + '</span>'
        + '<span class="tag">' + (d.theme || '-') + '</span>'
        + '</div>'
        + '<div class="draft-content" id="content-' + d.id + '">' + (d.content || '').replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</div>'
        + '<div id="edit-area-' + d.id + '" style="display:none">'
        + '<input class="edit-input" id="edit-input-' + d.id + '" placeholder="1行目を入力" value="' + firstLine + '">'
        + '<div class="btn-group" style="margin-bottom:8px">'
        + '<button class="btn btn-primary" onclick="saveEdit('' + d.id + '')">保存して承認</button>'
        + '<button class="btn btn-ghost" onclick="cancelEdit('' + d.id + '')">キャンセル</button>'
        + '</div></div>'
        + '<div class="draft-actions">'
        + '<button class="btn btn-success" onclick="approveDraft('' + d.id + '')">✓ 承認</button>'
        + '<button class="btn btn-ghost" onclick="skipDraft('' + d.id + '')">スキップ</button>'
        + '<button class="btn btn-yellow" onclick="editDraft('' + d.id + '')">✏️ 1行目編集</button>'
        + '</div></div>';
    }).join('');
  } catch(e) {
    console.error('loadDrafts error:', e);
  }
}

function editDraft(id) { document.getElementById('edit-area-' + id).style.display = 'block'; }
function cancelEdit(id) { document.getElementById('edit-area-' + id).style.display = 'none'; }

async function saveEdit(id) {
  try {
    const newFirst = document.getElementById('edit-input-' + id).value;
    await fetch('/api/draft/edit', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id: id, new_first_line: newFirst})});
    await approveDraft(id);
  } catch(e) { console.error(e); }
}
async function approveDraft(id) {
  try {
    await fetch('/api/draft/approve', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id: id})});
    const el = document.getElementById('draft-' + id);
    if (el) { el.style.opacity = '0.3'; setTimeout(function(){ el.remove(); loadDrafts(); }, 600); }
  } catch(e) { console.error(e); }
}
async function skipDraft(id) {
  try {
    await fetch('/api/draft/skip', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id: id})});
    const el = document.getElementById('draft-' + id);
    if (el) { el.style.opacity = '0.3'; setTimeout(function(){ el.remove(); loadDrafts(); }, 400); }
  } catch(e) { console.error(e); }
}

// ---- 投稿履歴 ----
async function loadHistory() {
  try {
    const resp = await fetch('/api/history');
    const posts = await resp.json();
    const rows = posts.slice().reverse().map(function(p) {
      const dt = p.posted_at ? p.posted_at.slice(0,16).replace('T',' ') : (p.created_at ? p.created_at.slice(0,16).replace('T',' ') : '-');
      const m1 = p.metrics_1h || {};
      const m24 = p.metrics_24h || p.metrics || {};
      const views = m24.views || m1.views || '-';
      const likes = m24.likes || m1.likes || '-';
      const replies = m24.replies || m1.replies || '-';
      return '<tr><td>' + dt + '</td><td>' + (p.theme||'-') + '</td><td>' + (p.pattern||'-') + '</td><td>' + (p.score||'-') + '</td><td>' + views + '</td><td>' + likes + '</td><td>' + replies + '</td><td class="status-' + (p.status||'queued') + '">' + (p.status||'-') + '</td></tr>';
    }).join('');
    document.getElementById('history-table').innerHTML = rows || '<tr><td colspan="8" style="text-align:center;color:#555;padding:30px">投稿履歴がありません</td></tr>';
  } catch(e) { console.error(e); }
}

// ---- ASP ----
async function loadASP() {
  try {
    const resp = await fetch('/api/asp');
    const data = await resp.json();
    if (!data.programs || data.programs.length === 0) {
      document.getElementById('asp-list').innerHTML = '<div class="empty-state"><div class="empty-icon">💰</div>まだリサーチ結果がありません<br><br><button class="btn btn-primary" onclick="runAgent('asp')">ASPリサーチを実行</button></div>';
      return;
    }
    document.getElementById('asp-updated').textContent = data.researched_at ? '最終更新: ' + data.researched_at.slice(0,16).replace('T',' ') : '';
    document.getElementById('asp-list').innerHTML = data.programs.map(function(p, i) {
      return '<div class="asp-card">'
        + '<div class="asp-rank">' + (i+1) + '</div>'
        + '<div class="asp-info"><div class="asp-name">' + p.name + '</div>'
        + '<div class="asp-reward">💴 ' + p.reward + '円</div>'
        + '<div class="asp-approval">' + (p.approval_rate ? '承認率: ' + p.approval_rate : '') + (p.commission_type ? ' | ' + p.commission_type : '') + '</div></div>'
        + '<a href="https://www.a8.net/a8v2/performanceSearch.html?key=' + encodeURIComponent(p.name) + '" target="_blank" class="btn btn-ghost" style="font-size:11px;padding:6px 10px;">A8で探す</a>'
        + '</div>';
    }).join('');
  } catch(e) { console.error(e); }
}

// ---- ログ ----
async function loadLogs() {
  try {
    const resp = await fetch('/api/runlog');
    const data = await resp.json();
    const el = document.getElementById('full-log');
    el.innerHTML = data.lines.map(colorLine).join('<br>');
    el.scrollTop = el.scrollHeight;
  } catch(e) { console.error(e); }
}

// ---- KILL SWITCH ----
async function killSwitch() {
  if (!confirm('緊急停止します。全投稿が止まります。よろしいですか？')) return;
  try { await fetch('/api/kill', {method:'POST'}); } catch(e){}
  loadDashboard();
}
async function killSwitchOff() {
  try { await fetch('/api/kill_off', {method:'POST'}); } catch(e){}
  loadDashboard();
}

// ---- 初期ロード ----
loadDashboard();
setInterval(loadDashboard, 30000);
