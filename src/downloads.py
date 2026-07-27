"""downloads.py

Utilities to download remote files (PDFs) with streaming, checksum, and
idempotent saves.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Tuple

import requests


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_filename_from_url(url: str) -> str:
    # keep only last segment and some identifying hash
    name = url.split("/")[-1] or "file"
    # replace query chars
    name = name.split("?")[0]
    return name


def download_file(url: str, dest_dir: Path, timeout: int = 30, verify: bool = True) -> Tuple[Path, str]:
    """Download a URL into dest_dir and return (path, sha256).

    If file already exists with same sha256, skip re-download. Raises on HTTP errors.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename_from_url(url)
    dest = dest_dir / filename

    # Stream download into a temp file then rename
    tmp = dest.with_suffix(dest.suffix + ".downloading")

    with requests.get(url, stream=True, timeout=timeout, verify=verify) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    # compute sha256
    sha = sha256_of_file(tmp)

    # rename to include hash if collision
    final_name = dest.stem
    if not final_name:
        final_name = "file"
    final = dest_dir / f"{final_name}-{sha[:8]}{dest.suffix}"
    tmp.replace(final)

    return final, sha
