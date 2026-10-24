#!/usr/bin/env python3
"""
Compute per-file and aggregate metrics from benchmark results.
Ground truth: config.GROUND_TRUTH_BACKEND (gpt-4o-transcribe).
iOS reference ignored — all WER is computed against the ground truth backend.

Recordings whose reference has fewer than config.MIN_REFERENCE_WORDS words are flagged
"excluded": they stay in the per-file rows and in the cost total, but are left out of every
RTF and WER statistic (one word is a 10-100 % error there and says nothing about quality).

Outputs results/metrics.json.
"""

import json
import math
import re
import statistics
import sys
from pathlib import Path

from jiwer import wer

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[-–—/]", " ", text)   # hyphens/dashes → space
    text = re.sub(r"[^\w\s]", "", text)   # strip all punctuation incl. periods
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_wer(ref: str, hyp: str) -> float | None:
    """WER of hyp against ref. No reference words -> None (undefined).
    An empty hypothesis against a non-empty reference is a real failure (every word deleted),
    so it counts as 1.0 instead of silently dropping the file from the statistics."""
    ref_n, hyp_n = normalise(ref), normalise(hyp)
    if not ref_n:
        return None
    if not hyp_n:
        return 1.0
    try:
        return round(wer(ref_n, hyp_n), 4)
    except Exception:
        return None


def percentile(values: list[float], p: int) -> float:
    """Median for p=50 (mean of the two middle values for an even count);
    nearest-rank percentile otherwise."""
    if not values:
        return 0.0
    values = sorted(values)
    if p == 50:
        return round(statistics.median(values), 4)
    idx = math.ceil(len(values) * p / 100) - 1
    return round(values[min(max(idx, 0), len(values) - 1)], 4)


def load_results(directory: Path) -> dict[str, dict]:
    results = {}
    if not directory.exists():
        return results
    for f in directory.glob("*.json"):
        data = json.loads(f.read_text())
        results[data["stem"]] = data
    return results


def agg_stats(values: list[float]) -> dict:
    if not values:
        return {}
    return {
        "mean": round(sum(values) / len(values), 4),
        "median": percentile(values, 50),
        "p95": percentile(values, 95),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "n": len(values),
    }


def main():
    local = load_results(config.RAW_LOCAL_DIR)

    api_results = {}
    for backend in config.API_BACKENDS:
        d = config.RESULTS_DIR / "raw" / backend["key"]
        api_results[backend["key"]] = load_results(d)

    all_stems = set(local.keys())
    for res in api_results.values():
        all_stems |= set(res.keys())
    stems = sorted(all_stems)

    if not stems:
        print("No results found. Run benchmark.py first.")
        sys.exit(1)

    backend_keys = [b["key"] for b in config.API_BACKENDS if api_results.get(b["key"])]
    gt_key = config.GROUND_TRUTH_BACKEND
    gt_results = api_results.get(gt_key, {})

    print(f"Analyzing {len(stems)} files | local: {len(local)} | backends: {backend_keys}")
    print(f"Ground truth: {gt_key}")

    per_file = []
    for stem in stems:
        l = local.get(stem)
        first_api = next((api_results[k].get(stem) for k in backend_keys if api_results[k].get(stem)), None)
        duration = (l or first_api or {}).get("duration_s", 0)
        gt_text = gt_results.get(stem, {}).get("text") if gt_results else None

        ref_words = len(normalise(gt_text).split()) if gt_text else 0
        row = {
            "stem": stem,
            "duration_s": duration,
            "ground_truth_key": gt_key,
            "reference_words": ref_words,
            "excluded": ref_words < config.MIN_REFERENCE_WORDS,
            "local_text": l["text"] if l else None,
        }

        if l:
            row["local_time_s"] = l["time_s"]
            row["local_rtf"] = round(l["time_s"] / duration, 4) if duration else None
            row["local_words"] = len(l["text"].split())
            row["local_wer"] = safe_wer(gt_text, l["text"]) if gt_text else None

        for key in backend_keys:
            a = api_results[key].get(stem)
            row[f"{key}_text"] = a["text"] if a else None
            if a:
                row[f"{key}_time_s"] = a["time_s"]
                row[f"{key}_rtf"] = round(a["time_s"] / duration, 4) if duration else None
                row[f"{key}_words"] = len(a["text"].split())
                row[f"{key}_cost_usd"] = a.get("cost_usd", 0)
                if key != gt_key and gt_text:
                    row[f"{key}_wer"] = safe_wer(gt_text, a["text"])
                else:
                    row[f"{key}_wer"] = 0.0 if key == gt_key and gt_text else None

        per_file.append(row)

    kept = [r for r in per_file if not r["excluded"]]
    aggregate = {
        "total_files": len(per_file),
        "total_duration_min": round(sum(r["duration_s"] for r in per_file) / 60, 2),
        "analysed_files": len(kept),
        "excluded_files": len(per_file) - len(kept),
        "min_reference_words": config.MIN_REFERENCE_WORDS,
        "analysed_duration_min": round(sum(r["duration_s"] for r in kept) / 60, 2),
        "backend_keys": backend_keys,
        "ground_truth_key": gt_key,
        # speed and error statistics: analysed files only; cost: every file (that is what was billed)
        "local_rtf": agg_stats([r["local_rtf"] for r in kept if r.get("local_rtf")]),
        "local_wer": agg_stats([r["local_wer"] for r in kept if r.get("local_wer") is not None]),
    }
    for key in backend_keys:
        aggregate[f"{key}_rtf"] = agg_stats([r[f"{key}_rtf"] for r in kept if r.get(f"{key}_rtf")])
        aggregate[f"{key}_total_cost"] = round(sum(r.get(f"{key}_cost_usd", 0) for r in per_file), 4)
        if key != gt_key:  # the reference is perfect by definition; it has no WER statistics
            aggregate[f"{key}_wer"] = agg_stats(
                [r[f"{key}_wer"] for r in kept if r.get(f"{key}_wer") is not None])

    metrics = {"per_file": per_file, "aggregate": aggregate}
    config.METRICS_FILE.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    print(f"\n{'='*55}")
    print(f"Total audio:    {aggregate['total_duration_min']:.1f} min "
          f"| analysed: {aggregate['analysed_files']} files, excluded {aggregate['excluded_files']} "
          f"(reference < {config.MIN_REFERENCE_WORDS} words)")
    for key in backend_keys:
        print(f"Cost [{key}]: ${aggregate[f'{key}_total_cost']:.4f}")
    if aggregate["local_rtf"]:
        print(f"Local RTF:      {aggregate['local_rtf']['mean']:.3f} mean | {aggregate['local_rtf']['p95']:.3f} p95")
    for key in backend_keys:
        s = aggregate[f"{key}_rtf"]
        if s:
            print(f"{key} RTF:  {s['mean']:.3f} mean | {s['p95']:.3f} p95")
    if aggregate["local_wer"].get("n"):
        print(f"Local WER vs {gt_key}: {aggregate['local_wer']['mean']:.3f} (n={aggregate['local_wer']['n']})")
    for key in backend_keys:
        s = aggregate.get(f"{key}_wer", {})
        if s.get("n"):
            print(f"{key} WER vs {gt_key}: {s['mean']:.3f} (n={s['n']})")
    print(f"{'='*55}")
    print(f"\nSaved → {config.METRICS_FILE}\nRun report.py next.")


if __name__ == "__main__":
    main()
