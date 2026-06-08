# get-files container

A minimal repository for building a Docker container that downloads one or more files, where each file is configured entirely via environment variables.

## Features

- Configure multiple downloads using indexed environment variables (`FILE_1_*`, `FILE_2_*`, ...)
- Configure independent destination paths per file via env vars
- Per-file authentication support via env vars:
  - `none`
  - `bearer`
  - `basic`
  - custom `header`
- Optional per-file custom headers via JSON
- Deterministic exit codes for automation
- Automated tests with `pytest`

## Environment Variable Contract

For each file `N`:

- Required:
  - `FILE_N_URL`
  - `FILE_N_DEST`
- Optional:
  - `FILE_N_TIMEOUT_SECONDS` (defaults to `DEFAULT_TIMEOUT_SECONDS` or `60`)
  - `FILE_N_HEADERS_JSON` (JSON object, e.g. `{"Accept":"application/octet-stream"}`)
  - `FILE_N_AUTH_TYPE` (`none` | `bearer` | `basic` | `header`, defaults to `none`)

Authentication fields by type:

- `bearer`:
  - `FILE_N_AUTH_TOKEN`
- `basic`:
  - `FILE_N_AUTH_USERNAME`
  - `FILE_N_AUTH_PASSWORD`
- `header`:
  - `FILE_N_AUTH_HEADER_NAME`
  - `FILE_N_AUTH_HEADER_VALUE`

Global optional:

- `DEFAULT_TIMEOUT_SECONDS`

## Build

```bash
docker build -t get-files:latest .
```

## Run Examples

### 1. Download one public file

```bash
docker run --rm \
  -e FILE_1_URL="https://example.com/file.txt" \
  -e FILE_1_DEST="/downloads/file.txt" \
  -v "$PWD/output:/downloads" \
  get-files:latest
```

### 2. Download multiple files with different auth methods

```bash
docker run --rm \
  -e FILE_1_URL="https://api.example.com/reports/daily.csv" \
  -e FILE_1_DEST="/downloads/reports/daily.csv" \
  -e FILE_1_AUTH_TYPE="bearer" \
  -e FILE_1_AUTH_TOKEN="token-value" \
  -e FILE_2_URL="https://files.example.com/private/archive.zip" \
  -e FILE_2_DEST="/downloads/archive/archive.zip" \
  -e FILE_2_AUTH_TYPE="basic" \
  -e FILE_2_AUTH_USERNAME="my-user" \
  -e FILE_2_AUTH_PASSWORD="my-pass" \
  -e FILE_3_URL="https://gateway.example.com/export" \
  -e FILE_3_DEST="/downloads/export.json" \
  -e FILE_3_AUTH_TYPE="header" \
  -e FILE_3_AUTH_HEADER_NAME="X-API-Key" \
  -e FILE_3_AUTH_HEADER_VALUE="my-api-key" \
  -e FILE_3_HEADERS_JSON='{"Accept":"application/json"}' \
  -v "$PWD/output:/downloads" \
  get-files:latest
```

## Exit Codes

- `0`: all downloads succeeded
- `1`: one or more downloads failed
- `2`: configuration error

## Local Development

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run tests:

```bash
pytest -q
```
