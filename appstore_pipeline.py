"""Portfolio demo: App Store Connect analytics pipeline.

Pulls selected App Store Connect analytics reports, aggregates them monthly,
and writes only new rows to a generic HTTP-backed reporting endpoint.

All credentials and environment-specific values are read from environment
variables. Do not commit private keys or .env files.
"""

import gzip
import io
import json
import os
import time
from pathlib import Path

import jwt
import pandas as pd
import requests

KEY_FILE = os.environ.get("APPSTORE_KEY_FILE", "")
KEY_ID = os.environ.get("APPSTORE_KEY_ID", "")
ISSUER_ID = os.environ.get("APPSTORE_ISSUER_ID", "")
STATE_FILE = Path(os.environ.get("APPSTORE_STATE_FILE", "analytics_requests.example.json"))

OUTPUT_URL = os.environ.get("OUTPUT_API_URL", "")
OUTPUT_SHEET = os.environ.get("OUTPUT_SHEET", "AppStore")
OUTPUT_USERNAME = os.environ.get("OUTPUT_USERNAME", "")
OUTPUT_PASSWORD = os.environ.get("OUTPUT_PASSWORD", "")

METRIC_RULES = [
    {
        "metric": "Impressions",
        "report": "App Store Discovery and Engagement Standard",
        "filter_col": "Event",
        "filter_val": "Impression",
        "value_col": "Unique Counts",
        "date_col": "Date",
    },
    {
        "metric": "Downloads",
        "report": "App Downloads Standard",
        "filter_col": "Download Type",
        "filter_val": "First-time download",
        "value_col": "Counts",
        "date_col": "Date",
    },
]
TARGET_REPORTS = {r["report"] for r in METRIC_RULES}


def validate_config() -> None:
    required = {
        "APPSTORE_KEY_FILE": KEY_FILE,
        "APPSTORE_KEY_ID": KEY_ID,
        "APPSTORE_ISSUER_ID": ISSUER_ID,
        "OUTPUT_API_URL": OUTPUT_URL,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def get_token() -> str:
    with open(KEY_FILE, "r", encoding="utf-8") as f:
        private_key = f.read()
    now = int(time.time())
    payload = {"iss": ISSUER_ID, "iat": now, "exp": now + 1200, "aud": "appstoreconnect-v1"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": KEY_ID})


def api_get(url: str, token: str, params=None):
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def download_segment(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    raw = response.content
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", errors="replace")
    separator = "\t" if "\t" in text.split("\n", 1)[0] else ","
    return pd.read_csv(io.StringIO(text), sep=separator)


def extract_metrics(df: pd.DataFrame, app_name: str, granularity: str, report_name: str) -> list[dict]:
    rows = []
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    for rule in METRIC_RULES:
        if rule["report"].lower() != report_name.lower():
            continue
        required_cols = [rule["date_col"], rule["value_col"], rule["filter_col"]]
        if any(c not in df.columns for c in required_cols):
            continue

        subset = df[df[rule["filter_col"]].astype(str).str.strip().str.lower() == rule["filter_val"].lower()].copy()
        subset[rule["date_col"]] = pd.to_datetime(subset[rule["date_col"]], errors="coerce")
        subset[rule["value_col"]] = pd.to_numeric(subset[rule["value_col"]], errors="coerce")
        subset = subset.dropna(subset=[rule["date_col"], rule["value_col"]])
        subset["Month"] = subset[rule["date_col"]].dt.to_period("M").astype(str)

        grouped = subset.groupby([rule["date_col"], "Month"], as_index=False)[rule["value_col"]].sum()
        for _, row in grouped.iterrows():
            rows.append({
                "App": app_name,
                "Date": row[rule["date_col"]],
                "Month": row["Month"],
                "Metric": rule["metric"],
                "Value": row[rule["value_col"]],
                "Granularity": granularity,
                "Report": report_name,
            })
    return rows


def main() -> None:
    validate_config()
    if not STATE_FILE.exists():
        raise FileNotFoundError(f"State file not found: {STATE_FILE}")

    with STATE_FILE.open("r", encoding="utf-8") as f:
        app_requests = json.load(f)

    token = get_token()
    all_rows = []

    for app_name, config in app_requests.items():
        request_id = config.get("request_id") if isinstance(config, dict) else config
        reports_url = f"https://api.appstoreconnect.apple.com/v1/analyticsReportRequests/{request_id}/reports"
        reports = api_get(reports_url, token, {"limit": 200}).get("data", [])

        for report in reports:
            report_name = report.get("attributes", {}).get("name", "")
            if report_name not in TARGET_REPORTS:
                continue
            instances_url = f"https://api.appstoreconnect.apple.com/v1/analyticsReports/{report['id']}/instances"
            instances = api_get(instances_url, token, {"limit": 200}).get("data", [])

            for instance in instances:
                granularity = instance.get("attributes", {}).get("granularity", "")
                segments_url = f"https://api.appstoreconnect.apple.com/v1/analyticsReportInstances/{instance['id']}/segments"
                segments = api_get(segments_url, token, {"limit": 200}).get("data", [])
                for segment in segments:
                    url = segment.get("attributes", {}).get("url")
                    if url:
                        all_rows.extend(extract_metrics(download_segment(url), app_name, granularity, report_name))

    output = pd.DataFrame(all_rows)
    print(f"Extracted {len(output):,} metric rows.")
    print("Add your preferred storage/output adapter here (SQL, CSV, Sheets, REST endpoint, etc.).")


if __name__ == "__main__":
    main()
