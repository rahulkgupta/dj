#!/usr/bin/env python3
"""
Upload local audio files to the Modal volume and optionally queue processing jobs.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Sequence

sys.path.append(os.path.dirname(__file__))

from modal_tagger_db import app, queue_and_process_all, upload_batch  # noqa: E402

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aiff"}


def iter_audio_files(root: Path) -> Iterable[Path]:
    """Yield audio files underneath the provided directory."""
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
            yield path


def chunk(items: Sequence[Path], size: int) -> Iterable[Sequence[Path]]:
    """Yield fixed-size chunks from a sequence."""
    for index in range(0, len(items), size):
        yield items[index : index + size]


def upload_directory(directory: Path, batch_size: int) -> int:
    """Upload all supported audio files to the Modal volume."""
    files = list(iter_audio_files(directory))
    if not files:
        print("No audio files found.")
        return 0

    print(f"Uploading {len(files)} files from {directory} (batch size {batch_size})...")

    uploaded = 0
    with app.run():
        for group in chunk(files, batch_size):
            payload = []
            for file_path in group:
                payload.append((file_path.read_bytes(), str(file_path.relative_to(directory))))
            upload_batch.remote(payload)
            uploaded += len(group)
            print(f"  ✓ Uploaded {uploaded}/{len(files)} files")

    print(f"Upload complete: {uploaded} files written to the Modal volume.")
    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload audio to Modal volume and queue processing.")
    parser.add_argument("directory", type=Path, help="Directory containing audio files.")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of files per upload batch.")
    parser.add_argument(
        "--queue",
        action="store_true",
        help="Queue every uploaded file for processing after the upload completes.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano-2025-08-07",
        help="Model to use when queueing processing jobs (see modal_tagger_db).",
    )
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.exists() or not directory.is_dir():
        raise SystemExit(f"Directory not found: {directory}")

    uploaded = upload_directory(directory, args.batch_size)

    if args.queue and uploaded:
        print("Queueing files for processing...")
        with app.run():
            result = queue_and_process_all.remote(model=args.model)
            print(result)
    elif uploaded:
        print("Files uploaded. Use `modal run modal_tagger_db.py queue` to process them later.")


if __name__ == "__main__":
    main()
