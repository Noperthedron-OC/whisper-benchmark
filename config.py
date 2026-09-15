import os
from pathlib import Path

ROOT = Path(__file__).parent
CORPUS_DIR = Path("/home/mimir/shared/imports/iOS_dictations/processed")
RESULTS_DIR = ROOT / "results"
RAW_LOCAL_DIR = RESULTS_DIR / "raw" / "local"
RAW_API_DIR = RESULTS_DIR / "raw" / "api"
METRICS_FILE = RESULTS_DIR / "metrics.json"
REPORT_FILE = RESULTS_DIR / "report.html"
CORPUS_FILE = ROOT / "data" / "corpus.txt"

WHISPER_CLI = "/home/mimir/opt/whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = "/home/mimir/opt/whisper.cpp/models/ggml-large-v3-turbo-q5_0.bin"
WHISPER_FLAGS = ["--language", "auto", "--no-timestamps", "--no-prints"]

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# API backends to benchmark — each gets its own results/raw/<key>/ directory
API_BACKENDS = [
    {"key": "whisper-1",        "model": "whisper-1",         "cost_per_min": 0.006},
    {"key": "gpt-4o-transcribe","model": "gpt-4o-transcribe", "cost_per_min": 0.006},
]

LOCAL_TIMEOUT = 300
API_TIMEOUT = 120
API_RETRY_DELAY = 5
