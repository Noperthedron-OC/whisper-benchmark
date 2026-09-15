#!/usr/bin/env python3
"""
Run both local whisper.cpp and OpenAI Whisper API on the corpus.
Saves per-file JSON to results/raw/local/ and results/raw/api/.
Idempotent: skips files already processed.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def get_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def transcribe_local(m4a: Path) -> tuple[str, float]:
    wav = Path(tempfile.mktemp(suffix=".wav"))
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(m4a), "-ar", "16000", "-ac", "1",
             str(wav), "-y", "-loglevel", "quiet"],
            check=True, timeout=120
        )
        t0 = time.perf_counter()
        result = subprocess.run(
            [config.WHISPER_CLI, "-m", config.WHISPER_MODEL,
             "-f", str(wav)] + config.WHISPER_FLAGS,
            capture_output=True, text=True, timeout=config.LOCAL_TIMEOUT
        )
        elapsed = time.perf_counter() - t0
        return result.stdout.strip(), elapsed
    finally:
        wav.unlink(missing_ok=True)


def transcribe_api(m4a: Path) -> tuple[str, float]:
    from openai import OpenAI
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    t0 = time.perf_counter()
    with open(m4a, "rb") as f:
        response = client.audio.transcriptions.create(
            model=config.OPENAI_MODEL,
            file=f,
            response_format="text",
        )
    elapsed = time.perf_counter() - t0
    return response.strip(), elapsed


def load_corpus() -> list[dict]:
    entries = []
    for line in config.CORPUS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        stem, m4a, ref = line.split("\t")
        entries.append({
            "stem": stem,
            "m4a": Path(m4a),
            "ref": Path(ref) if ref != "NONE" else None,
        })
    return entries


def run_local(entries: list[dict], limit: int | None, dry_run: bool):
    config.RAW_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    todo = [e for e in entries if not (config.RAW_LOCAL_DIR / f"{e['stem']}.json").exists()]
    if limit:
        todo = todo[:limit]
    print(f"\n[Local] {len(todo)} files to transcribe")
    for entry in tqdm(todo, unit="file"):
        if dry_run:
            print(f"  DRY: {entry['stem']}")
            continue
        try:
            duration = get_duration(entry["m4a"])
            text, elapsed = transcribe_local(entry["m4a"])
            out = {"stem": entry["stem"], "text": text, "time_s": round(elapsed, 3),
                   "duration_s": round(duration, 3)}
            (config.RAW_LOCAL_DIR / f"{entry['stem']}.json").write_text(json.dumps(out, indent=2))
        except Exception as e:
            tqdm.write(f"  ERROR {entry['stem']}: {e}")


def run_api(entries: list[dict], limit: int | None, dry_run: bool):
    config.RAW_API_DIR.mkdir(parents=True, exist_ok=True)
    todo = [e for e in entries if not (config.RAW_API_DIR / f"{e['stem']}.json").exists()]
    if limit:
        todo = todo[:limit]
    print(f"\n[API]   {len(todo)} files to transcribe")
    for entry in tqdm(todo, unit="file"):
        if dry_run:
            print(f"  DRY: {entry['stem']}")
            continue
        for attempt in range(2):
            try:
                duration = get_duration(entry["m4a"])
                text, elapsed = transcribe_api(entry["m4a"])
                cost = round(duration / 60 * config.OPENAI_COST_PER_MINUTE, 6)
                out = {"stem": entry["stem"], "text": text, "time_s": round(elapsed, 3),
                       "duration_s": round(duration, 3), "cost_usd": cost}
                (config.RAW_API_DIR / f"{entry['stem']}.json").write_text(json.dumps(out, indent=2))
                break
            except Exception as e:
                if attempt == 0:
                    tqdm.write(f"  RETRY {entry['stem']}: {e}")
                    time.sleep(config.API_RETRY_DELAY)
                else:
                    tqdm.write(f"  ERROR {entry['stem']}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Whisper benchmark runner")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Process only first N files (for testing)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entries = load_corpus()
    print(f"Corpus: {len(entries)} files ({sum(1 for e in entries if e['ref'])} with iOS ref)")

    if not args.api_only:
        run_local(entries, args.limit, args.dry_run)
    if not args.local_only:
        run_api(entries, args.limit, args.dry_run)

    print("\nDone. Run analyze.py next.")


if __name__ == "__main__":
    main()
