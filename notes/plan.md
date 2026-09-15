# Whisper Benchmark — Implementation Plan

## Phase 1: Scaffold (30 min)

**Goal:** working directory structure, git init, dependencies pinned.

- [x] Create project directory structure
- [ ] `git init` in project root
- [ ] `requirements.txt` with pinned deps: `jiwer`, `openai`, `tqdm`
- [ ] `config.py` — central config: corpus path, model flags, API model name, output dirs
- [ ] `data/corpus.txt` — generated list of all 44 m4a paths + which have iOS refs
- [ ] First commit: scaffold

---

## Phase 2: Runner — `scripts/benchmark.py` (60 min)

**Goal:** script that, for each file in corpus, transcribes via both backends and saves raw JSON.

### Structure

```python
benchmark.py [--local-only] [--api-only] [--dry-run] [--limit N]
```

### Local backend
1. Get audio duration via `ffprobe`
2. Invoke `whisper-cli` subprocess with the right flags (same as `transcribe.sh`)
3. Measure wall-clock time with `time.perf_counter()`
4. Parse stdout as transcript text
5. Save `results/raw/local/<stem>.json`
6. Skip if output already exists (idempotent)

### API backend
1. `POST /v1/audio/transcriptions` with the raw `.m4a` file
2. Model: `whisper-1`, response_format: `text`
3. Measure wall-clock time
4. Save `results/raw/api/<stem>.json`
5. Skip if output already exists (idempotent)

### Error handling
- Catch and log failures per file; never abort the whole run
- On network error: retry once with 5 s back-off
- On timeout (>300 s local, >120 s API): log and skip

### Run order
- Sequential (not parallel): local first for all files, then API
- Reason: avoid hammering the API rate limits and avoid overloading the CPU during local inference
- Progress: `tqdm` progress bar with ETA

---

## Phase 3: Analyzer — `scripts/analyze.py` (45 min)

**Goal:** consume raw JSON outputs, compute all metrics, produce `results/metrics.json`.

### Steps
1. Load all local + API JSONs
2. For paired files, load iOS reference `.txt`
3. Normalise all texts (lowercase, strip punctuation)
4. Compute per-file metrics table (see spec)
5. Compute aggregates (mean, median, p95, totals)
6. Save `results/metrics.json`

### WER normalisation function
```python
import re
def normalise(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)   # strip punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text
```

---

## Phase 4: Visualiser — `scripts/report.py` (90 min)

**Goal:** generate `results/report.html` — self-contained, no server required.

### Template approach
- Pure Python string template (no external templating lib)
- Embed Chart.js from CDN (`https://cdn.jsdelivr.net/npm/chart.js`)
- Embed all data as `const DATA = {...}` JSON block in the HTML `<script>` tag
- CSS: minimal, dark-friendly, readable on mobile

### Sections
1. **Header** — title, run timestamp, summary stats
2. **Speed chart** — Chart.js scatter: x=duration_s, y=time_s, two datasets (local/API)
3. **WER histogram** — Chart.js bar: WER buckets 0–100%, three series (local, API, cross)
4. **RTF comparison** — Chart.js bar: per-file RTF side by side (sorted by duration)
5. **Table** — HTML table, sortable via JS click-on-header, all metrics, clickable rows
6. **Diff panel** — hidden by default, appears on row click; three columns: iOS / local / API; word-level diff highlighted with `<mark>` spans

### Word-level diff
- Implemented in vanilla JS (no external lib)
- LCS-based diff: highlight substituted/inserted words in red, deleted in grey
- Green = exact match

---

## Phase 5: Integration test (30 min)

**Goal:** end-to-end smoke test before the full benchmark run.

- Run `benchmark.py --limit 3` (3 files, both backends)
- Run `analyze.py`
- Run `report.py`
- Open `report.html` and verify charts render, diff viewer works

---

## Phase 6: Full benchmark run

**Goal:** run all 44 files and generate the final report.

- Estimated local runtime: ~3–5 min total (large-v3-turbo is fast, RTF ~0.1–0.2x on CPU)
- Estimated API time: ~3–5 min (network + API processing, ~2–4 s per short file)
- Estimated API cost: assuming ~90 min total audio → ~$0.54

---

## Phase 7: GitHub setup

**Requires Erich to do one of:**

### Option A (recommended) — GitHub CLI
```bash
sudo apt install gh
gh auth login   # follow prompts, browser-based OAuth
```
Then I create the repo and push:
```bash
gh repo create erichwei/whisper-benchmark --private --source=. --remote=origin --push
```

### Option B — Manual
1. Create a new private repo at github.com (e.g. `erichwei/whisper-benchmark`)
2. Copy the SSH clone URL
3. Tell me the URL → I run `git remote add origin <url> && git push -u origin main`
4. SSH key: either use an existing one from `~/.ssh/` or tell me and I'll generate one

### Option C — HTTPS with personal access token
1. Go to github.com → Settings → Developer settings → Personal access tokens → Fine-grained
2. Create token with `repo` scope
3. Tell me the token → I configure git credential store

---

## File checklist

```
projects/whisper-benchmark/
  README.md              ✓
  TODO.md                ← next
  requirements.txt       ← Phase 1
  config.py              ← Phase 1
  data/corpus.txt        ← Phase 1
  scripts/benchmark.py   ← Phase 2
  scripts/analyze.py     ← Phase 3
  scripts/report.py      ← Phase 4
  results/               (generated)
  notes/spec.md          ✓
  notes/plan.md          ✓
  log/2026-09.md         ← Phase 1
```
