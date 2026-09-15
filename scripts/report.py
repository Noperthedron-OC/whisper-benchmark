#!/usr/bin/env python3
"""
Generate a self-contained HTML report from metrics.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def build_report(metrics: dict) -> str:
    agg = metrics["aggregate"]
    per_file = metrics["per_file"]
    data_json = json.dumps(metrics, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Whisper Benchmark Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --card: #1a1d27; --border: #2a2d3d;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #6366f1;
    --local: #34d399; --api: #60a5fa; --ios: #f59e0b;
    --red: #f87171; --green: #4ade80; --grey: #6b7280;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 14px; line-height: 1.6; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
  h1 {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ font-size: 1rem; font-weight: 600; color: var(--muted); margin-bottom: 16px; }}
  h3 {{ font-size: 0.9rem; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }}
  .grid {{ display: grid; gap: 16px; }}
  .grid-4 {{ grid-template-columns: repeat(4, 1fr); }}
  .grid-2 {{ grid-template-columns: repeat(2, 1fr); }}
  @media (max-width: 900px) {{ .grid-4, .grid-2 {{ grid-template-columns: 1fr 1fr; }} }}
  @media (max-width: 500px) {{ .grid-4, .grid-2 {{ grid-template-columns: 1fr; }} }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }}
  .stat-value {{ font-size: 2rem; font-weight: 700; line-height: 1; }}
  .stat-label {{ color: var(--muted); font-size: 0.8rem; margin-top: 4px; }}
  .local {{ color: var(--local); }}
  .api {{ color: var(--api); }}
  .ios {{ color: var(--ios); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }}
  .badge-local {{ background: #064e3b; color: var(--local); }}
  .badge-api {{ background: #1e3a5f; color: var(--api); }}
  .badge-ios {{ background: #451a03; color: var(--ios); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ padding: 8px 10px; text-align: left; color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; white-space: nowrap; }}
  th:hover {{ color: var(--text); }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #1f2233; vertical-align: top; }}
  tr {{ cursor: pointer; transition: background 0.1s; }}
  tr:hover {{ background: #1f2233; }}
  tr.active {{ background: #23273a; }}
  .null {{ color: var(--muted); }}
  .diff-panel {{ display: none; margin-top: 16px; }}
  .diff-panel.visible {{ display: block; }}
  .diff-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }}
  @media (max-width: 800px) {{ .diff-grid {{ grid-template-columns: 1fr; }} }}
  .diff-col {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .diff-col h4 {{ font-size: 0.8rem; margin-bottom: 10px; }}
  .diff-text {{ font-size: 0.85rem; line-height: 1.7; }}
  mark.sub {{ background: #7f1d1d; color: #fca5a5; border-radius: 3px; padding: 0 2px; }}
  mark.ins {{ background: #14532d; color: #86efac; border-radius: 3px; padding: 0 2px; }}
  mark.del {{ background: transparent; color: var(--grey); text-decoration: line-through; padding: 0 2px; }}
  canvas {{ max-height: 280px; }}
  .section-title {{ margin: 28px 0 12px; font-size: 1rem; font-weight: 600; }}
  .filter-bar {{ display: flex; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }}
  input[type=text] {{ background: var(--card); border: 1px solid var(--border); color: var(--text); border-radius: 6px; padding: 6px 12px; font-size: 0.85rem; flex: 1; min-width: 180px; }}
  input[type=text]:focus {{ outline: none; border-color: var(--accent); }}
  .wer-bar {{ display: inline-block; height: 8px; border-radius: 4px; vertical-align: middle; margin-left: 4px; }}
</style>
</head>
<body>
<div class="container">
  <h1>🎙 Whisper Benchmark</h1>
  <h2>local whisper.cpp vs OpenAI Whisper API &nbsp;·&nbsp; {agg['total_files']} recordings &nbsp;·&nbsp; {agg['total_duration_min']:.1f} min audio</h2>

  <!-- Summary stats -->
  <div class="grid grid-4" style="margin-bottom:20px">
    <div class="card">
      <div class="stat-value local">{agg['local_rtf'].get('mean', 'N/A') if agg['local_rtf'] else 'N/A'}</div>
      <div class="stat-label">Local mean RTF <span style="font-size:0.75em">(lower = faster)</span></div>
    </div>
    <div class="card">
      <div class="stat-value api">{agg['api_rtf'].get('mean', 'N/A') if agg['api_rtf'] else 'N/A'}</div>
      <div class="stat-label">API mean RTF</div>
    </div>
    <div class="card">
      <div class="stat-value" style="color:#f59e0b">{agg['cross_wer'].get('mean', 'N/A') if agg['cross_wer'] else 'N/A'}</div>
      <div class="stat-label">Cross-WER (local vs API agreement)</div>
    </div>
    <div class="card">
      <div class="stat-value" style="color:#e879f9">${agg['total_api_cost_usd']:.4f}</div>
      <div class="stat-label">Total API cost (whisper-1)</div>
    </div>
  </div>

  {"" if not agg['local_wer'] else f'''
  <div class="grid grid-4" style="margin-bottom:20px">
    <div class="card">
      <div class="stat-value local">{agg["local_wer"].get("mean","N/A")}</div>
      <div class="stat-label">Local mean WER vs iOS ref (n={agg["local_wer"].get("n",0)})</div>
    </div>
    <div class="card">
      <div class="stat-value api">{agg["api_wer"].get("mean","N/A")}</div>
      <div class="stat-label">API mean WER vs iOS ref</div>
    </div>
    <div class="card">
      <div class="stat-value local">{agg["local_wer"].get("median","N/A")}</div>
      <div class="stat-label">Local median WER</div>
    </div>
    <div class="card">
      <div class="stat-value api">{agg["api_wer"].get("median","N/A")}</div>
      <div class="stat-label">API median WER</div>
    </div>
  </div>
  '''}

  <!-- Charts -->
  <div class="grid grid-2" style="margin-bottom:20px">
    <div class="card">
      <h3>Speed — Audio Duration vs Transcription Time</h3>
      <canvas id="speedChart"></canvas>
    </div>
    <div class="card">
      <h3>Real-Time Factor per File</h3>
      <canvas id="rtfChart"></canvas>
    </div>
  </div>

  {"" if not agg['local_wer'] else '''
  <div class="card" style="margin-bottom:20px">
    <h3>WER Distribution vs iOS Reference</h3>
    <canvas id="werChart"></canvas>
  </div>
  '''}

  <!-- Table -->
  <p class="section-title">Per-file results <span style="color:var(--muted);font-weight:400;font-size:0.85em">— click a row to compare transcripts</span></p>
  <div class="filter-bar">
    <input type="text" id="filterInput" placeholder="Filter by filename…" oninput="filterTable()">
  </div>
  <div class="card" style="overflow-x:auto;margin-bottom:16px">
    <table id="resultsTable">
      <thead>
        <tr>
          <th onclick="sortTable(0)">File ↕</th>
          <th onclick="sortTable(1)">Duration ↕</th>
          <th onclick="sortTable(2)">Local time ↕</th>
          <th onclick="sortTable(3)">Local RTF ↕</th>
          <th onclick="sortTable(4)">API time ↕</th>
          <th onclick="sortTable(5)">API RTF ↕</th>
          <th onclick="sortTable(6)">Local WER ↕</th>
          <th onclick="sortTable(7)">API WER ↕</th>
          <th onclick="sortTable(8)">Cross-WER ↕</th>
          <th onclick="sortTable(9)">API cost ↕</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>

  <!-- Diff panel -->
  <div id="diffPanel" class="diff-panel">
    <p class="section-title" id="diffTitle">Transcript comparison</p>
    <div class="diff-grid">
      <div class="diff-col">
        <h4><span class="badge badge-ios">iOS</span> reference</h4>
        <div class="diff-text" id="diffIos">—</div>
      </div>
      <div class="diff-col">
        <h4><span class="badge badge-local">Local</span> whisper.cpp</h4>
        <div class="diff-text" id="diffLocal">—</div>
      </div>
      <div class="diff-col">
        <h4><span class="badge badge-api">API</span> whisper-1</h4>
        <div class="diff-text" id="diffApi">—</div>
      </div>
    </div>
  </div>
</div>

<script>
const DATA = {data_json};
const perFile = DATA.per_file;

// ── Table ─────────────────────────────────────────────────────────────────
let sortCol = 1, sortAsc = false, activeRow = null;

function fmt(v, decimals=3, suffix='') {{
  if (v === null || v === undefined) return '<span class="null">—</span>';
  return (+v).toFixed(decimals) + suffix;
}}
function fmtWer(v) {{
  if (v === null || v === undefined) return '<span class="null">—</span>';
  const pct = Math.min(v * 100, 100);
  const col = pct < 20 ? '#4ade80' : pct < 40 ? '#facc15' : '#f87171';
  return `<span style="color:${{col}}">${{(+v).toFixed(3)}}</span>
    <span class="wer-bar" style="width:${{Math.round(pct)}}px;background:${{col}};opacity:0.4"></span>`;
}}

function buildRows(data) {{
  return data.map((r, i) => {{
    const cols = [
      r.stem,
      r.duration_s ? (r.duration_s/60).toFixed(1)+'m' : '—',
      fmt(r.local_time_s, 1, 's'),
      fmt(r.local_rtf, 3),
      fmt(r.api_time_s, 1, 's'),
      fmt(r.api_rtf, 3),
      fmtWer(r.local_wer),
      fmtWer(r.api_wer),
      fmtWer(r.cross_wer),
      r.api_cost_usd ? '$'+r.api_cost_usd.toFixed(4) : '<span class="null">—</span>',
    ];
    return `<tr data-idx="${{i}}" onclick="selectRow(this,${{i}})">${{cols.map(c=>`<td>${{c}}</td>`).join('')}}</tr>`;
  }}).join('');
}}

function filterTable() {{
  const q = document.getElementById('filterInput').value.toLowerCase();
  const filtered = q ? perFile.filter(r => r.stem.toLowerCase().includes(q)) : perFile;
  document.getElementById('tableBody').innerHTML = buildRows(filtered);
}}

function sortTable(col) {{
  if (sortCol === col) sortAsc = !sortAsc; else {{ sortCol = col; sortAsc = true; }}
  const keys = ['stem','duration_s','local_time_s','local_rtf','api_time_s','api_rtf','local_wer','api_wer','cross_wer','api_cost_usd'];
  const k = keys[col];
  const sorted = [...perFile].sort((a,b) => {{
    const av = a[k], bv = b[k];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  }});
  document.getElementById('tableBody').innerHTML = buildRows(sorted);
}}

// ── Diff viewer ───────────────────────────────────────────────────────────
function wordDiff(ref, hyp) {{
  if (!ref || !hyp) return hyp || '<span class="null">—</span>';
  const rw = ref.split(/[\s]+/), hw = hyp.split(/[\s]+/);
  // Simple LCS-based diff
  const m = rw.length, n = hw.length;
  const dp = Array.from({{length: m+1}}, () => new Array(n+1).fill(0));
  for (let i=1;i<=m;i++) for (let j=1;j<=n;j++)
    dp[i][j] = rw[i-1].toLowerCase()===hw[j-1].toLowerCase() ? dp[i-1][j-1]+1 : Math.max(dp[i-1][j],dp[i][j-1]);
  // Trace back
  const ops = []; let i=m, j=n;
  while (i>0||j>0) {{
    if (i>0&&j>0&&rw[i-1].toLowerCase()===hw[j-1].toLowerCase()) {{ ops.push(['eq',hw[j-1]]); i--;j--; }}
    else if (j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])) {{ ops.push(['ins',hw[j-1]]); j--; }}
    else {{ ops.push(['del',rw[i-1]]); i--; }}
  }}
  ops.reverse();
  return ops.map(([t,w])=>{{
    if (t==='eq') return w;
    if (t==='ins') return `<mark class="ins">${{w}}</mark>`;
    return `<mark class="del">${{w}}</mark>`;
  }}).join(' ');
}}

function selectRow(tr, idx) {{
  if (activeRow) activeRow.classList.remove('active');
  activeRow = tr; tr.classList.add('active');
  const r = perFile[idx] || perFile.find((_,i)=>i===idx);
  // find actual record by stem
  const stem = tr.querySelector('td').textContent;
  const rec = perFile.find(x => x.stem === stem) || perFile[idx];
  document.getElementById('diffTitle').textContent = `Transcript comparison — ${{rec.stem}}`;
  document.getElementById('diffIos').innerHTML = rec.ios_text || '<span class="null">No iOS reference</span>';
  const ref = rec.ios_text || rec.api_text || '';
  document.getElementById('diffLocal').innerHTML = rec.local_text ? wordDiff(ref, rec.local_text) : '<span class="null">—</span>';
  document.getElementById('diffApi').innerHTML = rec.api_text ? wordDiff(ref, rec.api_text) : '<span class="null">—</span>';
  document.getElementById('diffPanel').classList.add('visible');
  document.getElementById('diffPanel').scrollIntoView({{behavior:'smooth',block:'nearest'}});
}}

// ── Charts ────────────────────────────────────────────────────────────────
const chartDefaults = {{
  plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
  scales: {{
    x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1f2233' }} }},
    y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1f2233' }} }},
  }}
}};

// Speed scatter
const withBoth = perFile.filter(r => r.local_time_s && r.api_time_s);
new Chart(document.getElementById('speedChart'), {{
  type: 'scatter',
  data: {{
    datasets: [
      {{ label: 'Local', data: withBoth.map(r=>{{return{{x:r.duration_s,y:r.local_time_s}}}}), backgroundColor:'#34d399aa', pointRadius:5 }},
      {{ label: 'API',   data: withBoth.map(r=>{{return{{x:r.duration_s,y:r.api_time_s}}}}),   backgroundColor:'#60a5faaa', pointRadius:5 }},
    ]
  }},
  options: {{ ...chartDefaults, plugins: {{ ...chartDefaults.plugins, tooltip: {{ callbacks: {{ label: ctx=>{{
    const r=withBoth[ctx.dataIndex]; return `${{ctx.dataset.label}}: ${{r.duration_s.toFixed(0)}}s audio → ${{ctx.parsed.y.toFixed(1)}}s`;
  }}}} }}, legend: chartDefaults.plugins.legend }},
  scales: {{ x: {{ ...chartDefaults.scales.x, title:{{display:true,text:'Audio duration (s)',color:'#64748b'}} }},
             y: {{ ...chartDefaults.scales.y, title:{{display:true,text:'Transcription time (s)',color:'#64748b'}} }} }} }}
}});

// RTF bar chart
const rtfData = perFile.filter(r=>r.local_rtf||r.api_rtf).slice(0,44);
new Chart(document.getElementById('rtfChart'), {{
  type: 'bar',
  data: {{
    labels: rtfData.map(r=>r.stem.slice(5,16)),
    datasets: [
      {{ label:'Local RTF', data:rtfData.map(r=>r.local_rtf), backgroundColor:'#34d39966' }},
      {{ label:'API RTF',   data:rtfData.map(r=>r.api_rtf),   backgroundColor:'#60a5fa66' }},
    ]
  }},
  options: {{ ...chartDefaults, scales: {{
    x: {{ ...chartDefaults.scales.x, ticks:{{ maxRotation:90,font:{{size:9}},color:'#64748b' }} }},
    y: {{ ...chartDefaults.scales.y, title:{{display:true,text:'RTF',color:'#64748b'}} }}
  }} }}
}});

// WER histogram
const werEl = document.getElementById('werChart');
if (werEl) {{
  const buckets = [0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0];
  const lwerHist = new Array(10).fill(0), awerHist = new Array(10).fill(0), cwerHist = new Array(10).fill(0);
  perFile.forEach(r=>{{
    if (r.local_wer!=null) lwerHist[Math.min(Math.floor(r.local_wer*10),9)]++;
    if (r.api_wer!=null)   awerHist[Math.min(Math.floor(r.api_wer*10),9)]++;
    if (r.cross_wer!=null) cwerHist[Math.min(Math.floor(r.cross_wer*10),9)]++;
  }});
  new Chart(werEl, {{
    type:'bar',
    data:{{
      labels:['0–10%','10–20%','20–30%','30–40%','40–50%','50–60%','60–70%','70–80%','80–90%','90–100%'],
      datasets:[
        {{label:'Local WER',data:lwerHist,backgroundColor:'#34d39966'}},
        {{label:'API WER',  data:awerHist,backgroundColor:'#60a5fa66'}},
        {{label:'Cross-WER',data:cwerHist,backgroundColor:'#f59e0b66'}},
      ]
    }},
    options:{{...chartDefaults,scales:{{
      x:{{...chartDefaults.scales.x,title:{{display:true,text:'WER bucket',color:'#64748b'}}}},
      y:{{...chartDefaults.scales.y,title:{{display:true,text:'# files',color:'#64748b'}}}}
    }}}}
  }});
}}

// Initial render
document.getElementById('tableBody').innerHTML = buildRows(perFile);
</script>
</body>
</html>"""


def main():
    if not config.METRICS_FILE.exists():
        print("metrics.json not found. Run analyze.py first.")
        sys.exit(1)
    metrics = json.loads(config.METRICS_FILE.read_text())
    html = build_report(metrics)
    config.REPORT_FILE.write_text(html)
    print(f"Report written to {config.REPORT_FILE}")


if __name__ == "__main__":
    main()
