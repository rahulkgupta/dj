# DJ Audio Tagger - Project Documentation

## Project Overview
AI-powered audio tagging system for DJs that automatically generates DJ-specific metadata for music files using audio analysis and GPT models.

## Technical Stack
- **Language**: Python 3
- **Database**: PostgreSQL (Neon) for metadata storage and search
- **Key Dependencies**: 
  - `librosa` - Audio feature extraction
  - `dspy-ai` - GPT integration for tag generation
  - `mutagen` - ID3 tag reading/writing
  - `modal` - Cloud processing platform
  - `psycopg2-binary` - PostgreSQL database access
  - `numpy/scipy` - Signal processing

## Project Structure

```
id3_tagger/              # Core tagging module
├── audio_analyzer.py    # Extracts BPM, key, energy, spectral features
├── dspy_tagger.py       # AI tag generation using GPT
├── tag_definitions.py   # Tag schemas and predefined options
└── tag_writer.py        # Read/write ID3 tags (MP3, MP4, FLAC)

# Database Integration
database.py              # PostgreSQL database utilities and models
setup_database.py        # Initialise schema and verify connectivity (idempotent)

# Modal Processing
modal_tagger_db.py       # Modal functions: upload_batch, process_audio_file, queue_and_process_all
upload_to_modal_volume.py # CLI helper to upload local files to the Modal volume
```

## Processing Workflows

### Database-Integrated Processing (Recommended)

1. **Install dependencies**
   ```bash
   source venv/bin/activate && pip install -r requirements.txt
   ```

2. **Initialise / verify the database schema**
   ```bash
   export DATABASE_URL="postgres://..."
   python setup_database.py --stats
   ```

3. **Upload local audio to the Modal volume**
   ```bash
   python upload_to_modal_volume.py /path/to/music --batch-size 25 --queue
   ```
   - Omitting `--queue` only uploads; follow with `modal run modal_tagger_db.py queue` later to process anything already in the volume.

4. **Monitor database state**
   ```bash
   python database.py stats
   ```
   - Extend `database.py` with custom queries (e.g., search filters) as needed for your tooling or dashboards.

## Tag System

### Technical Tags (from audio analysis)
- `bpm` - Beats per minute
- `key` - Musical key 
- `camelot_key` - Harmonic mixing notation

### DJ-Specific Tags (AI-generated with enforced validation)
- `top_genres` - Top 3 genres ordered by confidence
- `energy` - Energy level: **low**, **medium**, **high**, **peak**, **dynamic** (enforced enum)
- `mood` - 2-3 moods from **finalized 20-mood system** (enforced enum):
  - **Core emotions**: euphoric, melancholic, uplifting, romantic, dark, dreamy
  - **Movement**: groovy, hypnotic, driving, smooth, raw, playful
  - **Intensity**: intense, peaceful, epic, sensual
  - **Character**: nostalgic, cerebral, spiritual, rebellious
- `set_position` - opener/warmup/build/peak/breakdown/closer  
- `bassline_type` - Type of bassline
- `vocal_type` - Type of vocals
- `prominent_instruments` - 2-4 main instruments
- `danceability` - Score 0-10

### New Tag System Features
- **Enforced validation** using Pydantic enums ensures consistent tagging
- **Backward compatibility** maintained for `energy_level` field

## Implementation Details

### Modal Processing
- Uses `spawn()` for parallel, fire-and-forget processing
- Batch size of 20-50 files for optimal performance
- Run with `--detach` flag for persistent execution

### Performance Optimizations
- Numba disabled (`NUMBA_DISABLE_JIT=1`) to avoid compilation race conditions
- Parallel downloads using spawn batches
- Modal Volume for persistent storage

### Database Storage
- **PostgreSQL Database**: All song metadata stored in structured tables
- **Processed Files**: Saved in Modal volume `processed/` directory
- **Search Capabilities**: Fast queries by BPM, key, mood, genre, energy, artist
- **Deduplication**: Automatic detection of duplicate files by hash
- **Full-Text Search**: Search across artist, title, and comments

## Environment Setup

### Required Setup
- **PostgreSQL Database**: Neon database connection string
- **OpenAI API Key**: For AI tag generation
- **ALWAYS activate virtual environment first**: `source venv/bin/activate`

### Quick Setup (Database Integration)
```bash
# Install dependencies
source venv/bin/activate && pip install -r requirements.txt

# Initialise/verify database schema
export DATABASE_URL="postgres://..."
python setup_database.py --stats

# Upload and queue in one step
python upload_to_modal_volume.py /path/to/music --queue
```

### Manual Modal Setup
```bash
modal setup  # authenticate once
modal secret create neon-db-url DATABASE_URL="postgresql://..."
modal secret create openai-api-key OPENAI_API_KEY="sk-..."
```

## Common Operations

### Upload & Queue
```bash
# Upload without queueing
python upload_to_modal_volume.py /path/to/music

# Queue everything currently on the Modal volume
modal run modal_tagger_db.py queue
```

### Database Management
```bash
# Stats snapshot
python database.py stats
```

### Local Processing
```bash
## Important Notes

1. **Always activate venv first**: `source venv/bin/activate`
2. **Ensure secrets exist**: Modal secrets `openai-api-key` and `neon-db-url` must be present before queueing
3. Uploads preserve directory structure so processed files mirror local layout
4. Tag generation uses `gpt-5-nano-2025-08-07` by default—override with `--model` if needed
5. Supported formats: MP3, WAV, FLAC, M4A, AIFF

## Troubleshooting

- **Modal timeout**: Reduce queue size or re-run `modal_tagger_db.queue` to restart stalled jobs
- **Database auth errors**: Verify `DATABASE_URL` locally and in the Modal secret; ensure the Neon instance accepts your IP
- **Missing tags**: Inspect Modal logs for the failing `process_audio_file` call; dedupe logic skips files whose hashes already exist
