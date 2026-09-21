# App Store Connect Analytics Pipeline

A portfolio-ready Python pipeline that extracts selected analytics metrics from the Apple App Store Connect API and transforms them into a clean monthly reporting dataset for BI tools such as Power BI.

## What this demonstrates

- App Store Connect API authentication with JWT / ES256
- Automated analytics report retrieval
- Gzip/CSV/TSV handling
- Data cleaning and aggregation with pandas
- Idempotent reporting-pipeline design
- Secure configuration through environment variables

## Architecture

```text
App Store Connect API
        ↓
Python extraction + transformation
        ↓
Monthly analytics dataset
        ↓
Reporting storage / REST API / CSV / database
        ↓
Power BI or another BI tool
```

## Metrics in the demo

- Impressions
- First-time downloads

The code is intentionally generic and contains no production credentials, client names, application IDs, or private infrastructure details.

## Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to your own private configuration source and set the required environment variables.
4. Copy `analytics_requests.example.json` to `analytics_requests.json` and add your own App Store Connect analytics report request IDs.
5. Run:

```bash
python appstore_pipeline.py
```

## Security

Never commit Apple `.p8` private keys, passwords, API credentials, real report request IDs, or `.env` files.

## Portfolio note

This repository is a sanitized demonstration of a production analytics pattern. All organization-specific names, identifiers, credentials, and endpoints have been removed.
