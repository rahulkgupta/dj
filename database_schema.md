# Audio Tagging Database Schema

## Overview
Denormalized PostgreSQL schema for storing audio processing jobs and song metadata. Designed for Modal + Neon integration with fast queries and minimal JOINs.

## Connection String
```bash
postgresql://neondb_owner:npg_tHmS1qpg0rbo@ep-wild-cloud-a419ahu0-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

## Schema

### Jobs Table
Tracks Modal processing status and job metadata.

```sql
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    modal_job_id TEXT UNIQUE,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    processing_time_seconds FLOAT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);
```

### Songs Table
Denormalized storage for all song data and metadata.

```sql
CREATE TABLE songs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    
    -- File metadata
    file_path TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    file_hash TEXT UNIQUE,
    file_size_bytes BIGINT,
    duration_seconds FLOAT,
    
    -- Artist/Track info
    artist TEXT,
    title TEXT,
    album TEXT,
    year TEXT,
    
    -- Audio features (from librosa)
    bpm FLOAT,
    bpm_range TEXT,
    key TEXT,
    camelot_key TEXT,
    mix_key TEXT,
    spectral_centroid_mean FLOAT,
    energy_mean FLOAT,
    energy_std FLOAT,
    dynamic_range FLOAT,
    onset_rate FLOAT,
    harmonic_ratio FLOAT,
    beat_strength FLOAT,
    tempo_stability FLOAT,
    low_freq_energy FLOAT,
    mid_freq_energy FLOAT,
    high_freq_energy FLOAT,
    
    -- AI-generated tags (denormalized)
    energy_level TEXT CHECK (energy_level IN ('low', 'medium', 'high', 'peak', 'dynamic')),
    mood_1 TEXT,  -- Primary mood (from 20-mood system)
    mood_2 TEXT,  -- Secondary mood  
    mood_3 TEXT,  -- Tertiary mood
    genre_1 TEXT,  -- Primary genre
    genre_2 TEXT,  -- Secondary genre
    genre_3 TEXT,  -- Tertiary genre
    set_position TEXT,
    bassline_type TEXT,
    vocal_type TEXT,
    vocal_gender TEXT,
    language TEXT,
    danceability INTEGER CHECK (danceability >= 0 AND danceability <= 10),
    
    -- Denormalized arrays as JSONB
    instruments JSONB,  -- ["kick_drum", "hi_hats", "synths"]
    moods JSONB,  -- ["dark", "intense", "driving"] 
    genres JSONB,  -- ["techno", "minimal", "detroit"]
    
    -- Full comment field
    comment TEXT,
    
    -- Metadata
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_model TEXT DEFAULT 'gpt-5-nano-2025-08-07',
    
    -- Full-text search vector
    tsv_search tsvector GENERATED ALWAYS AS (
        to_tsvector('english', 
            coalesce(artist, '') || ' ' || 
            coalesce(title, '') || ' ' || 
            coalesce(comment, '')
        )
    ) STORED
);
```

### Indexes

```sql
-- Jobs table indexes
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_modal_id ON jobs(modal_job_id);

-- Songs table indexes for common queries
CREATE INDEX idx_songs_bpm ON songs(bpm);
CREATE INDEX idx_songs_key ON songs(key);
CREATE INDEX idx_songs_energy ON songs(energy_level);
CREATE INDEX idx_songs_mood1 ON songs(mood_1);
CREATE INDEX idx_songs_genre1 ON songs(genre_1);
CREATE INDEX idx_songs_artist ON songs(artist);

-- Full-text search
CREATE INDEX idx_songs_search ON songs USING GIN(tsv_search);

-- JSONB indexes for array queries
CREATE INDEX idx_songs_moods_gin ON songs USING GIN(moods);
CREATE INDEX idx_songs_genres_gin ON songs USING GIN(genres);
CREATE INDEX idx_songs_instruments_gin ON songs USING GIN(instruments);
```

## Sample Queries

### Basic Filtering
```sql
-- Find high-energy techno tracks
SELECT artist, title, bpm, energy_level 
FROM songs 
WHERE genre_1 = 'techno' AND energy_level = 'high';

-- Find tracks by BPM range
SELECT artist, title, bpm 
FROM songs 
WHERE bpm BETWEEN 120 AND 130;

-- Find dark, intense tracks
SELECT artist, title, mood_1, mood_2, mood_3
FROM songs 
WHERE mood_1 = 'dark' OR mood_2 = 'dark' OR mood_3 = 'dark';
```

### JSONB Array Queries
```sql
-- Find songs with specific moods (using JSONB)
SELECT artist, title, moods
FROM songs 
WHERE moods @> '"dark"' AND moods @> '"intense"';

-- Find songs with piano
SELECT artist, title, instruments
FROM songs 
WHERE instruments @> '"piano"';

-- Find tracks that fit multiple genres
SELECT artist, title, genres
FROM songs 
WHERE genres @> '"house"' OR genres @> '"deep_house"';
```

### Full-Text Search
```sql
-- Search across artist, title, and comment
SELECT artist, title, comment
FROM songs 
WHERE tsv_search @@ to_tsquery('english', 'dark & electronic');
```

### DJ Set Building
```sql
-- Find opener tracks in key of A minor
SELECT artist, title, bpm, key, energy_level
FROM songs 
WHERE set_position = 'opener' 
  AND key = 'Am' 
  AND energy_level IN ('low', 'medium')
ORDER BY bpm;

-- Find tracks for harmonic mixing (Camelot wheel)
SELECT artist, title, bpm, camelot_key
FROM songs 
WHERE camelot_key IN ('8A', '9A', '7A')  -- Compatible keys
  AND bpm BETWEEN 126 AND 132
ORDER BY bpm;
```

### Analytics
```sql
-- Most common moods
SELECT mood_1, COUNT(*) as count
FROM songs 
WHERE mood_1 IS NOT NULL
GROUP BY mood_1 
ORDER BY count DESC;

-- Genre distribution
SELECT genre_1, COUNT(*) as count
FROM songs 
GROUP BY genre_1 
ORDER BY count DESC;

-- BPM distribution
SELECT 
  CASE 
    WHEN bpm < 100 THEN '< 100'
    WHEN bpm < 120 THEN '100-120'
    WHEN bpm < 130 THEN '120-130'
    WHEN bpm < 140 THEN '130-140'
    ELSE '140+'
  END as bpm_range,
  COUNT(*) as count
FROM songs 
GROUP BY 1 
ORDER BY 1;
```

## Modal Integration Code

### Setting up Modal Secret
```bash
modal secret create neon-db-url DATABASE_URL="postgresql://neondb_owner:npg_tHmS1qpg0rbo@ep-wild-cloud-a419ahu0-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

### Processing Function Template
```python
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
import hashlib

@app.function(
    secrets=[modal.Secret.from_name("neon-db-url")]
)
def process_audio_file(file_path: str, file_data: bytes) -> dict:
    # Connect to Neon
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # 1. Create job record
        file_hash = hashlib.md5(file_data).hexdigest()
        cur.execute("""
            INSERT INTO jobs (modal_job_id, file_path, file_name, file_hash, status)
            VALUES (%s, %s, %s, %s, 'processing')
            RETURNING id
        """, (
            modal.current_function_call_id(), 
            file_path, 
            os.path.basename(file_path),
            file_hash
        ))
        job_id = cur.fetchone()['id']
        conn.commit()
        
        # 2. Check if song already exists
        cur.execute("SELECT id FROM songs WHERE file_hash = %s", (file_hash,))
        if cur.fetchone():
            cur.execute("UPDATE jobs SET status = 'completed' WHERE id = %s", (job_id,))
            conn.commit()
            return {"status": "already_processed", "job_id": job_id}
        
        # 3. Process audio file
        # ... (audio processing code)
        
        # 4. Insert song data (single INSERT with all fields)
        cur.execute("""
            INSERT INTO songs (
                job_id, file_path, file_name, file_hash, file_size_bytes,
                artist, title, bpm, bpm_range, key, camelot_key,
                energy_level, mood_1, mood_2, mood_3,
                genre_1, genre_2, genre_3,
                moods, genres, instruments,
                set_position, bassline_type, vocal_type, danceability,
                comment, processing_model
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
        """, (
            # ... all the values
        ))
        
        # 5. Mark job complete
        cur.execute("""
            UPDATE jobs 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP,
                processing_time_seconds = %s
            WHERE id = %s
        """, (processing_time, job_id))
        
        conn.commit()
        return {"status": "success", "job_id": job_id}
        
    except Exception as e:
        # Mark job as failed
        cur.execute("""
            UPDATE jobs 
            SET status = 'failed', 
                error_message = %s,
                completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (str(e), job_id))
        conn.commit()
        raise e
        
    finally:
        cur.close()
        conn.close()
```

## Benefits

1. **Fast Queries**: Denormalized design eliminates JOINs for common queries
2. **Flexible Search**: JSONB arrays + GIN indexes for complex filtering
3. **Full-Text Search**: Built-in PostgreSQL search across artist/title/comment
4. **Deduplication**: Automatic via file_hash uniqueness constraint
5. **Job Tracking**: Clean separation of processing status vs. music data
6. **Scalability**: Neon handles connection pooling and scaling automatically

## 20-Mood System Values

Valid values for mood fields:
- euphoric, melancholic, uplifting, romantic, dark, dreamy
- groovy, hypnotic, driving, smooth, raw, playful  
- intense, peaceful, epic, sensual
- nostalgic, cerebral, spiritual, rebellious