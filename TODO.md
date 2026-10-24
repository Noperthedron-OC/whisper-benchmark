# Whisper Benchmark — TODO

## Done

- [x] Project setup: `config.py`, `requirements.txt`, corpus list (local only, see `data/corpus.example.txt`)
- [x] `scripts/benchmark.py`: runner for local whisper.cpp and the OpenAI backends (whisper-1, gpt-4o-transcribe)
- [x] `scripts/analyze.py`: RTF, WER vs reference, cost
- [x] `scripts/report.py`: HTML report with charts and table; `--public` writes a numbers-only version
- [x] Smoke test and full run (44 recordings, 84.8 min)
- [x] GitHub repository set up
- [x] Review of the analysis (24 Oct 2026): equal averaging, true median, empty transcripts count as WER 1.0, nearly empty recordings excluded (`MIN_REFERENCE_WORDS`), dead cross-WER column removed
- [x] Re-run, README with results, public report
- [x] Private data (transcripts, metrics, corpus list) removed from the repository and its history, now ignored
- [x] Repository made public (24 Oct 2026) as a fresh repository with the clean history; the old private one was renamed `whisper-benchmark-old` and is to be deleted

## Ideas (not planned)

- Repeat the timing runs to measure variation between runs (every file was run once per system).
- Test the local model on a GPU, and with a model that stays loaded between files.
- Check the repetition problem of the local model more closely (decoding settings, e.g. temperature fallback or no-speech threshold).
- Use a human-corrected transcript for a subset, so WER does not only measure agreement with `gpt-4o-transcribe`.
- Publish the public report as a web page.
