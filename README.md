# Whisper Benchmark

Compare local whisper.cpp against OpenAI's transcription APIs on real voice recordings.

**Backends:**
- **Local** — whisper.cpp `ggml-large-v3-turbo-q5_0`, called directly via CLI
- **whisper-1** — OpenAI Transcriptions API, classic Whisper large-v2 model
- **gpt-4o-transcribe** — OpenAI Transcriptions API, newer GPT-4o based model (ground truth)

**Test corpus:** 44 `.m4a` recordings (~85 min of audio), mixed German/English natural speech.

**Metrics:** transcription speed (RTF), Word Error Rate vs ground truth, API cost.

**Ground truth:** `gpt-4o-transcribe` output is used as the reference for WER calculations. No manual transcription was produced.

**Output:** `results/report.html` — self-contained interactive report with charts, per-file table, and side-by-side transcript diff viewer.

---

## Results (full run — 44 files, 84.8 min audio)

| Backend | Mean RTF | WER vs gpt-4o-transcribe | API cost (full corpus) |
|---|---|---|---|
| Local whisper.cpp | 1.067× | 0.199 | — |
| whisper-1 | 0.061× | 0.264 | $0.51 |
| gpt-4o-transcribe | 0.043× | (reference) | $0.51 |

**RTF** = transcription time / audio duration. Lower is faster. RTF > 1.0 means slower than real-time.

### Key findings

- **Local is ~17× slower than gpt-4o-transcribe** and frequently exceeds real-time (mean RTF 1.07). Not suitable for interactive or pipeline use without a GPU.
- **gpt-4o-transcribe is the best overall** — fastest API response and highest accuracy. Same price as whisper-1 ($0.006/min).
- **Surprising: local WER (0.199) beats whisper-1 WER (0.264)** against the gpt-4o-transcribe reference. Local whisper.cpp (large-v3-turbo) agrees more with the newer model than the older API model does — likely because both use large-v3-turbo weights under the hood.
- **Total API cost for 85 min of audio: ~$0.51 per model.** At that rate, processing a full month of daily voice notes (~30 h) would cost ~$10.80.

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

python scripts/analyze.py   # compute metrics → results/metrics.json
python scripts/report.py    # generate → results/report.html
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
  report.html             — generated interactive report
data/
  corpus.txt      — list of m4a files used in the benchmark
config.py         — central configuration
notes/
  spec.md         — full specification
  plan.md         — implementation plan
log/
  2026-09.md      — session notes
```
