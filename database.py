#!/usr/bin/env python3
"""
Database utilities using SQLAlchemy ORM for the DJ Audio Tagger project.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, 
    DateTime, ForeignKey, BigInteger, CheckConstraint, Index,
    text, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()


class Job(Base):
    __tablename__ = 'jobs'
    
    id = Column(Integer, primary_key=True)
    modal_job_id = Column(Text, unique=True)
    file_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_hash = Column(Text)
    status = Column(String, default='pending')
    submitted_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    processing_time_seconds = Column(Float)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Relationship
    songs = relationship("Song", back_populates="job")
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')"),
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_modal_id', 'modal_job_id'),
    )


class Song(Base):
    __tablename__ = 'songs'
    
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey('jobs.id'))
    file_path = Column(Text, nullable=False)
    file_name = Column(Text, nullable=False)
    file_hash = Column(Text, unique=True)
    file_size_bytes = Column(BigInteger)
    duration_seconds = Column(Float)
    artist = Column(Text)
    title = Column(Text)
    album = Column(Text)
    year = Column(Text)
    bpm = Column(Float)
    bpm_range = Column(Text)
    key = Column(Text)
    camelot_key = Column(Text)
    mix_key = Column(Text)
    spectral_centroid_mean = Column(Float)
    energy_mean = Column(Float)
    energy_std = Column(Float)
    dynamic_range = Column(Float)
    onset_rate = Column(Float)
    harmonic_ratio = Column(Float)
    beat_strength = Column(Float)
    tempo_stability = Column(Float)
    low_freq_energy = Column(Float)
    mid_freq_energy = Column(Float)
    high_freq_energy = Column(Float)
    energy_level = Column(String)
    mood_1 = Column(Text)
    mood_2 = Column(Text)
    mood_3 = Column(Text)
    genre_1 = Column(Text)
    genre_2 = Column(Text)
    genre_3 = Column(Text)
    set_position = Column(Text)
    bassline_type = Column(Text)
    vocal_type = Column(Text)
    vocal_gender = Column(Text)
    language = Column(Text)
    danceability = Column(Integer)
    instruments = Column(JSONB)
    moods = Column(JSONB)
    genres = Column(JSONB)
    comment = Column(Text)
    processed_at = Column(DateTime, default=datetime.utcnow)
    processing_model = Column(Text, default='gpt-5-nano-2025-08-07')
    
    # Relationship
    job = relationship("Job", back_populates="songs")
    
    __table_args__ = (
        CheckConstraint("energy_level IN ('low', 'medium', 'high', 'peak', 'dynamic')"),
        CheckConstraint("danceability >= 0 AND danceability <= 10"),
        Index('idx_songs_bpm', 'bpm'),
        Index('idx_songs_key', 'key'),
        Index('idx_songs_energy', 'energy_level'),
        Index('idx_songs_moods_gin', 'moods', postgresql_using='gin'),
        Index('idx_songs_genres_gin', 'genres', postgresql_using='gin'),
    )


class Database:
    """Database connection and utility class using SQLAlchemy ORM."""
    
    def __init__(self, database_url: str = None):
        """Initialize database connection and create tables."""
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable required")
        
        self.engine = create_engine(self.database_url)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions."""
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    def create_job(self, modal_job_id: str, file_path: str, file_hash: str) -> int:
        """Create a new job record and return job_id."""
        file_name = os.path.basename(file_path)
        with self.get_session() as session:
            job = session.query(Job).filter_by(modal_job_id=modal_job_id).first()
            if job:
                job.status = 'processing'
            else:
                job = Job(
                    modal_job_id=modal_job_id,
                    file_path=file_path,
                    file_name=file_name,
                    file_hash=file_hash,
                    status='processing'
                )
                session.add(job)
            session.commit()
            return job.id
    
    def update_job_status(self, job_id: int, status: str, error_message: str = None, 
                         processing_time: float = None):
        """Update job status."""
        with self.get_session() as session:
            job = session.query(Job).filter_by(id=job_id).first()
            if job:
                job.status = status
                if status == 'completed':
                    job.completed_at = datetime.utcnow()
                    job.processing_time_seconds = processing_time
                elif status == 'failed':
                    job.error_message = error_message
                    job.completed_at = datetime.utcnow()
                    job.processing_time_seconds = processing_time
                session.commit()
    
    def song_exists(self, file_hash: str) -> Optional[int]:
        """Check if song already exists by file hash. Returns song_id if exists."""
        with self.get_session() as session:
            song = session.query(Song).filter_by(file_hash=file_hash).first()
            return song.id if song else None
    
    def create_song(self, job_id: int, file_path: str, file_hash: str, file_size: int, 
                   audio_features: Dict, tags: Dict) -> int:
        """Create a new song record with all metadata using SQLAlchemy ORM."""
        print(f"🔵 create_song called with job_id={job_id}, file_path={file_path}")
        
        file_name = os.path.basename(file_path)
        artist = tags.get('artist', 'Unknown')
        title = tags.get('title', file_name.rsplit('.', 1)[0])
        
        print(f"🔵 Basic song info: artist={artist}, title={title}")
        
        # Process moods
        def _coerce_enum(value):
            """Convert Enum-like values (including stringified enums) into plain strings."""
            if value is None:
                return None
            if hasattr(value, "value"):
                return str(value.value)
            if isinstance(value, str) and "." in value:
                prefix, _, suffix = value.partition(".")
                if suffix:
                    # Handles cases like EnergyEnum.low / MoodEnum.groovy
                    return suffix
            return str(value)

        moods = tags.get('mood', [])
        if isinstance(moods, str):
            moods = [moods]
        moods = [ _coerce_enum(mood) for mood in moods if mood ]
        print(f"🔵 Processed moods: {moods}")
        
        # Process genres
        genres = []
        if tags.get('genre'):
            genres.append(tags['genre'])
        if tags.get('genre_alternatives'):
            genres.extend(tags['genre_alternatives'])
        genres = [g for g in genres if g]
        print(f"🔵 Processed genres: {genres}")
        
        # Process instruments
        instruments = tags.get('prominent_instruments', [])
        if isinstance(instruments, str):
            instruments = [instruments]
        print(f"🔵 Processed instruments: {instruments}")
        
        # Process energy level
        energy_level = tags.get('energy_level')
        processed_energy = _coerce_enum(energy_level) if energy_level else None
        print(f"🔵 Energy level: {energy_level} -> {processed_energy}")
        print(f"🔵 Energy level type: {type(energy_level)}")
        
        print(f"🔵 Creating SQLAlchemy session...")
        with self.get_session() as session:
            print(f"🔵 Session created successfully")
            try:
                print(f"🔵 Creating Song object...")
                song = Song(
                    job_id=job_id,
                    file_path=file_path,
                    file_name=file_name,
                    file_hash=file_hash,
                    file_size_bytes=file_size,
                    artist=artist,
                    title=title,
                    duration_seconds=audio_features.get('duration_minutes', 0) * 60,
                    bpm=audio_features.get('bpm'),
                    bpm_range=audio_features.get('bpm_range'),
                    key=audio_features.get('key'),
                    camelot_key=tags.get('camelot_key'),
                    mix_key=tags.get('mix_key'),
                    spectral_centroid_mean=audio_features.get('spectral_centroid_mean'),
                    energy_mean=audio_features.get('energy_mean'),
                    energy_std=audio_features.get('energy_std'),
                    dynamic_range=audio_features.get('dynamic_range'),
                    onset_rate=audio_features.get('onset_rate'),
                    harmonic_ratio=audio_features.get('harmonic_ratio'),
                    beat_strength=audio_features.get('beat_strength'),
                    tempo_stability=audio_features.get('tempo_stability'),
                    low_freq_energy=audio_features.get('low_freq_energy'),
                    mid_freq_energy=audio_features.get('mid_freq_energy'),
                    high_freq_energy=audio_features.get('high_freq_energy'),
                    energy_level=processed_energy,
                    mood_1=moods[0] if len(moods) > 0 else None,
                    mood_2=moods[1] if len(moods) > 1 else None,
                    mood_3=moods[2] if len(moods) > 2 else None,
                    genre_1=genres[0] if len(genres) > 0 else None,
                    genre_2=genres[1] if len(genres) > 1 else None,
                    genre_3=genres[2] if len(genres) > 2 else None,
                    set_position=tags.get('set_position'),
                    bassline_type=tags.get('bassline_type'),
                    vocal_type=tags.get('vocal_type'),
                    vocal_gender=tags.get('vocal_gender'),
                    language=tags.get('language'),
                    danceability=tags.get('danceability'),
                    moods=moods,
                    genres=genres,
                    instruments=instruments,
                    comment=tags.get('comment'),
                    processing_model="gpt-5-nano-2025-08-07"
                )
                print(f"🔵 Song object created successfully")
                
                print(f"🔵 Adding song to session...")
                session.add(song)
                print(f"🔵 Song added to session, committing...")
                session.commit()
                print(f"🔵 Session committed successfully, song.id={song.id}")
                return song.id
            except Exception as e:
                print(f"🔴 Error in create_song: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
    
    def get_job_stats(self) -> Dict[str, Any]:
        """Get job processing statistics using SQLAlchemy."""
        with self.get_session() as session:
            # Job statistics
            job_stats = session.query(
                Job.status,
                func.count(Job.id).label('count'),
                func.avg(Job.processing_time_seconds).label('avg_time'),
                func.max(Job.completed_at).label('latest_completion')
            ).group_by(Job.status).order_by(Job.status).all()
            
            job_stats_dict = [
                {
                    'status': stat.status,
                    'count': stat.count,
                    'avg_time': float(stat.avg_time) if stat.avg_time else None,
                    'latest_completion': stat.latest_completion.isoformat() if stat.latest_completion else None
                }
                for stat in job_stats
            ]
            
            # Song statistics
            total_songs = session.query(func.count(Song.id)).scalar()
            
            return {
                "job_statistics": job_stats_dict,
                "total_songs": total_songs
            }
    
    def search_songs(self, artist: str = None, genre: str = None, mood: str = None,
                    energy: str = None, bpm_min: float = None, bpm_max: float = None,
                    key: str = None, limit: int = 50) -> List[Dict]:
        """Search songs with filters using SQLAlchemy."""
        from sqlalchemy import or_, and_
        
        with self.get_session() as session:
            query = session.query(Song)
            
            if artist:
                query = query.filter(Song.artist.ilike(f"%{artist}%"))
            
            if genre:
                query = query.filter(
                    or_(
                        Song.genre_1.ilike(f"%{genre}%"),
                        Song.genres.contains([genre])
                    )
                )
            
            if mood:
                query = query.filter(
                    or_(
                        Song.mood_1 == mood,
                        Song.mood_2 == mood,
                        Song.mood_3 == mood,
                        Song.moods.contains([mood])
                    )
                )
            
            if energy:
                query = query.filter(Song.energy_level == energy)
            
            if bpm_min:
                query = query.filter(Song.bpm >= bpm_min)
            
            if bpm_max:
                query = query.filter(Song.bpm <= bpm_max)
            
            if key:
                query = query.filter(Song.key == key)
            
            results = query.order_by(Song.processed_at.desc()).limit(limit).all()
            
            return [
                {
                    'artist': song.artist,
                    'title': song.title,
                    'bpm': song.bpm,
                    'key': song.key,
                    'energy_level': song.energy_level,
                    'mood_1': song.mood_1,
                    'mood_2': song.mood_2,
                    'mood_3': song.mood_3,
                    'genre_1': song.genre_1,
                    'genre_2': song.genre_2,
                    'genre_3': song.genre_3,
                    'moods': song.moods,
                    'genres': song.genres,
                    'instruments': song.instruments,
                    'file_path': song.file_path,
                    'processed_at': song.processed_at.isoformat() if song.processed_at else None,
                    'danceability': song.danceability
                }
                for song in results
            ]


def main():
    """CLI interface for database operations."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python database.py <command>")
        print("Commands: setup, stats, search")
        sys.exit(1)
    
    command = sys.argv[1]
    db = Database()
    
    if command == "setup":
        print("Database schema created successfully")
    
    elif command == "stats":
        stats = db.get_job_stats()
        print(json.dumps(stats, indent=2, default=str))
    
    elif command == "search":
        # Interactive search
        artist = input("Artist (optional): ").strip() or None
        genre = input("Genre (optional): ").strip() or None
        energy = input("Energy level (optional): ").strip() or None
        
        results = db.search_songs(artist=artist, genre=genre, energy=energy, limit=10)
        print(f"\nFound {len(results)} songs:")
        for song in results:
            print(f"- {song['artist']} - {song['title']} ({song['energy_level']}, {song['bpm']} BPM)")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
