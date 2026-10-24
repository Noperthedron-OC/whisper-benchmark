# Whisper Benchmark — Specification

> **Status (24 Oct 2026):** this spec is the original plan. Decisions made during the work: the iOS reference transcripts were dropped (all WER is measured against `gpt-4o-transcribe`); a second API backend was added; recordings with fewer than 10 reference words are excluded from all statistics; the `cross_wer` metric was not implemented. See `README.md` for the current method and results.

## Goal

Quantify the real-world difference between local whisper.cpp and the OpenAI Whisper API on Erich's actual voice recordings. Produce actionable data: is the local model fast enough and accurate enough to justify staying offline, or does the API justify its cost?

---

## Inputs

### Audio corpus
- **Source:** `/home/mimir/shared/imports/iOS_dictations/processed/*.m4a`
- **Count:** 44 files (July 26–27, 2026)
- **Format:** AAC/M4A, recorded at iOS default quality (~32 kHz)
- **Language:** mixed German and English, natural speech, no script
- **Duration range:** ~34 s – ~449 s (estimated total ~90–120 min of audio)

### iOS reference transcripts
- 27 of the 44 files have a matching `.txt` (same stem, no `-Dictation` suffix)
- These are Apple Voice Memos auto-transcriptions — not perfect ground truth, but a consistent third reference from a different engine
- Used to compute WER for both backends; not used as a gold standard

---

## Backends

### Local — whisper.cpp
- Binary: `/home/mimir/opt/whisper.cpp/build/bin/whisper-cli`
- Model: `ggml-large-v3-turbo-q5_0` (quantised large-v3-turbo, ~550 MB)
- Flags: `--language auto --no-timestamps --no-prints`
- Audio pre-processing: ffmpeg → WAV 16 kHz mono (matching `transcribe.sh`)
- Timing: wall-clock of the `whisper-cli` run only (model load + inference). The ffmpeg conversion happens before the clock starts and is not counted (corrected 24 Oct 2026 to match the code)

### API — OpenAI Whisper
- Endpoint: `POST https://api.openai.com/v1/audio/transcriptions`
- Model: `whisper-1`
- Format: upload raw `.m4a` directly (API accepts it natively)
- Auth: `OPENAI_API_KEY` env var
- Timing: wall-clock from request send to response received (network + inference)
- Cost: $0.006 / minute of audio (billed on input duration)

---

## Metrics

### Per-file
| Metric | Description |
|---|---|
| `local_time_s` | Wall-clock seconds for local transcription |
| `api_time_s` | Wall-clock seconds for API transcription |
| `duration_s` | Audio duration in seconds (via ffprobe) |
| `local_rtf` | Real-time factor: `local_time_s / duration_s` (lower = faster) |
| `api_rtf` | Same for API |
| `local_wer` | WER vs iOS reference (paired files only) |
| `api_wer` | WER vs iOS reference (paired files only) |
| `cross_wer` | WER comparing local output against API output (all files) |
| `local_words` | Word count of local transcript |
| `api_words` | Word count of API transcript |
| `api_cost_usd` | `duration_s / 60 * 0.006` |

### Aggregate
- Mean / median / p95 of all per-file metrics
- Total API cost for the corpus
- WER distribution histogram
- Speed distribution scatter

---

## Word Error Rate methodology

- Library: `jiwer` (`pip install jiwer`)
- Normalisation before comparison: lowercase, strip punctuation, collapse whitespace
- Language: mixed German/English — no language-specific normalisation (keep it simple; the recordings are naturally mixed)
- WER formula: `(S + D + I) / N` where S=substitutions, D=deletions, I=insertions, N=reference words
- Cross-WER (local vs API): treat local output as "hypothesis", API as "reference" — a measure of agreement, not absolute accuracy

---

## Output files

```
results/raw/local/<stem>.json    — {"file": "...", "text": "...", "time_s": 1.23, "duration_s": 34.0}
results/raw/api/<stem>.json      — same structure + {"cost_usd": 0.003}
results/metrics.json             — per-file and aggregate metrics dict
results/report.html              — self-contained interactive HTML report
```

---

## Report content (HTML)

1. **Summary banner** — total files, total audio time, mean WER (local vs iOS, API vs iOS), total API cost
2. **Speed comparison** — scatter plot: audio duration vs transcription time, both backends
3. **WER distribution** — side-by-side histogram (local WER, API WER, cross-WER)
4. **Per-file table** — sortable, filterable; columns: filename, duration, local RTF, API RTF, local WER, API WER, cross-WER
5. **Diff viewer** — click any row → three-panel side-by-side: iOS / local / API transcript with word-level diffs highlighted
6. **Cost estimate** — projected API cost at different corpus scales

Charts: Chart.js (CDN, but report is otherwise self-contained). Diff highlighting: pure JS.

---

## What's out of scope (v1)

- `gpt-4o-transcribe` (more expensive, different tradeoffs — v2)
- Automatic ground-truth verification (would need human review)
- Timestamp comparison (local supports it, API does too, skip for now)
- Streaming / real-time transcription latency
- Multiple local model sizes (only large-v3-turbo-q5_0 for now)
