import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


DEFAULT_TIMEOUT_SECONDS = 60


@dataclass
class FileSpec:
    index: int
    url: str
    destination: Path
    auth_type: str
    auth_token: Optional[str]
    auth_username: Optional[str]
    auth_password: Optional[str]
    auth_header_name: Optional[str]
    auth_header_value: Optional[str]
    extra_headers: Dict[str, str]
    timeout_seconds: int


def _parse_indices_from_env(env: Dict[str, str]) -> List[int]:
    indices: List[int] = []
    for key in env:
        if key.startswith("FILE_") and key.endswith("_URL"):
            raw_index = key[len("FILE_") : -len("_URL")]
            if raw_index.isdigit():
                indices.append(int(raw_index))
    return sorted(set(indices))


def _read_headers_json(raw: Optional[str], index: int) -> Dict[str, str]:
    if not raw:
        return {}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"FILE_{index}_HEADERS_JSON must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"FILE_{index}_HEADERS_JSON must be a JSON object")

    headers: Dict[str, str] = {}
    for k, v in parsed.items():
        headers[str(k)] = str(v)
    return headers


def _env_get(env: Dict[str, str], index: int, field: str) -> Optional[str]:
    return env.get(f"FILE_{index}_{field}")


def parse_file_specs(env: Optional[Dict[str, str]] = None) -> List[FileSpec]:
    env_map = env or dict(os.environ)
    default_timeout = int(env_map.get("DEFAULT_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))

    specs: List[FileSpec] = []
    indices = _parse_indices_from_env(env_map)
    if not indices:
        raise ValueError("No files configured. Set at least one FILE_<n>_URL environment variable.")

    for index in indices:
        url = _env_get(env_map, index, "URL")
        destination = _env_get(env_map, index, "DEST")
        if not url:
            raise ValueError(f"Missing FILE_{index}_URL")
        if not destination:
            raise ValueError(f"Missing FILE_{index}_DEST")

        auth_type = (_env_get(env_map, index, "AUTH_TYPE") or "none").strip().lower()
        if auth_type not in {"none", "bearer", "basic", "header"}:
            raise ValueError(
                f"FILE_{index}_AUTH_TYPE must be one of: none, bearer, basic, header"
            )

        spec = FileSpec(
            index=index,
            url=url,
            destination=Path(destination),
            auth_type=auth_type,
            auth_token=_env_get(env_map, index, "AUTH_TOKEN"),
            auth_username=_env_get(env_map, index, "AUTH_USERNAME"),
            auth_password=_env_get(env_map, index, "AUTH_PASSWORD"),
            auth_header_name=_env_get(env_map, index, "AUTH_HEADER_NAME"),
            auth_header_value=_env_get(env_map, index, "AUTH_HEADER_VALUE"),
            extra_headers=_read_headers_json(_env_get(env_map, index, "HEADERS_JSON"), index),
            timeout_seconds=int(_env_get(env_map, index, "TIMEOUT_SECONDS") or default_timeout),
        )
        _validate_auth(spec)
        specs.append(spec)

    return specs


def _validate_auth(spec: FileSpec) -> None:
    if spec.auth_type == "bearer" and not spec.auth_token:
        raise ValueError(f"FILE_{spec.index}_AUTH_TOKEN is required when AUTH_TYPE=bearer")

    if spec.auth_type == "basic" and (
        not spec.auth_username or spec.auth_password is None
    ):
        raise ValueError(
            f"FILE_{spec.index}_AUTH_USERNAME and FILE_{spec.index}_AUTH_PASSWORD are required when AUTH_TYPE=basic"
        )

    if spec.auth_type == "header" and (
        not spec.auth_header_name or spec.auth_header_value is None
    ):
        raise ValueError(
            f"FILE_{spec.index}_AUTH_HEADER_NAME and FILE_{spec.index}_AUTH_HEADER_VALUE are required when AUTH_TYPE=header"
        )


def _build_headers(spec: FileSpec) -> Dict[str, str]:
    headers = dict(spec.extra_headers)
    if spec.auth_type == "bearer":
        headers["Authorization"] = f"Bearer {spec.auth_token}"
    elif spec.auth_type == "header":
        headers[spec.auth_header_name or ""] = spec.auth_header_value or ""
    return headers


def _build_basic_auth(spec: FileSpec) -> Optional[Tuple[str, str]]:
    if spec.auth_type == "basic":
        return (spec.auth_username or "", spec.auth_password or "")
    return None


def download_file(spec: FileSpec) -> None:
    spec.destination.parent.mkdir(parents=True, exist_ok=True)

    headers = _build_headers(spec)
    auth = _build_basic_auth(spec)

    with requests.get(
        spec.url,
        headers=headers,
        auth=auth,
        timeout=spec.timeout_seconds,
        stream=True,
    ) as response:
        response.raise_for_status()
        with spec.destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    output.write(chunk)


def run(env: Optional[Dict[str, str]] = None) -> int:
    try:
        specs = parse_file_specs(env)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    failures = 0
    for spec in specs:
        try:
            print(f"Downloading FILE_{spec.index}: {spec.url} -> {spec.destination}")
            download_file(spec)
        except requests.RequestException as exc:
            failures += 1
            print(f"Download failed for FILE_{spec.index}: {exc}", file=sys.stderr)
        except OSError as exc:
            failures += 1
            print(f"Write failed for FILE_{spec.index}: {exc}", file=sys.stderr)

    if failures:
        print(f"Completed with {failures} failure(s)", file=sys.stderr)
        return 1

    print("All downloads completed successfully")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
