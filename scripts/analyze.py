#!/usr/bin/env python3
"""
Compute per-file and aggregate metrics from benchmark results.
Outputs results/metrics.json.
"""

import json
import re
import sys
from pathlib import Path

from jiwer import wer

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def normalise(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[-–—/]", " ", text)   # hyphens/dashes → space (preserves word boundaries)
    text = re.sub(r"[^\w\s]", "", text)   # strip remaining punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_wer(ref: str, hyp: str) -> float | None:
    ref_n, hyp_n = normalise(ref), normalise(hyp)
    if not ref_n:
        return None
    try:
        return round(wer(ref_n, hyp_n), 4)
    except Exception:
        return None


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = int(len(values) * p / 100)
    return round(values[min(idx, len(values) - 1)], 4)


def load_results(directory: Path) -> dict[str, dict]:
    results = {}
    for f in directory.glob("*.json"):
        data = json.loads(f.read_text())
        results[data["stem"]] = data
    return results


def main():
    local = load_results(config.RAW_LOCAL_DIR)
    api = load_results(config.RAW_API_DIR)

    if not local and not api:
        print("No results found. Run benchmark.py first.")
        sys.exit(1)

    stems = sorted(set(local) | set(api))
    print(f"Analyzing {len(stems)} files ({len(local)} local, {len(api)} API results)")

    per_file = []
    for stem in stems:
        l = local.get(stem)
        a = api.get(stem)
        duration = (l or a).get("duration_s", 0)

        # Load iOS reference if available
        ref_path = config.CORPUS_DIR / f"{stem}.txt" if hasattr(config, "CORPUS_DIR") else None
        ref_text = None
        corpus_ref = config.CORPUS_DIR / f"{stem}.txt"
        if corpus_ref.exists():
            ref_text = corpus_ref.read_text().strip()

        row = {
            "stem": stem,
            "duration_s": duration,
            "has_ios_ref": ref_text is not None,
        }

        if l:
            row["local_time_s"] = l["time_s"]
            row["local_rtf"] = round(l["time_s"] / duration, 4) if duration else None
            row["local_words"] = len(l["text"].split())
            row["local_wer"] = safe_wer(ref_text, l["text"]) if ref_text else None
        if a:
            row["api_time_s"] = a["time_s"]
            row["api_rtf"] = round(a["time_s"] / duration, 4) if duration else None
            row["api_words"] = len(a["text"].split())
            row["api_wer"] = safe_wer(ref_text, a["text"]) if ref_text else None
            row["api_cost_usd"] = a.get("cost_usd", round(duration / 60 * config.OPENAI_COST_PER_MINUTE, 6))

        if l and a:
            row["cross_wer"] = safe_wer(a["text"], l["text"])

        # Store transcript snippets for diff viewer
        row["local_text"] = l["text"] if l else None
        row["api_text"] = a["text"] if a else None
        row["ios_text"] = ref_text

        per_file.append(row)

    # Aggregate stats
    def agg(key: str) -> dict:
        vals = [r[key] for r in per_file if r.get(key) is not None]
        if not vals:
            return {}
        return {
            "mean": round(sum(vals) / len(vals), 4),
            "median": percentile(vals, 50),
            "p95": percentile(vals, 95),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "n": len(vals),
        }

    aggregate = {
        "total_files": len(per_file),
        "files_with_ios_ref": sum(1 for r in per_file if r["has_ios_ref"]),
        "total_duration_min": round(sum(r["duration_s"] for r in per_file) / 60, 2),
        "total_api_cost_usd": round(sum(r.get("api_cost_usd", 0) for r in per_file), 4),
        "local_rtf": agg("local_rtf"),
        "api_rtf": agg("api_rtf"),
        "local_wer": agg("local_wer"),
        "api_wer": agg("api_wer"),
        "cross_wer": agg("cross_wer"),
        "local_time_s": agg("local_time_s"),
        "api_time_s": agg("api_time_s"),
    }

    metrics = {"per_file": per_file, "aggregate": aggregate}
    config.METRICS_FILE.write_text(json.dumps(metrics, indent=2, ensure_ascii=False))

    print(f"\n{'='*50}")
    print(f"Total audio:    {aggregate['total_duration_min']:.1f} min")
    print(f"API cost:       ${aggregate['total_api_cost_usd']:.4f}")
    if aggregate["local_rtf"]:
        print(f"Local RTF:      {aggregate['local_rtf']['mean']:.3f} (mean) | {aggregate['local_rtf']['p95']:.3f} (p95)")
    if aggregate["api_rtf"]:
        print(f"API RTF:        {aggregate['api_rtf']['mean']:.3f} (mean) | {aggregate['api_rtf']['p95']:.3f} (p95)")
    if aggregate["local_wer"].get("n"):
        print(f"Local WER:      {aggregate['local_wer']['mean']:.3f} (mean, n={aggregate['local_wer']['n']})")
    if aggregate["api_wer"].get("n"):
        print(f"API WER:        {aggregate['api_wer']['mean']:.3f} (mean, n={aggregate['api_wer']['n']})")
    if aggregate["cross_wer"].get("n"):
        print(f"Cross-WER:      {aggregate['cross_wer']['mean']:.3f} (mean)")
    print(f"{'='*50}")
    print(f"\nSaved to {config.METRICS_FILE}")
    print("Run report.py next.")


if __name__ == "__main__":
    main()
