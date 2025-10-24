"""Tag definitions and schemas for ID3 tagging."""

from typing import List, Dict, Any


# Venue/location options
WHERE_OPTIONS = [
    "bedroom",
    "lounge", 
    "club",
    "festival",
    "warehouse",
    "beach",
    "rooftop",
    "gym",
    "car",
    "house_party"
]

# Time/occasion options
WHEN_OPTIONS = [
    "early_morning",
    "morning",
    "afternoon", 
    "daytime_rave",
    "sunset",
    "evening",
    "prime_time",
    "peak_hours",
    "after_hours",
    "late_night",
    "sunrise"
]

# Mood/feeling options - Finalized 20 moods
MOOD_OPTIONS = [
    "euphoric",
    "melancholic",
    "uplifting",
    "romantic",
    "dark",
    "dreamy",
    "groovy",
    "hypnotic",
    "sensual",
    "smooth",
    "raw",
    "driving",
    "playful",
    "intense",
    "nostalgic",
    "cerebral",
    "epic",
    "peaceful",
    "spiritual",
    "rebellious"
]

# Set position options
SET_POSITION_OPTIONS = [
    "opener",
    "warmup",
    "build",
    "peak",
    "sustain",
    "breakdown",
    "release",
    "closer"
]

# Bassline type options
BASSLINE_OPTIONS = [
    "walking",
    "grindy", 
    "booming",
    "sub",
    "rolling",
    "acid",
    "deep",
    "minimal",
    "dubby",
    "wobbly",
    "punchy",
    "none"
]

# Vocal type options
VOCAL_OPTIONS = [
    "none",
    "spoken_word",
    "chanting",
    "singing",
    "rap",
    "acapella",
    "vocoder",
    "chopped",
    "soulful",
    "opera",
    "whisper"
]

# Instrument options
INSTRUMENT_OPTIONS = [
    "kick_drum",
    "hi_hats",
    "snare",
    "claps",
    "congas",
    "percussion",
    "piano",
    "organ",
    "strings",
    "pads",
    "synths",
    "guitar",
    "bass_guitar",
    "saxophone",
    "trumpet",
    "horns",
    "flute",
    "violin",
    "sweeps",
    "risers"
]

# Genre options (can be expanded)
GENRE_OPTIONS = [
    "house",
    "deep_house",
    "tech_house",
    "progressive_house",
    "techno",
    "minimal_techno",
    "acid_techno",
    "trance",
    "drum_and_bass",
    "dubstep",
    "hip_hop",
    "trap",
    "ambient",
    "downtempo",
    "disco",
    "funk",
    "soul",
    "jazz",
    "classical",
    "experimental",
    "breakbeat",
    "garage",
    "grime",
    "reggae",
    "dub",
    "latin",
    "afrobeat"
]

# Energy level options - Finalized 5 levels
ENERGY_LEVELS = ["low", "medium", "high", "peak", "dynamic"]


def get_tag_schema() -> Dict[str, Any]:
    """
    Get the complete tag schema with all field definitions.
    
    Returns:
        Dictionary defining all tag fields and their types
    """
    return {
        # Technical (from audio analysis)
        "bpm": float,
        "bpm_range": str,  # "120", "130", etc.
        "key": str,
        "mix_key": str,  # Open key notation
        "camelot_key": str,  # Camelot wheel notation
        
        # Classification
        "genre": str,
        "subgenre": str,
        "year": str,
        "era": str,  # "90s", "2000s", etc.
        
        # Mood (enforced with 20 moods)
        "mood": List[str],  # 2-3 moods from finalized 20 options
        "feelings": List[str],  # Alias for mood
        
        # Musical characteristics
        "prominent_instruments": List[str],
        "bassline_type": str,
        "vocal_type": str,
        "vocal_gender": str,
        "language": str,
        
        # DJ-specific
        "set_position": str,
        "energy_level": str,
        "tempo_stability": str,  # "stable", "variable"
        
        # Extended metadata
        "comment": str,  # Full vibes description
        "color_code": str,  # For visual organization
        "rating": int,  # 1-5 stars
    }


def format_comment_field(tags: Dict[str, Any]) -> str:
    """
    Format tags into a comprehensive comment field.
    
    Args:
        tags: Dictionary of extracted tags
    
    Returns:
        Formatted comment string
    """
    parts = []
    
    # Multi-genre section
    genre_parts = []
    if tags.get('genre'):
        genre_parts.append(tags['genre'])
    if tags.get('genre_alternatives'):
        # Add up to 2 alternative genres
        alts = tags['genre_alternatives'][:2] if isinstance(tags['genre_alternatives'], list) else [tags['genre_alternatives']]
        genre_parts.extend(alts)
    if genre_parts:
        parts.append(f"Genres: {' / '.join(genre_parts)}")
    
    # Vibes/mood section
    if tags.get('mood'):
        moods = tags['mood'] if isinstance(tags['mood'], list) else [tags['mood']]
        parts.append(f"Vibes: {', '.join(moods)}")
    
    # Instruments section
    if tags.get('prominent_instruments'):
        instruments = tags['prominent_instruments']
        if isinstance(instruments, list):
            parts.append(f"Instruments: {', '.join(instruments)}")
    
    # Bassline
    if tags.get('bassline_type') and tags['bassline_type'] != 'none':
        parts.append(f"Bassline: {tags['bassline_type']}")
    
    # Vocals
    if tags.get('vocal_type') and tags['vocal_type'] != 'none':
        parts.append(f"Vocals: {tags['vocal_type']}")
    
    # Energy level
    if tags.get('energy_level') or tags.get('energy'):
        energy = tags.get('energy_level') or tags.get('energy')
        parts.append(f"Energy: {energy}")
    
    # DJ position
    if tags.get('set_position'):
        parts.append(f"DJ Position: {tags['set_position']}")
    
    return " | ".join(parts)



def validate_tags(tags: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean extracted tags.
    
    Args:
        tags: Raw extracted tags
    
    Returns:
        Validated and cleaned tags
    """
    validated = {}
    
    # Ensure lists are lists
    list_fields = ['mood', 'feelings', 'prominent_instruments']
    for field in list_fields:
        if field in tags:
            value = tags[field]
            if isinstance(value, str):
                # Split comma-separated strings
                validated[field] = [v.strip() for v in value.split(',')]
            elif isinstance(value, list):
                validated[field] = value
            else:
                validated[field] = [str(value)]
    
    # Copy string fields
    string_fields = ['artist', 'title', 'bpm_range', 'key', 'mix_key', 'camelot_key', 'genre', 
                    'subgenre', 'year', 'era', 'bassline_type', 'vocal_type',
                    'vocal_gender', 'language', 'set_position', 'energy_level',
                    'tempo_stability', 'color_code']
    for field in string_fields:
        if field in tags:
            value = tags[field]
            if value not in (None, ''):
                validated[field] = str(value)
    
    # Handle genre alternatives (list field)
    if 'genre_alternatives' in tags:
        value = tags['genre_alternatives']
        if isinstance(value, str):
            validated['genre_alternatives'] = [v.strip() for v in value.split(',')]
        elif isinstance(value, list):
            validated['genre_alternatives'] = value
        else:
            validated['genre_alternatives'] = [str(value)]
    
    # Copy numeric fields
    if 'bpm' in tags:
        validated['bpm'] = float(tags['bpm'])
    if 'rating' in tags:
        validated['rating'] = int(tags['rating'])
    
    # Generate comment field if not present
    if 'comment' not in tags:
        validated['comment'] = format_comment_field(validated)
    else:
        validated['comment'] = tags['comment']
    
    return validated
