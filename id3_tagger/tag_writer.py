"""ID3 tag writing and reading using mutagen."""

import json
from typing import Dict, Any, Optional
from mutagen.mp3 import MP3
from mutagen.id3 import (
    ID3, TIT2, TPE1, TALB, TDRC, TCON, TBPM, TKEY, COMM, TXXX,
    ID3NoHeaderError, APIC
)
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen import File
import os


def read_existing_tags(audio_path: str) -> Dict[str, Any]:
    """
    Read existing ID3 tags from an audio file.
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Dictionary of existing tags
    """
    tags = {}
    
    try:
        audio_file = File(audio_path)
        if audio_file is None:
            return tags
        
        # Handle different file formats
        if isinstance(audio_file, MP3):
            if audio_file.tags:
                tags = _read_id3_tags(audio_file.tags)
        elif isinstance(audio_file, MP4):
            tags = _read_mp4_tags(audio_file)
        elif isinstance(audio_file, FLAC):
            tags = _read_flac_tags(audio_file)
        else:
            # Generic tag reading
            if hasattr(audio_file, 'tags') and audio_file.tags:
                for key, value in audio_file.tags.items():
                    if isinstance(value, list) and len(value) > 0:
                        tags[key] = str(value[0])
                    else:
                        tags[key] = str(value)
    except Exception as e:
        print(f"Error reading tags: {e}")
    
    return tags


def _read_id3_tags(id3_tags) -> Dict[str, Any]:
    """Read ID3 tags from MP3 file."""
    tags = {}
    
    # Standard tags
    if 'TIT2' in id3_tags:  # Title
        tags['title'] = str(id3_tags['TIT2'].text[0])
    if 'TPE1' in id3_tags:  # Artist
        tags['artist'] = str(id3_tags['TPE1'].text[0])
    if 'TALB' in id3_tags:  # Album
        tags['album'] = str(id3_tags['TALB'].text[0])
    if 'TDRC' in id3_tags:  # Year
        tags['year'] = str(id3_tags['TDRC'].text[0])
    if 'TCON' in id3_tags:  # Genre
        tags['genre'] = str(id3_tags['TCON'].text[0])
    if 'TBPM' in id3_tags:  # BPM
        tags['bpm'] = str(id3_tags['TBPM'].text[0])
    if 'TKEY' in id3_tags:  # Key
        tags['key'] = str(id3_tags['TKEY'].text[0])
    
    # Comments
    for frame in id3_tags.getall('COMM'):
        tags['comment'] = str(frame.text[0])
        break
    
    # Custom tags (TXXX frames)
    for frame in id3_tags.getall('TXXX'):
        desc = str(frame.desc)
        text = str(frame.text[0]) if frame.text else ''
        tags[desc.lower().replace(' ', '_')] = text
    
    return tags


def _read_mp4_tags(mp4_file) -> Dict[str, Any]:
    """Read tags from MP4/M4A file."""
    tags = {}
    tag_mapping = {
        '\xa9nam': 'title',
        '\xa9ART': 'artist',
        '\xa9alb': 'album',
        '\xa9day': 'year',
        '\xa9gen': 'genre',
        '\xa9cmt': 'comment',
        'tmpo': 'bpm',
    }
    
    for mp4_key, tag_key in tag_mapping.items():
        if mp4_key in mp4_file:
            value = mp4_file[mp4_key]
            if isinstance(value, list) and len(value) > 0:
                tags[tag_key] = str(value[0])
            else:
                tags[tag_key] = str(value)
    
    return tags


def _read_flac_tags(flac_file) -> Dict[str, Any]:
    """Read tags from FLAC file."""
    tags = {}
    tag_mapping = {
        'title': 'title',
        'artist': 'artist',
        'album': 'album',
        'date': 'year',
        'genre': 'genre',
        'comment': 'comment',
        'bpm': 'bpm',
    }
    
    for flac_key, tag_key in tag_mapping.items():
        if flac_key in flac_file:
            value = flac_file[flac_key]
            if isinstance(value, list) and len(value) > 0:
                tags[tag_key] = str(value[0])
            else:
                tags[tag_key] = str(value)
    
    return tags


def write_tags(audio_path: str, tags: Dict[str, Any]) -> bool:
    """
    Write tags to an audio file.
    
    Args:
        audio_path: Path to audio file
        tags: Dictionary of tags to write
    
    Returns:
        True if successful, False otherwise
    """
    try:
        file_ext = os.path.splitext(audio_path)[1].lower()
        
        if file_ext in ['.mp3']:
            return _write_mp3_tags(audio_path, tags)
        elif file_ext in ['.m4a', '.mp4']:
            return _write_mp4_tags(audio_path, tags)
        elif file_ext in ['.flac']:
            return _write_flac_tags(audio_path, tags)
        else:
            print(f"Unsupported file format: {file_ext}")
            return False
            
    except Exception as e:
        print(f"Error writing tags: {e}")
        return False


def _write_mp3_tags(audio_path: str, tags: Dict[str, Any]) -> bool:
    """Write ID3 tags to MP3 file."""
    try:
        # Try to load existing ID3 tags
        try:
            audio = MP3(audio_path)
        except ID3NoHeaderError:
            # Create new ID3 tags if none exist
            audio = MP3(audio_path)
            audio.add_tags()
        
        # Standard tags
        if 'title' in tags:
            audio.tags.add(TIT2(encoding=3, text=tags['title']))
        if 'artist' in tags:
            audio.tags.add(TPE1(encoding=3, text=tags['artist']))
        if 'album' in tags:
            audio.tags.add(TALB(encoding=3, text=tags['album']))
        if 'year' in tags:
            audio.tags.add(TDRC(encoding=3, text=str(tags['year'])))
        if 'genre' in tags:
            audio.tags.add(TCON(encoding=3, text=tags['genre']))
        if 'bpm' in tags:
            audio.tags.add(TBPM(encoding=3, text=str(tags['bpm'])))
        if 'key' in tags:
            audio.tags.add(TKEY(encoding=3, text=tags['key']))
        
        # Comment field
        if 'comment' in tags:
            audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=tags['comment']))
        
        # Custom tags as TXXX frames
        custom_fields = [
            'bpm_range', 'subgenre', 'mix_key', 'camelot_key', 'era',
            'where', 'when', 'mood', 'feelings', 'prominent_instruments',
            'bassline_type', 'vocal_type', 'vocal_gender', 'language',
            'set_position', 'energy_level', 'tempo_stability', 'color_code',
            'rating', 'genre_alternatives'
        ]
        
        for field in custom_fields:
            if field in tags:
                value = tags[field]
                # Convert lists to comma-separated strings
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                else:
                    value = str(value)
                audio.tags.add(TXXX(encoding=3, desc=field, text=value))
        
        audio.save()
        return True
        
    except Exception as e:
        print(f"Error writing MP3 tags: {e}")
        return False


def _write_mp4_tags(audio_path: str, tags: Dict[str, Any]) -> bool:
    """Write tags to MP4/M4A file."""
    try:
        audio = MP4(audio_path)
        
        # Standard MP4 atoms
        tag_mapping = {
            'title': '\xa9nam',
            'artist': '\xa9ART',
            'album': '\xa9alb',
            'year': '\xa9day',
            'genre': '\xa9gen',
            'comment': '\xa9cmt',
        }
        
        for tag_key, mp4_key in tag_mapping.items():
            if tag_key in tags:
                audio[mp4_key] = str(tags[tag_key])
        
        # BPM (special handling)
        if 'bpm' in tags:
            audio['tmpo'] = [int(float(tags['bpm']))]
        
        # Custom tags as freeform atoms
        custom_fields = [
            'bpm_range', 'subgenre', 'key', 'mix_key', 'camelot_key',
            'where', 'when', 'mood', 'prominent_instruments',
            'bassline_type', 'vocal_type', 'set_position', 'energy_level'
        ]
        
        for field in custom_fields:
            if field in tags:
                value = tags[field]
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                # Store as freeform text
                audio[f'----:com.apple.iTunes:{field}'] = str(value).encode('utf-8')
        
        audio.save()
        return True
        
    except Exception as e:
        print(f"Error writing MP4 tags: {e}")
        return False


def _write_flac_tags(audio_path: str, tags: Dict[str, Any]) -> bool:
    """Write tags to FLAC file."""
    try:
        audio = FLAC(audio_path)
        
        # Standard FLAC tags
        tag_mapping = {
            'title': 'TITLE',
            'artist': 'ARTIST',
            'album': 'ALBUM',
            'year': 'DATE',
            'genre': 'GENRE',
            'comment': 'COMMENT',
            'bpm': 'BPM',
            'key': 'KEY',
        }
        
        for tag_key, flac_key in tag_mapping.items():
            if tag_key in tags:
                audio[flac_key] = str(tags[tag_key])
        
        # Custom tags
        custom_fields = [
            'bpm_range', 'subgenre', 'mix_key', 'camelot_key',
            'where', 'when', 'mood', 'prominent_instruments',
            'bassline_type', 'vocal_type', 'set_position', 'energy_level'
        ]
        
        for field in custom_fields:
            if field in tags:
                value = tags[field]
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                audio[field.upper()] = str(value)
        
        audio.save()
        return True
        
    except Exception as e:
        print(f"Error writing FLAC tags: {e}")
        return False




def export_tags_to_central_json(audio_path: str, tags: Dict[str, Any], audio_features: Dict[str, Any] = None, json_path: str = "all_tags.json") -> str:
    """
    Export tags and audio features to a centralized JSON file where each filename is a key.
    
    Args:
        audio_path: Path to audio file
        tags: Tags dictionary to export
        audio_features: Audio features dictionary to export
        json_path: Path to centralized JSON file
    
    Returns:
        Path to the JSON file
    """
    filename = os.path.basename(audio_path)
    
    # Load existing central JSON file
    central_data = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                central_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load existing {json_path}: {e}")
    
    # Initialize file entry if it doesn't exist
    if filename not in central_data:
        central_data[filename] = {}
    
    # Update tags section
    tags_copy = tags.copy()
    tags_copy['source_file'] = filename
    central_data[filename]['tags'] = tags_copy
    
    # Update audio_features section if provided
    if audio_features:
        central_data[filename]['audio_features'] = audio_features
    
    # Write back to centralized file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(central_data, f, indent=2, ensure_ascii=False)
    
    return json_path


def load_audio_features_from_central_json(audio_path: str, json_path: str = "all_tags.json") -> Optional[Dict[str, Any]]:
    """
    Load cached audio features from the centralized JSON file.
    
    Args:
        audio_path: Path to audio file
        json_path: Path to centralized JSON file
    
    Returns:
        Audio features dictionary if found, None otherwise
    """
    filename = os.path.basename(audio_path)
    
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                central_data = json.load(f)
            
            if filename in central_data and 'audio_features' in central_data[filename]:
                return central_data[filename]['audio_features']
    except Exception as e:
        print(f"Warning: Could not load audio features from {json_path}: {e}")
    
    return None


def import_tags_from_central_json(filename: str, audio_path: str, json_path: str = "all_tags.json") -> bool:
    """
    Import tags for a specific file from the centralized JSON.
    
    Args:
        filename: Filename key to look up in the central JSON
        audio_path: Path to audio file to write tags to  
        json_path: Path to centralized JSON file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            central_data = json.load(f)
        
        if filename not in central_data:
            print(f"No data found for {filename} in {json_path}")
            return False
        
        # Handle both old format (direct tags) and new format (nested structure)
        if 'tags' in central_data[filename]:
            tags = central_data[filename]['tags']
        else:
            # Backward compatibility with old format
            tags = central_data[filename]
        
        # Remove source_file from tags before writing to audio file
        if 'source_file' in tags:
            del tags['source_file']
        
        return write_tags(audio_path, tags)
        
    except Exception as e:
        print(f"Error importing tags from central JSON: {e}")
        return False


