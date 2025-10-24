"""DSPy module for intelligent tag inference - Version 3 with proper Pydantic structured outputs."""

import os

# DSPy initializes a disk-backed cache on import; ensure it points to a writable location.
_CACHE_DIR = os.environ.setdefault("DSPY_CACHEDIR", "/tmp/dspy_cache")
os.environ.setdefault("DISKCACHE_DEFAULT_DIRECTORY", _CACHE_DIR)
os.environ.setdefault("CACHE_DIR", _CACHE_DIR)
os.makedirs(_CACHE_DIR, exist_ok=True)

import dspy
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from .tag_definitions import validate_tags, format_comment_field, MOOD_OPTIONS, ENERGY_LEVELS
from .audio_analyzer import get_camelot_key


class MoodEnum(str, Enum):
    """Enum for the 20 finalized mood options."""
    euphoric = "euphoric"
    melancholic = "melancholic"
    uplifting = "uplifting"
    romantic = "romantic"
    dark = "dark"
    dreamy = "dreamy"
    groovy = "groovy"
    hypnotic = "hypnotic"
    sensual = "sensual"
    smooth = "smooth"
    raw = "raw"
    driving = "driving"
    playful = "playful"
    intense = "intense"
    nostalgic = "nostalgic"
    cerebral = "cerebral"
    epic = "epic"
    peaceful = "peaceful"
    spiritual = "spiritual"
    rebellious = "rebellious"


class EnergyEnum(str, Enum):
    """Enum for the 5 energy levels."""
    low = "low"
    medium = "medium"
    high = "high"
    peak = "peak"
    dynamic = "dynamic"


class DJTags(BaseModel):
    """Pydantic model for structured DJ tag output with enforced enums."""
    top_genres: List[str] = Field(description="Top 3 most likely genres, ordered by confidence (e.g. ['Hip-Hop', 'Trap', 'Southern Hip-Hop'])", min_items=1, max_items=3)
    energy: EnergyEnum = Field(description="Energy level: low, medium, high, peak, or dynamic")
    mood: List[MoodEnum] = Field(
        description="2-3 moods from: euphoric, melancholic, uplifting, romantic, dark, dreamy, groovy, hypnotic, sensual, smooth, raw, driving, playful, intense, nostalgic, cerebral, epic, peaceful, spiritual, rebellious",
        min_items=1, 
        max_items=3
    )
    artist: Optional[str] = Field(default=None, description="Identified performing artist name.")
    title: Optional[str] = Field(default=None, description="Identified track title.")
    set_position: str = Field(description="DJ set position: opener/warm_up/build/peak/breakdown/closer")
    bassline_type: str = Field(description="Type of bassline")
    vocal_type: str = Field(description="Type of vocals")
    prominent_instruments: List[str] = Field(description="2-4 prominent instruments")
    danceability: int = Field(description="Danceability score 0-10", ge=0, le=10)


class TrackTaggerSignature(dspy.Signature):
    """Analyze audio features to generate comprehensive DJ-focused tags."""
    
    audio_features: str = dspy.InputField(
        desc="Audio analysis including BPM, key, spectral features, energy levels"
    )
    artist: str = dspy.InputField(
        desc="Artist name"
    )
    song_title: str = dspy.InputField(
        desc="Song title"
    )
    filename: str = dspy.InputField(
        desc="Original filename for additional context"
    )
    existing_tags: str = dspy.InputField(
        desc="Any existing ID3 tags from the file"
    )
    
    tags: DJTags = dspy.OutputField(
        desc="Generate comprehensive DJ tags based on audio analysis and artist/song context"
    )


class TrackTagger(dspy.Module):
    def __init__(self):
        super().__init__()
        self.tagger = dspy.Predict(TrackTaggerSignature)
        
    def __call__(self, audio_features: Dict[str, Any], filename: str, existing_tags: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate comprehensive tags from audio features.
        
        Args:
            audio_features: Dictionary of extracted audio features
            filename: Name of the audio file
            existing_tags: Existing ID3 tags (if any)
        
        Returns:
            Dictionary of enhanced tags
        """
        if existing_tags is None:
            existing_tags = {}
        
        # Format features for LLM
        features_str = self._format_features(audio_features)
        # Extract artist and song title from existing tags if available
        artist, song_title = self._extract_artist_title(existing_tags)
        existing_tags_str = self._format_metadata_context(
            filename=filename,
            artist=artist,
            song_title=song_title,
            existing_tags=existing_tags,
        )
        print(f"  [DEBUG] Extracted artist: '{artist}', song: '{song_title}'")
        
        # Run DSPy inference
        print(f"    - Calling DSPy with {len(features_str)} char context...")
        api_start = time.time()
        result = self.tagger(
            audio_features=features_str,
            artist=artist,
            song_title=song_title,
            filename=filename,
            existing_tags=existing_tags_str
        )
        api_time = time.time() - api_start
        print(f"    - DSPy API call completed in {api_time:.2f}s")
        
        # Convert Pydantic model to dict
        generated_tags = result.tags.model_dump()

        # Preserve existing artist/title tags if the model did not supply them
        if artist and not generated_tags.get("artist"):
            generated_tags["artist"] = artist
        if song_title and not generated_tags.get("title"):
            generated_tags["title"] = song_title
        
        # Convert to backward-compatible format
        if 'top_genres' in generated_tags and generated_tags['top_genres']:
            generated_tags['genre'] = generated_tags['top_genres'][0]  # Primary genre
            generated_tags['genre_alternatives'] = generated_tags['top_genres'][1:] if len(generated_tags['top_genres']) > 1 else []
        
        # Convert energy enum to energy_level for backward compatibility
        if 'energy' in generated_tags:
            generated_tags['energy_level'] = generated_tags['energy']
        
        # Add audio-derived features
        tags = self._add_audio_features(generated_tags, audio_features, existing_tags)
        
        # Validate and clean tags
        tags = validate_tags(tags)
        
        # Generate comment field
        if 'comment' not in tags:
            tags['comment'] = format_comment_field(tags)
        
        return tags
    
    def _extract_artist_title(self, existing_tags: Dict[str, Any]) -> tuple[str, str]:
        """Extract artist and song title from existing tags only."""
        if not existing_tags:
            return "Unknown", "Unknown"

        artist = (existing_tags.get("artist") or "").strip()
        title = (existing_tags.get("title") or "").strip()

        return artist, title

    def _format_metadata_context(
        self,
        filename: str,
        artist: str,
        song_title: str,
        existing_tags: Dict[str, Any],
    ) -> str:
        """Summarize filename-derived metadata and existing ID3 tags for the LLM."""
        lines = [
            f"Filename: {filename}",
            f"Current artist tag: {artist or '<missing>'}",
            f"Current title tag: {song_title or '<missing>'}",
        ]

        if not artist or not song_title:
            lines.append(
                "Please infer accurate artist and title names from the audio and filename if they are missing."
            )

        if not existing_tags:
            lines.append("Existing ID3 tags: none detected.")
            return "\n".join(lines)

        lines.append("Existing ID3 tags:")
        key_order = [
            "artist",
            "title",
            "album",
            "year",
            "genre",
            "comment",
            "bpm",
            "key",
        ]

        def _trim(value: Any) -> str:
            text = str(value)
            if len(text) > 240:
                return text[:237] + "..."
            return text

        seen_keys = set()
        for key in key_order:
            if key in existing_tags and existing_tags[key]:
                lines.append(f"  - {key}: {_trim(existing_tags[key])}")
                seen_keys.add(key)

        # Include any additional custom tags for completeness
        extra_keys = sorted(k for k in existing_tags.keys() if k not in seen_keys)
        for key in extra_keys:
            value = existing_tags[key]
            if value:
                lines.append(f"  - {key}: {_trim(value)}")

        return "\n".join(lines)
    
    def _format_features(self, features: Dict[str, Any]) -> str:
        """Format audio features for LLM processing."""
        return f"""
Audio Analysis:
- BPM: {features.get('bpm', 0):.1f} (Range: {features.get('bpm_range', 'unknown')})
- Key: {features.get('key', 'unknown')}
- Energy: mean={features.get('energy_mean', 0):.3f}, std={features.get('energy_std', 0):.3f}
- Spectral Centroid: {features.get('spectral_centroid_mean', 0):.0f} Hz (brightness)
- Harmonic/Percussive Ratio: {features.get('harmonic_ratio', 0.5):.2f} (0=percussive, 1=harmonic)
- Onset Rate: {features.get('onset_rate', 0):.2f} per second
- Tempo Stability: {features.get('tempo_stability', 0):.2f} (0=variable, 1=stable)
- Duration: {features.get('duration_minutes', 0):.1f} minutes

Frequency Distribution:
- Low (Bass): {features.get('low_freq_energy', 0.33):.2%}
- Mid: {features.get('mid_freq_energy', 0.33):.2%}  
- High (Treble): {features.get('high_freq_energy', 0.33):.2%}

Dynamic Range: {features.get('dynamic_range', 0):.3f}
Beat Strength: {features.get('beat_strength', 0):.3f}
"""
    
    def _add_audio_features(self, tags: Dict[str, Any], audio_features: Dict[str, Any], existing_tags: Dict[str, Any]) -> Dict[str, Any]:
        """Add audio-derived features to tags."""
        # Add BPM info
        tags['bpm'] = audio_features.get('bpm', 120)
        tags['bpm_range'] = audio_features.get('bpm_range', '120')
        
        # Key information
        if 'key' not in tags or not tags['key']:
            tags['key'] = audio_features.get('key', 'C')
        
        # Generate Camelot key
        if 'camelot_key' not in tags:
            # Determine mode based on mood/genre
            mode = 'minor' if any(m in str(tags.get('mood', [])) for m in ['dark', 'melancholic', 'mysterious']) else 'major'
            tags['camelot_key'] = get_camelot_key(tags['key'], mode)
        
        # Mix key (same as Camelot)
        if 'mix_key' not in tags:
            tags['mix_key'] = tags.get('camelot_key', '8B')
        
        # Note: existing_tags is now always empty for fresh generation
        # Artist/title extraction happens from filename instead
        
        return tags


def create_tagger(model: str = "gpt-5-nano-2025-08-07") -> TrackTagger:
    """
    Create and configure a TrackTagger instance.
    
    Args:
        model: LLM model to use
    
    Returns:
        Configured TrackTagger instance
    """
    import time
    start = time.time()
    
    # Format the model name for DSPy 3.x
    if not model.startswith('openai/'):
        model = f'openai/{model}'
    
    # Special configuration for gpt-5-nano reasoning model
    if 'gpt-5' in model:
        lm = dspy.LM(model, temperature=1.0, max_tokens=16000)
    else:
        lm = dspy.LM(model, temperature=0.7, max_tokens=4000)
    
    config_time = time.time() - start
    print(f"    - LM configuration took {config_time:.2f}s")
    
    start = time.time()
    dspy.configure(lm=lm)
    configure_time = time.time() - start
    print(f"    - dspy.configure took {configure_time:.2f}s")
    
    return TrackTagger()
