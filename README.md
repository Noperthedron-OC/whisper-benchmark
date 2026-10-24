# Whisper Benchmark

Compare local whisper.cpp against OpenAI's transcription APIs on real voice recordings.

**Backends:**
- **Local** — whisper.cpp `ggml-large-v3-turbo-q5_0`, called directly via CLI
- **whisper-1** — OpenAI Transcriptions API, classic Whisper large-v2 model
- **gpt-4o-transcribe** — OpenAI Transcriptions API, newer GPT-4o based model (ground truth)

**Test corpus:** 44 `.m4a` recordings (~85 min of audio), mixed German/English natural speech.

**Metrics:** transcription speed (RTF), Word Error Rate vs ground truth, API cost.

**Ground truth:** `gpt-4o-transcribe` output is used as the reference for WER calculations. No manual transcription was produced.

**Output:** `results/report-public.html` is the shareable report (numbers only). `results/report.html` is the full local version with transcripts and a side-by-side diff viewer; it is **not** meant to be shared (see [Data and privacy](#data-and-privacy)).

---

## Results (full run: 44 files, 84.8 min of audio)

| System | Total transcription time | Mean RTF | Median RTF | WER vs reference, all files (mean / median) | API cost (corpus) |
|---|---|---|---|---|---|
| Local whisper.cpp | 48.2 min | 1.067 | 0.712 | 0.199 / 0.093 | none |
| whisper-1 | 3.4 min | 0.061 | 0.043 | 0.204 / 0.055 | $0.51 |
| gpt-4o-transcribe | 2.5 min | 0.043 | 0.033 | reference | $0.51 |

**RTF** (real-time factor) = transcription time / audio duration, lower is better. **WER** (word error rate) = (substitutions + deletions + insertions) / words in the reference, lower is better. The reference is `gpt-4o-transcribe`, itself a machine transcription, so WER measures agreement, not truth.

### Key findings

- **Speed is the clear difference.** Local was about 20x slower than gpt-4o-transcribe in total time (about 25x by mean RTF) and slower than real time on 8 of 44 files. The online services are fast at every length. Local is relatively slower on short files (median RTF 0.93 under 1 min, 0.48 at 3 min and more), probably because the model is loaded on every call.
- **Cost is a non-issue at this volume.** Both online models cost $0.006 per minute: $0.51 for the corpus, about $10.80 for 30 hours of voice notes per month.
- **Accuracy is close on average, but not equal.** Over all 44 files local and whisper-1 have similar mean WER (0.199 vs 0.204); whisper-1 is better at the median (0.055 vs 0.093). On recordings of 3 minutes and more (9 files) local is clearly further from the reference (0.17 vs 0.05).
- **The local model sometimes repeats words or whole phrases**, mostly at the end of a clause or sentence, sometimes several times in a row: 15 times in 9 files (whisper-1: 5 in 4 files, gpt-4o-transcribe: 0). 6 of the 9 files are longer than 3 minutes.
- **A few nearly empty recordings distort the means.** 4 files have fewer than 10 words in the reference; they produce most WER values of 1.0 and above. Without them the mean WER is about 0.09 (local) and 0.10 (whisper-1).
- **Caveats:** one speaker, 44 files, one run on one server (CPU only), and a machine-made reference.

The public report contains these results with an explanation of the method, a glossary and the observations in full: [`results/report-public.html`](results/report-public.html) (download and open in a browser; it loads Chart.js from a CDN).

### Corrections to earlier versions of this README

- The earlier headline "local WER (0.199) beats whisper-1 (0.264)" compared different file sets: `analyze.py` leaves files with a perfect score (WER 0) out of the API averages (n=34 for whisper-1) but not out of the local average (n=44). Like for like (all files) the means are 0.199 and 0.204.
- "Local is about 17x slower than gpt-4o-transcribe" was the ratio of mean RTF against whisper-1. Against gpt-4o-transcribe it is about 25x by mean RTF and 20x by total time.
- "gpt-4o-transcribe has the highest accuracy" cannot be shown, because it is the reference. It is the fastest and costs the same as whisper-1.
- The guess that local agrees with gpt-4o-transcribe because both use the same model weights was never tested.

### Known issues

- `analyze.py` still excludes perfect (WER 0) files from the API aggregates (see above). The report labels the affected cards with their `n` and shows a like-for-like table computed from the per-file numbers.
- The `cross-WER` column in the per-file table is not populated in this run.
- `notes/spec.md` says the local timing includes the ffmpeg conversion; the code starts the clock after it.

## Data and privacy

The recordings are personal voice notes. Anything derived from their text is private:

- `results/raw/**`, `results/metrics.json` and `results/report.html` contain full transcripts.
- `data/corpus.txt` and the file names contain the date and time of each recording.
- `results/report-public.html` contains numbers only. Transcripts are removed, and recordings are numbered `Rec 01` to `Rec 44`.

The repository is private. Do not publish it or share the files above. For sharing, use the public report:

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

python scripts/analyze.py   # compute metrics → results/metrics.json
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
