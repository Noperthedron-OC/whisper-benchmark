# Whisper Benchmark

Compare local whisper.cpp against OpenAI's transcription APIs on real voice recordings.

## Motivation

Cost is only part of the reason. The online services are cheap ($0.006 per minute, about $10.80 for 30 hours of audio a month), so the real question is **whether, and for which use cases, a local speech-to-text (STT) model makes sense**, and where the online services are clearly better.

The author uses the local model today for:

- **speech input to [OpenClaw](https://github.com/openclaw/openclaw)**, a personal AI assistant, and
- **transcribing voice notes and ideas**, for example a dream journal. These are not interactive: the text is needed minutes later, so speed is not essential.

What a local model offers for such uses: voice notes are personal and **never leave the machine**; there is **no API key, no per-minute cost and no dependency** on an online service being reachable. What it costs: processor time, memory (see [Resource use](#resource-use-memory)), and speed and accuracy that may fall short for some uses. This benchmark measures exactly that trade-off on real recordings.

**Backends:**
- **Local** — whisper.cpp `ggml-large-v3-turbo-q5_0`, called directly via CLI
- **whisper-1** — OpenAI Transcriptions API, classic Whisper large-v2 model
- **gpt-4o-transcribe** — OpenAI Transcriptions API, newer GPT-4o based model (ground truth)

**Test corpus:** 44 `.m4a` recordings (~85 min of audio), mixed German/English natural speech. 4 of them have almost no speech (reference under 10 words) and are left out of all speed and error statistics, so **40 recordings (83.3 min) are analysed**. Cost is counted for all 44, because that is what was billed.

**Metrics:** transcription speed (RTF), Word Error Rate vs reference, API cost.

**Reference:** `gpt-4o-transcribe` output is used as the reference for WER. No manual transcription was produced, so WER measures agreement with that model, not truth.

**Output:** `results/report-public.html` is the shareable report (numbers only, with summary, method, glossary and observations). `results/report.html` is the full local version with transcripts and a side-by-side diff viewer. It is **not** in the repository (see [Data and privacy](#data-and-privacy)).

---

## Results (40 analysed recordings, 83.3 min of audio)

| System | Total transcription time | Mean RTF | Median RTF | WER vs reference (mean / median) | API cost (all 44 files) |
|---|---|---|---|---|---|
| Local whisper.cpp | 46.3 min | 0.749 | 0.677 | 0.094 / 0.086 | none |
| whisper-1 | 3.3 min | 0.048 | 0.043 | 0.099 / 0.046 | $0.51 |
| gpt-4o-transcribe | 2.4 min | 0.036 | 0.031 | reference | $0.51 |

**RTF** (real-time factor) = transcription time / audio duration, lower is better. **WER** (word error rate) = (substitutions + deletions + insertions) / words in the reference, lower is better.

### Key findings

- **Speed is the clear difference.** Local was about 19x slower than gpt-4o-transcribe in total time (about 21x by mean RTF) and slower than real time on 6 of 40 files. The online services are fast at every length. Local is relatively slower on short files (median RTF 0.93 under 1 min, 0.48 at 3 min and more), probably because the model is loaded on every call.
- **Cost is a non-issue at this volume.** Both online models cost $0.006 per minute: $0.51 for the corpus, about $10.80 for 30 hours of voice notes per month.
- **Accuracy is close on average, but not equal.** Local and whisper-1 have similar mean WER (0.094 vs 0.099); whisper-1 is better at the median (0.046 vs 0.086). On recordings of 3 minutes and more (9 files) local is clearly further from the reference (0.17 vs 0.05).
- **The local model sometimes repeats words or whole phrases**, mostly at the end of a clause or sentence, sometimes several times in a row: 13 times in 7 files (whisper-1: 3 in 2 files, gpt-4o-transcribe: 0). 6 of the 7 files are longer than 3 minutes.
- **Nearly empty recordings are excluded.** 4 recordings have fewer than 10 reference words. One word is a 10-100% error there, which says nothing about quality. Counting them would raise the mean WER to 0.199 (local) and 0.204 (whisper-1).
- **Caveats:** one speaker, 40 analysed files, one run on one server (CPU only), and a machine-made reference. The local run used `whisper-cli` with its default of 4 threads and loaded the model for every file; the resident `whisper-server` of the same machine uses 6 threads and keeps the model loaded. On one 62-second recording it took 36 s instead of 50 s, so the local timings here are somewhat pessimistic for server use (single sample, not a systematic measurement).

### Use cases: what this suggests

- **Voice notes, journaling, ideas (asynchronous):** local is a good fit. A typical note takes well under its own length to transcribe (median RTF about 0.7), nobody waits for it, the text stays on the machine, and on recordings up to about 3 minutes the mean WER is close to, or lower than, that of whisper-1 in this benchmark. For notes over about 3 minutes, expect more differences and occasional repeated phrases (see above) and check the text, or split long recordings.
- **Speech input to an assistant (short messages):** workable if a few seconds to about a minute of waiting is acceptable. A resident server (model already loaded) is clearly better than starting the program for every message. If answers are expected quickly, the online services respond in a few seconds at any length.
- **Real-time or interactive dictation:** not a good fit for a CPU-only local setup; the online services are about 20 times faster here.
- **Large volumes where cost matters:** at $0.006 per minute this is rarely the deciding factor; privacy and independence are better reasons to stay local.

These are readings of one benchmark with one speaker, not general rules.

### Resource use (memory)

Measured on 24 October 2026 on the same machine as the benchmark: a virtual machine with 7.9 GiB RAM and 8 vCPUs (AMD Ryzen 9 PRO 8945HS), no GPU, model `ggml-large-v3-turbo-q5_0` (574 MB file = 547 MiB).

| Setup | Memory | Time |
|---|---|---|
| Resident `whisper-server` (6 threads), idle | 725 MiB resident | n/a |
| Same server during one 62 s recording | up to 761 MiB | 36 s |
| `whisper-cli` (4 threads), one call, 62 s recording | peak 824 MiB | 50 s |
| `whisper-cli` (4 threads), one call, 467 s recording | peak 937 MiB | 227 s |
| Small proxy that converts audio formats in front of the server | 20 MiB | n/a |

Memory is dominated by the model (about 550 MiB) and grows only slowly with recording length (about 110 MiB more for a recording 7.5 times longer). A resident server therefore costs roughly 0.75 GiB of RAM permanently, which is fine on a machine with several GiB but would be a real share on a small board. Method: peak = maximum resident set size reported by `/usr/bin/time -v`; for the server, resident memory read from `/proc` every 0.25 s while one recording went through the proxy. One run each, so treat the figures as approximate.

The public report contains these results with the method, a glossary and the observations in full: [`results/report-public.html`](results/report-public.html) (download and open in a browser; it loads Chart.js from a CDN).

### Changes after review (24 October 2026)

An earlier version of this README reported different numbers (local mean WER 0.199 vs whisper-1 0.264, "local is about 17x slower"). A review found these problems, all fixed:

- **Unequal averaging.** `analyze.py` left files with a perfect score (WER 0) out of the API averages (n=34 for whisper-1) but not out of the local average (n=44). That made local look better than whisper-1. All averages now use the same files.
- **Wrong median.** `percentile()` returned the upper middle value for an even number of files. It now returns the true median (mean of the two middle values); p95 uses the nearest rank.
- **Silent drop of empty transcripts.** A system returning no text for a recording with words was dropped from the WER statistics. It now counts as WER 1.0. (No file was affected in this run.)
- **Nearly empty recordings** (reference under `MIN_REFERENCE_WORDS` = 10 words) are now excluded from all speed and error statistics and flagged `excluded` in `metrics.json`. They stay in the per-file table (greyed out) and in the cost total.
- **Dead `cross-WER` column** removed from the report.
- **Misattributed ratio.** "17x slower" was the mean-RTF ratio against whisper-1, not against gpt-4o-transcribe.
- **Unsupported claims.** "gpt-4o-transcribe has the highest accuracy" cannot be shown, because it is the reference (it is the fastest and costs the same as whisper-1). The guess that local agrees with it because both use the same model weights was never tested.
- **Spec vs code.** `notes/spec.md` said the local timing includes the ffmpeg conversion; the code starts the clock after it. The spec now matches the code.
- **Privacy.** Transcripts and recording names were removed from the repository and its history (see below).

## Data and privacy

The recordings are personal voice notes, and anything derived from their text is private. These files stay on the local machine and are **not** tracked (`.gitignore`):

- `results/raw/` (all transcripts), `results/metrics.json`, `results/report.html`
- `data/corpus.txt` (paths and names with the date and time of each recording). `data/corpus.example.txt` shows the format.

`results/report-public.html` contains numbers only: transcripts are removed and recordings are numbered `Rec 01` to `Rec 44`. On 24 October 2026 the private files were also removed from the Git history (rewritten and force-pushed).

```bash
python scripts/report.py --public   # writes results/report-public.html
```

---

## Quick start

```bash
cd projects/whisper-benchmark
pip install -r requirements.txt

# Run all backends (idempotent — skips already-done files)
python scripts/benchmark.py

# Or selectively:
python scripts/benchmark.py --local-only
python scripts/benchmark.py --api-only --backends gpt-4o-transcribe
python scripts/benchmark.py --limit 3   # smoke test

python scripts/analyze.py   # compute metrics → results/metrics.json (local only)
python scripts/report.py    # generate → results/report.html (private, with transcripts)
python scripts/report.py --public   # generate → results/report-public.html (numbers only)
```

## Configuration

Edit `config.py` to:
- Add/remove API backends (`API_BACKENDS`)
- Change the ground truth backend (`GROUND_TRUTH_BACKEND`)
- Adjust timeouts, model paths, cost rates

## Layout

```
scripts/
  benchmark.py    — runner: transcribes each file with each backend
  analyze.py      — metrics: WER vs ground truth, RTF, cost
  report.py       — visualizer: self-contained HTML report
results/
  raw/local/              — JSON outputs from local whisper.cpp
  raw/whisper-1/          — JSON outputs from whisper-1 API
  raw/gpt-4o-transcribe/  — JSON outputs from gpt-4o-transcribe API
  metrics.json            — computed comparison metrics
  report.html             — full report with transcripts (private, local use only)
  report-public.html      — shareable report: numbers only, with method, glossary, observations
data/
  corpus.txt      — list of m4a files used in the benchmark
config.py         — central configuration
notes/
  spec.md         — full specification
  plan.md         — implementation plan
log/
  2026-09.md      — session notes
```
