#!/usr/bin/env python3
"""
Modal functions for uploading audio to a shared volume and processing tracks with
database-backed metadata storage.
"""

import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import modal

from database import Database
from id3_tagger.audio_analyzer import extract_audio_features
from id3_tagger.dspy_tagger import create_tagger
from id3_tagger.tag_writer import read_existing_tags, write_tags

# Modal configuration ---------------------------------------------------------

app = modal.App("dj-audio-tagger-db")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .run_commands("apt-get update && apt-get install -y ffmpeg libsndfile1")
    .pip_install(
        "librosa==0.11.0",
        "dspy-ai>=3.0.0",
        "mutagen>=1.45.0",
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
    )
    .add_local_python_source("id3_tagger")
    .add_local_file("database.py", "/root/database.py")
)

volume = modal.Volume.from_name("dj-audio-files-db", create_if_missing=True)

VOLUME_PATH = "/audio"
PROCESSED_DIR = f"{VOLUME_PATH}/processed"
MUSIC_DIR = f"{VOLUME_PATH}/music"

OPENAI_SECRET = modal.Secret.from_name("openai-api-key")
NEON_SECRET = modal.Secret.from_name("neon-db-url")


def _ensure_volume_dirs() -> None:
    """Make sure music and processed directories exist on the Modal volume."""
    os.makedirs(MUSIC_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)


# Upload helpers --------------------------------------------------------------

@app.function(
    image=image,
    volumes={VOLUME_PATH: volume},
    timeout=600,
)
def upload_batch(files: List[Tuple[bytes, str]]) -> List[str]:
    """
    Upload a batch of files to the Modal volume.

    Args:
        files: List of (file_bytes, relative_path) tuples.

    Returns:
        List of absolute paths written to the volume.
    """
    _ensure_volume_dirs()
    uploaded_paths: List[str] = []

    for file_data, relative_path in files:
        safe_relative = Path(relative_path)
        if safe_relative.is_absolute() or ".." in safe_relative.parts:
            raise ValueError(f"Illegal relative path: {relative_path}")

        file_path = Path(MUSIC_DIR) / safe_relative
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "wb") as destination:
            destination.write(file_data)

        uploaded_paths.append(str(file_path))

    volume.commit()
    return uploaded_paths


# Processing ------------------------------------------------------------------

@app.function(
    image=image,
    secrets=[OPENAI_SECRET, NEON_SECRET],
    volumes={VOLUME_PATH: volume},
    timeout=300,
    cpu=2,
    memory=4096,
)
def process_audio_file(file_path: str, model: str = "gpt-5-nano-2025-08-07") -> Dict[str, object]:
    """
    Process an uploaded audio file: extract features, generate tags, persist to DB,
    and copy the tagged file into the processed directory.
    """
    _ensure_volume_dirs()
    start_time = time.time()
    db = Database()

    try:
        with open(file_path, "rb") as source:
            original_bytes = source.read()
    except FileNotFoundError as exc:
        return {
            "status": "failed",
            "file_path": file_path,
            "error": f"File not found: {exc}",
        }

    file_hash = hashlib.md5(original_bytes).hexdigest()
    file_name = os.path.basename(file_path)
    modal_job_id = str(uuid.uuid4())
    job_id = db.create_job(modal_job_id=modal_job_id, file_path=file_path, file_hash=file_hash)

    try:
        print(f"[dedupe] Checking hash {file_hash} for {file_name}")
        existing_song_id = db.song_exists(file_hash)
        if existing_song_id:
            print(f"[dedupe] Found existing song_id={existing_song_id} for hash {file_hash}")
            processing_time = time.time() - start_time
            db.update_job_status(job_id, "completed", processing_time=processing_time)
            return {
                "status": "already_processed",
                "job_id": job_id,
                "song_id": existing_song_id,
                "file_path": file_path,
                "processing_time": processing_time,
            }

        audio_features = extract_audio_features(file_path, use_cache=False)
        existing_tags = read_existing_tags(file_path)
        tagger = create_tagger(model)
        tags = tagger(audio_features, file_name, existing_tags)

        if not write_tags(file_path, tags):
            raise RuntimeError("Failed to write tags to file")

        relative_path = file_path.replace(f"{MUSIC_DIR}/", "")
        processed_path = Path(PROCESSED_DIR) / relative_path
        processed_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, processed_path)

        # Restore original bytes so future dedupe checks see a consistent hash.
        with open(file_path, "wb") as destination:
            destination.write(original_bytes)

        song_id = db.create_song(
            job_id=job_id,
            file_path=str(processed_path),
            file_hash=file_hash,
            file_size=len(original_bytes),
            audio_features=audio_features,
            tags=tags,
        )

        processing_time = time.time() - start_time
        db.update_job_status(job_id, "completed", processing_time=processing_time)
        volume.commit()

        return {
            "status": "success",
            "job_id": job_id,
            "song_id": song_id,
            "file_path": file_path,
            "processed_path": str(processed_path),
            "processing_time": processing_time,
        }

    except Exception as exc:  # pylint: disable=broad-except
        processing_time = time.time() - start_time
        db.update_job_status(job_id, "failed", error_message=str(exc), processing_time=processing_time)
        return {
            "status": "failed",
            "job_id": job_id,
            "file_path": file_path,
            "error": str(exc),
            "processing_time": processing_time,
        }


@app.function(
    image=image,
    secrets=[OPENAI_SECRET, NEON_SECRET],
    volumes={VOLUME_PATH: volume},
    timeout=86400,
    cpu=2,
)
def queue_and_process_all(model: str = "gpt-5-nano-2025-08-07") -> str:
    """
    Queue every audio file that exists in the Modal volume for processing.
    """
    _ensure_volume_dirs()

    import glob

    patterns = ("*.mp3", "*.wav", "*.flac", "*.m4a", "*.aiff")
    audio_files: List[str] = []

    for pattern in patterns:
        audio_files.extend(glob.glob(f"{MUSIC_DIR}/**/{pattern}", recursive=True))

    if not audio_files:
        return "No audio files found in the Modal volume."

    for file_path in audio_files:
        process_audio_file.spawn(file_path, model)

    return (
        f"Queued {len(audio_files)} files for processing. Jobs will continue running "
        "on Modal until completion."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Modal helpers for DJ audio tagging.")
    parser.add_argument(
        "command",
        choices=["queue"],
        help="Command to execute. Use 'queue' to process every file already uploaded.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5-nano-2025-08-07",
        help="Model name used by the tagging pipeline.",
    )
    args = parser.parse_args()

    if args.command == "queue":
        with app.run():
            result = queue_and_process_all.remote(model=args.model)
            print(result)
