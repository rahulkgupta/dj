# Repository Guidelines

## Project Structure & Module Organization
- `id3_tagger/` contains feature extraction, GPT tagging, schema definitions, and ID3 writing logic.
- `modal_tagger_db.py` defines the Modal app, `upload_batch`, `process_audio_file`, and `queue_and_process_all`.
- `upload_to_modal_volume.py` streams local files into the Modal volume; `setup_database.py` bootstraps the Postgres schema.
- `database.py` wraps SQLAlchemy models and helpers for stats/search; `content/` and `processed_music/` remain working dirs that stay out of git.

## Build, Test, and Development Commands
- Activate the virtualenv (`source venv/bin/activate`) and install deps with `pip install -r requirements.txt`.
- `python setup_database.py --stats` validates the `DATABASE_URL` connection and prints job totals.
- `python upload_to_modal_volume.py /path/to/music --queue` uploads audio and immediately queues processing.
- `modal run modal_tagger_db.py queue` re-queues everything already in the Modal volume.
- `python database.py stats` outputs aggregated job/songs information for quick smoke tests.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and descriptive `snake_case`; retain concise print logging for operational insight.
- Keep Modal config (app names, volume paths, models) centralized in `modal_tagger_db.py`; surface environment access through helper functions/modules rather than inline literals.

## Testing Guidelines
- No automated suite yet—add `pytest` cases when touching `id3_tagger/` or `database.py`, and exercise them against short audio fixtures.
- Document manual verification (e.g., file counts, sample metadata) in PR descriptions when altering tagging or persistence.

## Commit & Pull Request Guidelines
- Use present-tense, imperative commits (`Refactor queueing workflow`).
- PRs should describe the command paths touched, note required Modal/database migrations, and include validation steps reviewers can repeat.

## Security & Configuration Notes
- Secrets live in Modal (`modal secret create neon-db-url …`); never commit connection strings or local caches.
- Ensure generated media stays in gitignored directories and scrub personal metadata from any shared samples.
