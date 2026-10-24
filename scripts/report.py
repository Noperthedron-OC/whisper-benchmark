#!/usr/bin/env python3
"""
Generate a self-contained HTML report from metrics.json.
Handles any number of API backends dynamically.
"""

import json
import re
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


def sanitize(metrics: dict) -> dict:
    """Public version: drop every transcript text and replace recording names
    (timestamps of private voice notes) with neutral numbers. Numbers only."""
    per_file = []
    for i, r in enumerate(metrics["per_file"], 1):
        clean = {k: v for k, v in r.items() if not k.endswith("_text") and k != "stem"}
        clean["stem"] = f"Rec {i:02d}"
        per_file.append(clean)
    return {"per_file": per_file, "aggregate": metrics["aggregate"]}


def _mean(v):
    return sum(v) / len(v) if v else None


def _median(v):
    v = sorted(v)
    if not v:
        return None
    mid = len(v) // 2
    return v[mid] if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def _f(x, d=3):
    return "&ndash;" if x is None else f"{x:.{d}f}"


def repetition_stats(per_file: list, keys: list, max_len: int = 6) -> dict:
    """Count places where a word or a phrase (1-6 words) is directly followed by itself.
    Needs the transcripts, so it runs before sanitize(); only counts leave this function.
    Some repeats are real speech (stuttering, lists of names), so this is an indicator."""
    def words(t):
        return re.findall(r"\S+", t or "")

    def norm(w):
        return re.sub(r"[^\w]", "", w.lower())

    out = {}
    for k in keys:
        events = phrase = sentence_like = files_n = long_files = 0
        for r in per_file:
            w = words(r.get(f"{k}_text"))
            nw = [norm(x) for x in w]
            i, found = 0, 0
            while i < len(w):
                for n in range(1, max_len + 1):
                    if i + 2 * n <= len(w) and all(nw[i:i + n]) and nw[i:i + n] == nw[i + n:i + 2 * n]:
                        found += 1
                        phrase += n > 1
                        sentence_like += bool(re.search(r"[.!?,;:]$", w[i + n - 1]))
                        i += 2 * n - 1
                        break
                i += 1
            if found:
                events += found
                files_n += 1
                long_files += r["duration_s"] >= 180
        out[k] = {"events": events, "files": files_n, "phrase": phrase,
                  "sentence_like": sentence_like, "long_files": long_files}
    return out


def observations_html(agg: dict, inc: list, allrows: list, keys: list, rep: dict) -> str:
    """Observations. All numbers are computed from the per-file data, over the analysed files
    (`inc`) unless stated otherwise, so the text stays in step with the data."""
    gt = agg.get("ground_truth_key", "gpt-4o-transcribe")
    others = [k for k in keys if k != gt]  # systems that have a WER against the reference
    audio_min = sum(r["duration_s"] for r in inc) / 60
    minw = agg.get("min_reference_words", 10)
    excl = len(allrows) - len(inc)

    def total_min(k):
        return sum(r.get(f"{k}_time_s", 0) for r in inc) / 60

    t_local, t_gt = total_min("local"), total_min(gt)
    slower = t_local / t_gt if t_gt else 0
    rtf_ratio = (agg["local_rtf"]["mean"] / agg[f"{gt}_rtf"]["mean"]) if agg.get(f"{gt}_rtf") else 0
    over_rt = sum(1 for r in inc if (r.get("local_rtf") or 0) > 1)
    rtf_short = _median([r["local_rtf"] for r in inc if r["duration_s"] < 60 and r.get("local_rtf")])
    rtf_long = _median([r["local_rtf"] for r in inc if r["duration_s"] >= 180 and r.get("local_rtf")])
    cost = agg.get(f"{gt}_total_cost", 0)
    month = 30 * 60 * 0.006

    # WER by recording length
    buckets = [("under 1 min", 0, 60), ("1 to 3 min", 60, 180), ("3 min and longer", 180, 10**9)]
    wer_rows = ""
    for label, lo, hi in buckets:
        cells, n_b = "", 0
        for k in others:
            v = [r[f"{k}_wer"] for r in inc if lo <= r["duration_s"] < hi and r.get(f"{k}_wer") is not None]
            n_b = len(v)
            cells += f"<td>{_f(_mean(v))}</td><td>{_f(_median(v))}</td>"
        wer_rows += f"<tr><td>{label}</td><td>{n_b}</td>{cells}</tr>"
    wer_head = "".join(f"<th>{k} mean</th><th>{k} median</th>" for k in others)

    # What the excluded recordings would have done to the error rates
    ex_rows = ""
    for k in others:
        all_v = [r[f"{k}_wer"] for r in allrows if r.get(f"{k}_wer") is not None]
        kept_v = [r[f"{k}_wer"] for r in inc if r.get(f"{k}_wer") is not None]
        ex_rows += (f"<tr><td>{k}</td><td>{_f(_mean(kept_v))}</td><td>{_f(_mean(all_v))}</td></tr>")

    rl = rep.get("local", {})
    other_rep = "; ".join(
        f"{k}: {rep[k]['events']} in {rep[k]['files']} files" for k in keys if k != "local" and k in rep)

    return f"""
  <h3>Observations</h3>
  <ol>
    <li><b>Speed is the clear difference.</b> For {audio_min:.0f} minutes of audio, {gt} needed
        {t_gt:.1f} minutes in total, local {t_local:.0f} minutes: local was about {slower:.0f} times slower
        (about {rtf_ratio:.0f} times by mean RTF). {gt} is also slightly faster than whisper-1.
        Local was slower than real time (RTF above 1) on {over_rt} of {len(inc)} files.</li>
    <li><b>Local speed depends on file length.</b> Short files carry a fixed cost, because the model is loaded
        for every call (this is a likely explanation, not measured separately). Median local RTF falls from
        {_f(rtf_short, 2)} for files under a minute to {_f(rtf_long, 2)} for files of 3 minutes and more.
        The online services are fast at every length.</li>
    <li><b>Cost is a non-issue at this volume.</b> Both online models charge $0.006 per minute: ${cost:.2f} for
        the whole corpus (all {len(allrows)} files were billed). 30 hours of voice notes per month would be about
        ${month:.2f}. Local costs nothing per file, but occupied the server&rsquo;s processor for
        {t_local:.0f} minutes for these files.</li>
    <li><b>Accuracy: close on average, but different by recording length.</b> Against the reference, local and
        whisper-1 have similar mean error rates (see the cards above). By recording length the picture differs;
        in this run, local was clearly further from the reference on the longest recordings:
      <table class="mini"><thead><tr><th>recording length</th><th>files</th>{wer_head}</tr></thead>
      <tbody>{wer_rows}</tbody></table>
      With only a handful of files per band this is an indication, not proof.</li>
    <li><b>The local model sometimes repeats words or whole phrases.</b> A word or phrase directly followed
        by itself occurs {rl.get('events', 0)} times in the local transcripts, spread over {rl.get('files', 0)} files
        ({other_rep}). {rl.get('phrase', 0)} of the local cases are phrases of two or more words, and
        {rl.get('sentence_like', 0)} repeat a unit that ends a clause or sentence, i.e. the end of a sentence is said
        again, in some cases three or four times in a row before the text moves on. {rl.get('long_files', 0)} of the
        {rl.get('files', 0)} affected files are longer than 3 minutes. That looks like the known &ldquo;repetition loop&rdquo;
        of Whisper-type models. Some repeats are real speech (stuttering, a list of names, &ldquo;like like&rdquo;), so not
        every case is an error. Every wrongly repeated passage adds insertions and thus raises the WER of the local
        model; the reference text has no such passages.</li>
    <li><b>{excl} nearly empty recordings were left out.</b> Their reference has fewer than {minw} words (very
        little speech). One word more or less is then a 10&ndash;100% error, which says nothing about quality, and
        a very short clip can also distort the speed figures. They are excluded from all speed and error
        statistics, stay in the table (greyed out) and in the cost total. Mean WER with and without them:
      <table class="mini"><thead><tr><th>system</th><th>analysed files</th><th>if all files were counted</th></tr></thead>
      <tbody>{ex_rows}</tbody></table></li>
  </ol>
"""


def summary_html(agg: dict, inc: list, allrows: list, keys: list, rep: dict) -> str:
    """Short summary shown above everything else. Numbers are computed from the data."""
    gt = agg.get("ground_truth_key", "gpt-4o-transcribe")
    audio_min = sum(r["duration_s"] for r in inc) / 60
    t_local = sum(r.get("local_time_s", 0) for r in inc) / 60
    t_gt = sum(r.get(f"{gt}_time_s", 0) for r in inc) / 60
    slower = t_local / t_gt if t_gt else 0
    cost = agg.get(f"{gt}_total_cost", 0)
    others = [k for k in keys if k != gt]
    wer = {k: [r[f"{k}_wer"] for r in inc if r.get(f"{k}_wer") is not None] for k in others}
    cells = "; ".join(f"{k}: mean {_f(_mean(v))}, median {_f(_median(v))}" for k, v in wer.items())
    rl = rep.get("local", {})
    excl = len(allrows) - len(inc)
    return f"""
<div class="card" style="margin-bottom:20px">
  <h3>Summary</h3>
  <p style="margin-bottom:8px">Three speech-to-text systems transcribed the same {len(allrows)} voice recordings.
  {excl} nearly empty ones were left out of the statistics, so {len(inc)} files ({audio_min:.0f} minutes) were
  compared on speed, cost and agreement with a reference.</p>
  <ul style="padding-left:20px;line-height:1.7">
    <li><b>Speed:</b> {gt} took {t_gt:.1f} minutes in total, the local model {t_local:.0f} minutes, about
        {slower:.0f} times longer. The local model ran on the processor only.</li>
    <li><b>Cost:</b> ${cost:.2f} for the whole corpus with either online model ($0.006 per minute); local costs nothing per file.</li>
    <li><b>Agreement with the reference ({gt}), error rate:</b> {cells}.
        Averages are close, the online whisper-1 is better at the median.</li>
    <li><b>Where local is weaker:</b> long recordings (3 minutes and more) and repetitions: words or whole phrases
        are repeated, {rl.get('events', 0)} times in {rl.get('files', 0)} files, sometimes several times in a row.</li>
    <li><b>Caution:</b> the reference is itself a machine transcription, so the error rates show agreement, not
        truth. Only {len(inc)} files from one speaker, one run on one server.</li>
  </ul>
</div>
"""


def about_html(agg: dict, inc: list, allrows: list, keys: list, public: bool, rep: dict) -> str:
    gt = agg.get("ground_truth_key", "gpt-4o-transcribe")
    minw = agg.get("min_reference_words", 10)
    excl = len(allrows) - len(inc)
    total_min = sum(r["duration_s"] for r in allrows) / 60
    inc_min = sum(r["duration_s"] for r in inc) / 60
    removed = ("<p><b>Privacy:</b> This public version contains numbers only. All transcripts and the "
               "recording names (which contained date and time) were removed. Files are numbered "
               "<i>Rec 01 &hellip; Rec "
               f"{len(allrows):02d}</i>. The side-by-side transcript viewer of the full report is "
               "not included.</p>") if public else ""
    return f"""
<details class="card about" open>
  <summary>About this report &mdash; what was measured, how, and what the abbreviations mean</summary>

  <h3>What was done</h3>
  <p>The same {len(allrows)} voice recordings ({total_min:.0f} minutes in total, natural speech, mixed German and
  English, recorded on a phone) were transcribed by three speech-to-text systems. {excl} recordings with almost
  no speech were left out of the speed and error statistics; the remaining {len(inc)} ({inc_min:.0f} minutes)
  were compared. Speed, cost and agreement between the systems were measured. The goal: is it worth paying for an
  online service, or is a model that runs on the home server good and fast enough?</p>

  <h3>The three systems</h3>
  <ul>
    <li><b>local</b> &mdash; <i>whisper.cpp</i> with the model <i>large-v3-turbo</i> (compressed to 5 bit,
        &ldquo;q5_0&rdquo;), running on the server&rsquo;s processor (CPU), no graphics card. Language is
        detected automatically. Nothing leaves the machine.</li>
    <li><b>whisper-1</b> &mdash; OpenAI&rsquo;s online transcription service with the classic Whisper model.</li>
    <li><b>{gt}</b> &mdash; OpenAI&rsquo;s newer, GPT-4o based online transcription model.
        Both online services cost $0.006 per audio minute.</li>
  </ul>

  <h3>How it was measured</h3>
  <ul>
    <li><b>Time:</b> stopwatch around the transcription call. Local: only the run of the program
        (including loading the model each time); the preceding conversion of the audio to a 16 kHz WAV file
        is <i>not</i> counted. Online: from sending the request (including upload of the audio file) until the text
        is back. Files were processed one after the other, once each.</li>
    <li><b>Reference:</b> there is no human-written transcript. <b>{gt}</b> serves as the
        reference, so its own error rate is 0 by definition. All error rates therefore measure
        <i>agreement with {gt}</i>, not absolute correctness. Both of the other systems
        can be right where the reference is wrong.</li>
    <li><b>Settings:</b> the online services received the original audio file with default settings (no language
        given, no hint text, plain-text output). Local used automatic language detection and no time stamps.</li>
  </ul>

  <h3>How the comparison was performed</h3>
  <ol>
    <li><b>Pairing:</b> for each recording, the text of a system is compared with the reference text of the
        same recording.</li>
    <li><b>Cleaning (applied to both texts before comparing):</b> everything is made lowercase; hyphens, dashes and
        slashes become spaces; all other punctuation is deleted (also apostrophes, so &ldquo;don&rsquo;t&rdquo;
        becomes &ldquo;dont&rdquo;); repeated spaces and line breaks are collapsed. Letters with umlauts and
        &szlig; as well as digits are kept.</li>
    <li><b>Counting:</b> the cleaned texts are split into words and aligned by the minimum number of changes
        (word-level edit distance, library <i>jiwer</i>). Each replaced, missing or extra word counts as one error,
        no matter how small the difference is. WER = errors / words in the reference. If a system returns no text
        for a recording whose reference has words, that counts as WER 1.0 (every word missing).</li>
    <li><b>Which files count:</b> a recording whose reference has fewer than {minw} words is left out of all
        speed and error statistics ({excl} files). One word is then a 10&ndash;100% error, which says nothing
        about quality. These files stay in the table (greyed out) and in the cost total.</li>
    <li><b>Per file, then average:</b> the WER is calculated per recording, and mean, median and p95 are taken
        over the {len(inc)} analysed recordings. Every file counts equally, so a 2-minute recording weighs as much as
        a 7-minute one (the median is often more informative than the mean).</li>
  </ol>
  <p><b>Ignored (does not count as an error):</b> upper/lower case, punctuation, line breaks and paragraph
  layout, hyphen or slash versus space.</p>
  <p><b>Not ignored (counts as an error):</b> different spelling of the same word (for example &ldquo;Handynummer&rdquo; versus
  &ldquo;Handy-Nummer&rdquo; or &ldquo;Handy Nummer&rdquo; is an error, because one word becomes two; &ldquo;Handy-Nummer&rdquo;
  versus &ldquo;Handy Nummer&rdquo; is not),
  digits versus spelled-out numbers (&ldquo;2&rdquo; versus &ldquo;zwei&rdquo;), filler words
  (&ldquo;&auml;h&rdquo;, &ldquo;um&rdquo;), contractions, names, wrong language, and every word the
  reference has and the other text does not (or the other way round).</p>
  <p><b>Not taken into account at all:</b> whether a mistake changes the meaning (a harmless slip counts the same as
  a serious one), whether the reference itself is correct, punctuation and formatting quality, speaker or time
  information, audio quality, memory use and electricity of the local model, and variation between repeated runs
  (every file was run only once per system). Apple&rsquo;s own automatic transcripts of the recordings were
  considered at first and then dropped as unreliable.</p>
  <p><b>Highlighting in the full report</b> (not in this public version) uses its own simpler comparison in the browser
  (lowercase, plain letters only) and is only for display. It does not influence any number here.</p>

  <h3>Abbreviations and terms</h3>
  <dl>
    <dt>RTF &mdash; real-time factor</dt>
    <dd>Transcription time divided by audio duration. 0.05 means a 10-minute recording took 30 seconds.
        1.0 is exactly real time, above 1.0 is slower than the recording itself. Lower is better.</dd>
    <dt>WER &mdash; word error rate</dt>
    <dd>(S + D + I) / N: the number of replaced (substitutions), missing (deletions) and extra (insertions)
        words, divided by the number of words N in the reference. 0 = identical, 0.10 = about one word in ten
        differs. Values above 1 are possible if there are more errors than reference words. Lower is better.</dd>
    <dt>Mean / median / p95</dt>
    <dd>Average; the middle value (half of the files are better, half worse; less sensitive to outliers); and the
        value that 95% of the files stay below, i.e. the bad end.</dd>
    <dt>n</dt><dd>Number of files in a calculation.</dd>
    <dt>Cost</dt><dd>Audio minutes &times; $0.006, in US dollars, for all files. Local costs nothing per file.</dd>
    <dt>Time</dt><dd>Seconds for one file. <b>Duration</b> is the length of the recording.</dd>
    <dt>Greyed-out row</dt><dd>A recording that was left out of the statistics because it has almost no speech.</dd>
    <dt>Rec 01 &hellip;</dt><dd>Anonymous number of a recording (in chronological order).</dd>
    <dt>CPU / GPU</dt><dd>Normal processor / graphics processor. Speech models run much faster on a GPU.</dd>
    <dt>API</dt><dd>Interface to an online service.</dd>
  </dl>

  <h3>Reading the charts and the table</h3>
  <ul>
    <li><b>Speed (scatter):</b> every dot is a file. The higher a system&rsquo;s dots sit, the longer it took
        for the same duration. Charts show the analysed files only.</li>
    <li><b>RTF per file (bars):</b> the same in relative terms. Bars above 1 mean slower than real time.</li>
    <li><b>WER distribution:</b> how many files fall into each error band. Many files on the left (0&ndash;10%) is good.</li>
    <li><b>Table:</b> click a column header to sort. The filter box searches the file name. Colours: green &lt; 20%,
        yellow &lt; 40%, red above. Greyed-out rows are the excluded recordings.</li>
  </ul>

  {observations_html(agg, inc, allrows, keys, rep)}
  {removed}
</details>
"""


def build_report(metrics: dict, public: bool = False) -> str:
    rep = repetition_stats([r for r in metrics["per_file"] if not r.get("excluded")],
                           ["local"] + metrics["aggregate"].get("backend_keys", []))
    if public:
        metrics = sanitize(metrics)
    agg = metrics["aggregate"]
    per_file = metrics["per_file"]
    inc = [r for r in per_file if not r.get("excluded")]   # analysed files
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
    summary_row1 += stat_card(f"${total_cost:.4f}", "Total API cost (both online models, all files)", "")

    summary_row2 = ""
    gt = agg.get("ground_truth_key", "gpt-4o-transcribe")
    if agg.get("local_wer", {}).get("n"):
        summary_row2 += stat_card(agg["local_wer"]["mean"], f"Local WER vs {gt} (n={agg['local_wer']['n']})", "local")
    for k in backend_keys:
        if k != gt and agg.get(f"{k}_wer", {}).get("n"):
            summary_row2 += stat_card(agg[f"{k}_wer"]["mean"], f"{k} WER vs {gt} (n={agg[f'{k}_wer']['n']})", k)

    # Table header columns
    def th(label, idx):
        return f'<th onclick="sortTable({idx})">{label} ↕</th>'

    table_cols = ["File", "Duration", "Local time", "Local RTF", "Local WER"]
    for k in backend_keys:
        table_cols += [f"{k} time", f"{k} RTF", f"{k} WER"]
    table_cols.append("Cost")
    th_html = "".join(th(c, i) for i, c in enumerate(table_cols))

    # Colors for charts as JS arrays
    js_colors_line = json.dumps([color(k)["line"] for k in all_keys])
    js_colors_fill = json.dumps([color(k)["fill"] for k in all_keys])
    js_backend_keys = json.dumps(backend_keys)
    js_all_keys = json.dumps(all_keys)

    row_hint = ("— transcripts and recording names removed from this public version"
                if public else "— click a row to compare transcripts")
    diff_panel = "" if public else """<div id="diffPanel" class="diff-panel">
    <p class="sec" id="diffTitle">Transcript comparison</p>
    <div id="diffGrid" class="grid"></div>
  </div>"""

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
  tr.excl{{opacity:.45}}
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
  details.about{{margin-bottom:20px;line-height:1.65}}
  details.about summary{{cursor:pointer;font-weight:600;font-size:1rem}}
  details.about h3{{margin:18px 0 6px}}
  details.about p,details.about ul,details.about dl{{margin:6px 0}}
  details.about ul{{padding-left:20px}}
  details.about li{{margin:4px 0}}
  details.about dt{{font-weight:600;margin-top:8px}}
  details.about dd{{margin-left:18px;color:var(--muted)}}
  table.mini{{width:auto;margin:8px 0}}
  table.mini th,table.mini td{{cursor:default}}
</style>
</head>
<body>
<div class="container">
  <h1>🎙 Whisper Benchmark</h1>
  <h2>{agg['total_files']} recordings ({agg['analysed_files']} analysed) &nbsp;·&nbsp; {agg['total_duration_min']:.1f} min audio &nbsp;·&nbsp; backends: local + {', '.join(backend_keys)}</h2>

  {summary_html(agg, inc, per_file, all_keys, rep)}
  {about_html(agg, inc, per_file, all_keys, public, rep)}

  <div class="grid g4" style="margin-bottom:16px">{summary_row1}</div>
  {"" if not summary_row2 else f'<div class="grid g{min(len(all_keys),4)}" style="margin-bottom:20px">{summary_row2}</div>'}

  <div class="grid g2" style="margin-bottom:20px">
    <div class="card"><h3>Speed — Duration vs Transcription Time</h3><canvas id="speedChart"></canvas></div>
    <div class="card"><h3>Real-Time Factor per File</h3><canvas id="rtfChart"></canvas></div>
  </div>

  {"" if not agg.get("local_wer",{}).get("n") else '<div class="card" style="margin-bottom:20px"><h3>WER Distribution vs gpt-4o-transcribe Reference</h3><canvas id="werChart"></canvas></div>'}

  <p class="sec">Per-file results <span style="color:var(--muted);font-weight:400;font-size:.85em">{row_hint}</span></p>
  <div class="filter-bar"><input type="text" id="fi" placeholder="Filter by filename…" oninput="filterTable()"></div>
  <div class="card" style="overflow-x:auto;margin-bottom:16px">
    <table id="rt"><thead><tr>{th_html}</tr></thead><tbody id="tb"></tbody></table>
  </div>

  {diff_panel}
</div>

<script>
const DATA = {data_json};
const pf = DATA.per_file;
const pfa = pf.filter(r=>!r.excluded);   // analysed files: charts and statistics
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
    cols.push(fmt(r[k+'_time_s'],1,'s'), fmt(r[k+'_rtf'],3), fmtWer(r[k+'_wer']));
  }}
  const totalCost = backendKeys.reduce((s,k)=>s+(r[k+'_cost_usd']||0),0);
  cols.push(totalCost?'$'+totalCost.toFixed(4):'<span class="null">—</span>');
  return cols;
}}

function buildRows(data) {{
  return data.map((r,i)=>`<tr data-i="${{i}}" class="${{r.excluded?'excl':''}}" title="${{r.excluded?'Left out of the statistics: almost no speech in this recording':''}}" onclick="selectRow(this)">${{rowCols(r).map(c=>`<td>${{c}}</td>`).join('')}}</tr>`).join('');
}}

let filteredData = pf;
function filterTable() {{
  const q=document.getElementById('fi').value.toLowerCase();
  filteredData=q?pf.filter(r=>r.stem.toLowerCase().includes(q)):pf;
  document.getElementById('tb').innerHTML=buildRows(filteredData);
}}

const sortKeys=['stem','duration_s','local_time_s','local_rtf','local_wer',
  ...backendKeys.flatMap(k=>[k+'_time_s',k+'_rtf',k+'_wer']),
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
function normWord(w) {{
  return w.toLowerCase().replace(/[^\\w]/g, '');
}}
function wordDiff(ref, hyp) {{
  if(!ref||!hyp) return hyp||'<span class="null">—</span>';
  const rw=ref.split(/[\\s]+/),hw=hyp.split(/[\\s]+/);
  const m=rw.length,n=hw.length;
  const dp=Array.from({{length:m+1}},()=>new Array(n+1).fill(0));
  for(let i=1;i<=m;i++) for(let j=1;j<=n;j++)
    dp[i][j]=normWord(rw[i-1])===normWord(hw[j-1])?dp[i-1][j-1]+1:Math.max(dp[i-1][j],dp[i][j-1]);
  const ops=[];let i=m,j=n;
  while(i>0||j>0){{
    if(i>0&&j>0&&normWord(rw[i-1])===normWord(hw[j-1])){{ops.push(['eq',hw[j-1]]);i--;j--;}}
    else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])){{ops.push(['ins',hw[j-1]]);j--;}}
    else{{ops.push(['del',rw[i-1]]);i--;}}
  }}
  ops.reverse();
  return ops.map(([t,w])=>t==='eq'?w:t==='ins'?`<mark class="ins">${{w}}</mark>`:`<mark class="del">${{w}}</mark>`).join(' ');
}}

function selectRow(tr) {{
  if(!document.getElementById('diffPanel')) return;
  if(activeRow) activeRow.classList.remove('active');
  activeRow=tr; tr.classList.add('active');
  const stem=tr.querySelector('td').textContent;
  const rec=pf.find(x=>x.stem===stem)||filteredData[+tr.dataset.i];
  document.getElementById('diffTitle').textContent=`Transcript comparison — ${{rec.stem}}`;
  const gtKey=agg.ground_truth_key;
  const ref=rec[gtKey+'_text']||'';
  const panels=[
    {{label:gtKey+' (reference)',key:gtKey,text:rec[gtKey+'_text'],color:'#f59e0b',isRef:true}},
    {{label:'Local',key:'local',text:rec.local_text,color:'#34d399'}},
    ...backendKeys.filter(k=>k!==gtKey).map((k,i)=>{{return{{label:k,key:k,text:rec[k+'_text'],color:colorsLine[i+2]}}}})
  ];
  const grid=document.getElementById('diffGrid');
  grid.style.gridTemplateColumns=`repeat(${{panels.length}},1fr)`;
  grid.innerHTML=panels.map(p=>`
    <div class="card">
      <h3 style="color:${{p.color}}">${{p.label}}</h3>
      <div class="diff-text">${{p.isRef?(p.text||'<span class="null">No reference</span>'):wordDiff(ref,p.text)}}</div>
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
const withLocal = pfa.filter(r=>r.local_time_s);
new Chart(document.getElementById('speedChart'),{{
  type:'scatter',
  data:{{datasets:[
    {{label:'Local',data:withLocal.map(r=>{{return{{x:r.duration_s,y:r.local_time_s}}}}),backgroundColor:'#34d399aa',pointRadius:5}},
    ...backendKeys.map((k,i)=>{{
      const d=pfa.filter(r=>r[k+'_time_s']);
      return{{label:k,data:d.map(r=>{{return{{x:r.duration_s,y:r[k+'_time_s']}}}}),backgroundColor:colorsLine[i+1]+'aa',pointRadius:5}};
    }})
  ]}},
  options:{{...chartOpts,scales:{{
    x:{{...chartOpts.scales.x,title:{{display:true,text:'Audio duration (s)',color:'#64748b'}}}},
    y:{{...chartOpts.scales.y,title:{{display:true,text:'Transcription time (s)',color:'#64748b'}}}}
  }}}}
}});

// RTF bar
const rtfData=pfa.filter(r=>r.local_rtf||backendKeys.some(k=>r[k+'_rtf']));
new Chart(document.getElementById('rtfChart'),{{
  type:'bar',
  data:{{
    labels:rtfData.map(r=>r.stem.startsWith('Rec ')?r.stem:r.stem.slice(5,16)),
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
  pfa.forEach(r=>{{
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
    public = "--public" in sys.argv
    out = config.REPORT_FILE.with_name("report-public.html") if public else config.REPORT_FILE
    out.write_text(build_report(metrics, public=public))
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
