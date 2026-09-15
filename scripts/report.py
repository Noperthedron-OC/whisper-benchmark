#!/usr/bin/env python3
"""
Generate a self-contained HTML report from metrics.json.
Handles any number of API backends dynamically.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

COLORS = {
    "local":             {"line": "#34d399", "fill": "#34d39966"},
    "whisper-1":         {"line": "#60a5fa", "fill": "#60a5fa66"},
    "gpt-4o-transcribe": {"line": "#f472b6", "fill": "#f472b666"},
    "gpt-4o-mini-transcribe": {"line": "#fb923c", "fill": "#fb923c66"},
}
DEFAULT_COLOR = {"line": "#a78bfa", "fill": "#a78bfa66"}


def color(key: str) -> dict:
    return COLORS.get(key, DEFAULT_COLOR)


def build_report(metrics: dict) -> str:
    agg = metrics["aggregate"]
    per_file = metrics["per_file"]
    backend_keys = agg.get("backend_keys", [])
    all_keys = ["local"] + backend_keys
    data_json = json.dumps(metrics, ensure_ascii=False)

    # Build summary stat cards
    def stat_card(value, label, key=""):
        c = color(key)["line"] if key else "var(--text)"
        return f'<div class="card"><div class="stat-value" style="color:{c}">{value}</div><div class="stat-label">{label}</div></div>'

    summary_row1 = ""
    if agg.get("local_rtf"):
        summary_row1 += stat_card(agg["local_rtf"]["mean"], "Local mean RTF", "local")
    for k in backend_keys:
        if agg.get(f"{k}_rtf"):
            summary_row1 += stat_card(agg[f"{k}_rtf"]["mean"], f"{k} mean RTF", k)
    total_cost = sum(agg.get(f"{k}_total_cost", 0) for k in backend_keys)
    summary_row1 += stat_card(f"${total_cost:.4f}", "Total API cost", "")

    summary_row2 = ""
    if agg.get("local_wer", {}).get("n"):
        summary_row2 += stat_card(agg["local_wer"]["mean"], f"Local WER vs iOS (n={agg['local_wer']['n']})", "local")
    for k in backend_keys:
        if agg.get(f"{k}_wer", {}).get("n"):
            summary_row2 += stat_card(agg[f"{k}_wer"]["mean"], f"{k} WER vs iOS", k)

    # Table header columns
    def th(label, idx):
        return f'<th onclick="sortTable({idx})">{label} ↕</th>'

    table_cols = ["File", "Duration", "Local time", "Local RTF", "Local WER"]
    for k in backend_keys:
        table_cols += [f"{k} time", f"{k} RTF", f"{k} WER", f"{k} cross-WER"]
    table_cols.append("Cost")
    th_html = "".join(th(c, i) for i, c in enumerate(table_cols))

    # Colors for charts as JS arrays
    js_colors_line = json.dumps([color(k)["line"] for k in all_keys])
    js_colors_fill = json.dumps([color(k)["fill"] for k in all_keys])
    js_backend_keys = json.dumps(backend_keys)
    js_all_keys = json.dumps(all_keys)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Whisper Benchmark Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f1117;--card:#1a1d27;--border:#2a2d3d;
    --text:#e2e8f0;--muted:#94a3b8;--accent:#6366f1;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;font-size:14px;line-height:1.6}}
  .container{{max-width:1400px;margin:0 auto;padding:24px}}
  h1{{font-size:1.5rem;font-weight:700;margin-bottom:4px}}
  h2{{font-size:1rem;font-weight:600;color:var(--muted);margin-bottom:16px}}
  h3{{font-size:.85rem;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
  .grid{{display:grid;gap:16px}}
  .g4{{grid-template-columns:repeat(4,1fr)}}
  .g3{{grid-template-columns:repeat(3,1fr)}}
  .g2{{grid-template-columns:repeat(2,1fr)}}
  @media(max-width:900px){{.g4,.g3,.g2{{grid-template-columns:1fr 1fr}}}}
  @media(max-width:500px){{.g4,.g3,.g2{{grid-template-columns:1fr}}}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px}}
  .stat-value{{font-size:2rem;font-weight:700;line-height:1}}
  .stat-label{{color:var(--muted);font-size:.8rem;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{padding:8px 10px;text-align:left;color:var(--muted);font-weight:600;border-bottom:1px solid var(--border);cursor:pointer;user-select:none;white-space:nowrap}}
  th:hover{{color:var(--text)}}
  td{{padding:7px 10px;border-bottom:1px solid #1f2233;vertical-align:top}}
  tr{{cursor:pointer;transition:background .1s}}
  tr:hover{{background:#1f2233}}
  tr.active{{background:#23273a}}
  .null{{color:var(--muted)}}
  .diff-panel{{display:none;margin-top:16px}}
  .diff-panel.visible{{display:block}}
  .diff-text{{font-size:.85rem;line-height:1.8}}
  mark.ins{{background:#14532d;color:#86efac;border-radius:3px;padding:0 2px}}
  mark.del{{background:transparent;color:#6b7280;text-decoration:line-through;padding:0 2px}}
  canvas{{max-height:280px}}
  .sec{{margin:28px 0 12px;font-size:1rem;font-weight:600}}
  .filter-bar{{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap;align-items:center}}
  input[type=text]{{background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:6px 12px;font-size:.85rem;flex:1;min-width:180px}}
  input[type=text]:focus{{outline:none;border-color:var(--accent)}}
  .wbar{{display:inline-block;height:8px;border-radius:4px;vertical-align:middle;margin-left:4px;opacity:.5}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:600;margin-right:4px}}
</style>
</head>
<body>
<div class="container">
  <h1>🎙 Whisper Benchmark</h1>
  <h2>{agg['total_files']} recordings &nbsp;·&nbsp; {agg['total_duration_min']:.1f} min audio &nbsp;·&nbsp; backends: local + {', '.join(backend_keys)}</h2>

  <div class="grid g4" style="margin-bottom:16px">{summary_row1}</div>
  {"" if not summary_row2 else f'<div class="grid g{min(len(all_keys),4)}" style="margin-bottom:20px">{summary_row2}</div>'}

  <div class="grid g2" style="margin-bottom:20px">
    <div class="card"><h3>Speed — Duration vs Transcription Time</h3><canvas id="speedChart"></canvas></div>
    <div class="card"><h3>Real-Time Factor per File</h3><canvas id="rtfChart"></canvas></div>
  </div>

  {"" if not agg.get("local_wer",{}).get("n") else '<div class="card" style="margin-bottom:20px"><h3>WER Distribution vs iOS Reference</h3><canvas id="werChart"></canvas></div>'}

  <p class="sec">Per-file results <span style="color:var(--muted);font-weight:400;font-size:.85em">— click a row to compare transcripts</span></p>
  <div class="filter-bar"><input type="text" id="fi" placeholder="Filter by filename…" oninput="filterTable()"></div>
  <div class="card" style="overflow-x:auto;margin-bottom:16px">
    <table id="rt"><thead><tr>{th_html}</tr></thead><tbody id="tb"></tbody></table>
  </div>

  <div id="diffPanel" class="diff-panel">
    <p class="sec" id="diffTitle">Transcript comparison</p>
    <div id="diffGrid" class="grid"></div>
  </div>
</div>

<script>
const DATA = {data_json};
const pf = DATA.per_file;
const agg = DATA.aggregate;
const backendKeys = {js_backend_keys};
const allKeys = {js_all_keys};
const colorsLine = {js_colors_line};
const colorsFill = {js_colors_fill};

// ── Helpers ───────────────────────────────────────────────────────────────
function fmt(v, d=3, sfx='') {{
  if(v===null||v===undefined) return '<span class="null">—</span>';
  return (+v).toFixed(d)+sfx;
}}
function fmtWer(v) {{
  if(v===null||v===undefined) return '<span class="null">—</span>';
  const pct=Math.min(v*100,100);
  const c=pct<20?'#4ade80':pct<40?'#facc15':'#f87171';
  return `<span style="color:${{c}}">${{(+v).toFixed(3)}}</span><span class="wbar" style="width:${{Math.round(pct)}}px;background:${{c}}"></span>`;
}}

// ── Table ─────────────────────────────────────────────────────────────────
let sortCol=1, sortAsc=false, activeRow=null;

function rowCols(r) {{
  const cols=[
    r.stem,
    r.duration_s?(r.duration_s/60).toFixed(1)+'m':'—',
    fmt(r.local_time_s,1,'s'), fmt(r.local_rtf,3), fmtWer(r.local_wer),
  ];
  for(const k of backendKeys) {{
    cols.push(fmt(r[k+'_time_s'],1,'s'), fmt(r[k+'_rtf'],3), fmtWer(r[k+'_wer']), fmtWer(r[k+'_cross_wer']));
  }}
  const totalCost = backendKeys.reduce((s,k)=>s+(r[k+'_cost_usd']||0),0);
  cols.push(totalCost?'$'+totalCost.toFixed(4):'<span class="null">—</span>');
  return cols;
}}

function buildRows(data) {{
  return data.map((r,i)=>`<tr data-i="${{i}}" onclick="selectRow(this)">${{rowCols(r).map(c=>`<td>${{c}}</td>`).join('')}}</tr>`).join('');
}}

let filteredData = pf;
function filterTable() {{
  const q=document.getElementById('fi').value.toLowerCase();
  filteredData=q?pf.filter(r=>r.stem.toLowerCase().includes(q)):pf;
  document.getElementById('tb').innerHTML=buildRows(filteredData);
}}

const sortKeys=['stem','duration_s','local_time_s','local_rtf','local_wer',
  ...backendKeys.flatMap(k=>[k+'_time_s',k+'_rtf',k+'_wer',k+'_cross_wer']),
  backendKeys[0]+'_cost_usd'];

function sortTable(col) {{
  if(sortCol===col) sortAsc=!sortAsc; else {{sortCol=col;sortAsc=true;}}
  const k=sortKeys[col];
  filteredData=[...filteredData].sort((a,b)=>{{
    const av=a[k],bv=b[k];
    if(av==null&&bv==null)return 0;
    if(av==null)return 1; if(bv==null)return -1;
    return sortAsc?(av>bv?1:-1):(av<bv?1:-1);
  }});
  document.getElementById('tb').innerHTML=buildRows(filteredData);
}}

// ── Diff viewer ───────────────────────────────────────────────────────────
function wordDiff(ref, hyp) {{
  if(!ref||!hyp) return hyp||'<span class="null">—</span>';
  const rw=ref.split(/[\\s]+/),hw=hyp.split(/[\\s]+/);
  const m=rw.length,n=hw.length;
  const dp=Array.from({{length:m+1}},()=>new Array(n+1).fill(0));
  for(let i=1;i<=m;i++) for(let j=1;j<=n;j++)
    dp[i][j]=rw[i-1].toLowerCase()===hw[j-1].toLowerCase()?dp[i-1][j-1]+1:Math.max(dp[i-1][j],dp[i][j-1]);
  const ops=[];let i=m,j=n;
  while(i>0||j>0){{
    if(i>0&&j>0&&rw[i-1].toLowerCase()===hw[j-1].toLowerCase()){{ops.push(['eq',hw[j-1]]);i--;j--;}}
    else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])){{ops.push(['ins',hw[j-1]]);j--;}}
    else{{ops.push(['del',rw[i-1]]);i--;}}
  }}
  ops.reverse();
  return ops.map(([t,w])=>t==='eq'?w:t==='ins'?`<mark class="ins">${{w}}</mark>`:`<mark class="del">${{w}}</mark>`).join(' ');
}}

function selectRow(tr) {{
  if(activeRow) activeRow.classList.remove('active');
  activeRow=tr; tr.classList.add('active');
  const stem=tr.querySelector('td').textContent;
  const rec=pf.find(x=>x.stem===stem)||filteredData[+tr.dataset.i];
  document.getElementById('diffTitle').textContent=`Transcript comparison — ${{rec.stem}}`;
  const ref=rec.ios_text||rec[backendKeys[0]+'_text']||'';
  const panels=[
    {{label:'iOS',key:'ios',text:rec.ios_text,color:'#f59e0b'}},
    {{label:'Local',key:'local',text:rec.local_text,color:'#34d399'}},
    ...backendKeys.map((k,i)=>{{return{{label:k,key:k,text:rec[k+'_text'],color:colorsLine[i+1]}}}})
  ];
  const grid=document.getElementById('diffGrid');
  grid.style.gridTemplateColumns=`repeat(${{panels.length}},1fr)`;
  grid.innerHTML=panels.map(p=>`
    <div class="card">
      <h3 style="color:${{p.color}}">${{p.label}}</h3>
      <div class="diff-text">${{p.key==='ios'?(p.text||'<span class="null">No iOS reference</span>'):wordDiff(ref,p.text)}}</div>
    </div>`).join('');
  document.getElementById('diffPanel').classList.add('visible');
  document.getElementById('diffPanel').scrollIntoView({{behavior:'smooth',block:'nearest'}});
}}

// ── Charts ────────────────────────────────────────────────────────────────
const chartOpts = {{
  plugins:{{legend:{{labels:{{color:'#94a3b8'}}}}}},
  scales:{{
    x:{{ticks:{{color:'#64748b'}},grid:{{color:'#1f2233'}}}},
    y:{{ticks:{{color:'#64748b'}},grid:{{color:'#1f2233'}}}}
  }}
}};

// Speed scatter
const withLocal = pf.filter(r=>r.local_time_s);
new Chart(document.getElementById('speedChart'),{{
  type:'scatter',
  data:{{datasets:[
    {{label:'Local',data:withLocal.map(r=>{{return{{x:r.duration_s,y:r.local_time_s}}}}),backgroundColor:'#34d399aa',pointRadius:5}},
    ...backendKeys.map((k,i)=>{{
      const d=pf.filter(r=>r[k+'_time_s']);
      return{{label:k,data:d.map(r=>{{return{{x:r.duration_s,y:r[k+'_time_s']}}}}),backgroundColor:colorsLine[i+1]+'aa',pointRadius:5}};
    }})
  ]}},
  options:{{...chartOpts,scales:{{
    x:{{...chartOpts.scales.x,title:{{display:true,text:'Audio duration (s)',color:'#64748b'}}}},
    y:{{...chartOpts.scales.y,title:{{display:true,text:'Transcription time (s)',color:'#64748b'}}}}
  }}}}
}});

// RTF bar
const rtfData=pf.filter(r=>r.local_rtf||backendKeys.some(k=>r[k+'_rtf']));
new Chart(document.getElementById('rtfChart'),{{
  type:'bar',
  data:{{
    labels:rtfData.map(r=>r.stem.slice(5,16)),
    datasets:[
      {{label:'Local RTF',data:rtfData.map(r=>r.local_rtf),backgroundColor:'#34d39966'}},
      ...backendKeys.map((k,i)=>{{return{{label:k+' RTF',data:rtfData.map(r=>r[k+'_rtf']),backgroundColor:colorsFill[i+1]}}}})
    ]
  }},
  options:{{...chartOpts,scales:{{
    x:{{...chartOpts.scales.x,ticks:{{maxRotation:90,font:{{size:9}},color:'#64748b'}}}},
    y:{{...chartOpts.scales.y,title:{{display:true,text:'RTF',color:'#64748b'}}}}
  }}}}
}});

// WER histogram
const werEl=document.getElementById('werChart');
if(werEl){{
  const buckets=new Array(10).fill(0);
  const localH=[...buckets],apiHists=Object.fromEntries(backendKeys.map(k=>[k,[...buckets]]));
  pf.forEach(r=>{{
    if(r.local_wer!=null) localH[Math.min(Math.floor(r.local_wer*10),9)]++;
    backendKeys.forEach(k=>{{ if(r[k+'_wer']!=null) apiHists[k][Math.min(Math.floor(r[k+'_wer']*10),9)]++; }});
  }});
  new Chart(werEl,{{
    type:'bar',
    data:{{
      labels:['0–10%','10–20%','20–30%','30–40%','40–50%','50–60%','60–70%','70–80%','80–90%','90–100%'],
      datasets:[
        {{label:'Local WER',data:localH,backgroundColor:'#34d39966'}},
        ...backendKeys.map((k,i)=>{{return{{label:k+' WER',data:apiHists[k],backgroundColor:colorsFill[i+1]}}}})
      ]
    }},
    options:{{...chartOpts,scales:{{
      x:{{...chartOpts.scales.x,title:{{display:true,text:'WER bucket',color:'#64748b'}}}},
      y:{{...chartOpts.scales.y,title:{{display:true,text:'# files',color:'#64748b'}}}}
    }}}}
  }});
}}

// Init
filteredData=pf;
document.getElementById('tb').innerHTML=buildRows(pf);
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
