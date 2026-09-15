# Whisper Benchmark

Compare local whisper.cpp against the OpenAI Whisper API on real iOS voice recordings.

**Backends:**
- **Local** — whisper.cpp `ggml-large-v3-turbo-q5_0` running directly via CLI
- **API** — OpenAI Transcriptions API (`whisper-1`)
- **Reference** — iOS Voice Memos auto-transcription (the paired `.txt` files)

**Test corpus:** 44 `.m4a` recordings in `imports/iOS_dictations/processed/`; 27 have paired iOS transcriptions and serve as three-way comparison points.

**Metrics:** transcription speed, Word Error Rate (vs iOS reference), cross-agreement between local and API, cost estimate.

**Output:** `results/report.html` — self-contained interactive report.

## Quick start

```bash
cd projects/whisper-benchmark
pip install -r requirements.txt
python scripts/benchmark.py          # runs both backends, saves to results/raw/
python scripts/analyze.py            # computes WER and metrics
python scripts/report.py             # generates results/report.html
```

## Layout

```
scripts/
  benchmark.py    — runner: transcribes each file with both backends
  analyze.py      — metrics: WER, speed stats, cost
  report.py       — visualizer: generates self-contained HTML
results/
  raw/local/      — JSON outputs from local whisper.cpp
  raw/api/        — JSON outputs from OpenAI API
  metrics.json    — computed comparison metrics
  report.html     — generated report
data/
  corpus.txt      — list of m4a files used in the benchmark run
notes/
  spec.md         — full specification
  plan.md         — implementation plan
log/
  2026-09.md      — session notes
```
