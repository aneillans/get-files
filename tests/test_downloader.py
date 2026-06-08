from pathlib import Path
from typing import Iterable

import pytest

from src.downloader import download_file, parse_file_specs, run


class FakeResponse:
    def __init__(self, chunks: Iterable[bytes], status_code: int = 200):
        self._chunks = list(chunks)
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 0):
        del chunk_size
        for chunk in self._chunks:
            yield chunk


def test_parse_multiple_files_with_auth_modes():
    env = {
        "FILE_1_URL": "https://example.com/a",
        "FILE_1_DEST": "/tmp/a.txt",
        "FILE_1_AUTH_TYPE": "bearer",
        "FILE_1_AUTH_TOKEN": "abc",
        "FILE_2_URL": "https://example.com/b",
        "FILE_2_DEST": "/tmp/b.txt",
        "FILE_2_AUTH_TYPE": "basic",
        "FILE_2_AUTH_USERNAME": "user",
        "FILE_2_AUTH_PASSWORD": "pass",
    }

    specs = parse_file_specs(env)

    assert len(specs) == 2
    assert specs[0].auth_type == "bearer"
    assert specs[1].auth_type == "basic"


def test_parse_requires_file_configuration():
    with pytest.raises(ValueError):
        parse_file_specs({})


def test_parse_rejects_invalid_headers_json():
    env = {
        "FILE_1_URL": "https://example.com/a",
        "FILE_1_DEST": "/tmp/a.txt",
        "FILE_1_HEADERS_JSON": "not-json",
    }

    with pytest.raises(ValueError):
        parse_file_specs(env)


def test_download_file_writes_to_destination(monkeypatch, tmp_path: Path):
    destination = tmp_path / "files" / "sample.txt"

    calls = {}

    def fake_get(url, headers=None, auth=None, timeout=None, stream=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["auth"] = auth
        calls["timeout"] = timeout
        calls["stream"] = stream
        return FakeResponse([b"hello", b" ", b"world"])

    monkeypatch.setattr("src.downloader.requests.get", fake_get)

    spec = parse_file_specs(
        {
            "FILE_1_URL": "https://example.com/data.txt",
            "FILE_1_DEST": str(destination),
            "FILE_1_AUTH_TYPE": "header",
            "FILE_1_AUTH_HEADER_NAME": "X-Api-Key",
            "FILE_1_AUTH_HEADER_VALUE": "secret",
            "FILE_1_HEADERS_JSON": '{"Accept":"application/octet-stream"}',
        }
    )[0]

    download_file(spec)

    assert destination.read_bytes() == b"hello world"
    assert calls["url"] == "https://example.com/data.txt"
    assert calls["headers"]["X-Api-Key"] == "secret"
    assert calls["headers"]["Accept"] == "application/octet-stream"
    assert calls["auth"] is None
    assert calls["stream"] is True


def test_run_returns_nonzero_for_config_error():
    assert run({}) == 2
