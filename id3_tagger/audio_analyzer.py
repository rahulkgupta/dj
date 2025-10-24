"""Audio feature extraction using Librosa."""

import numpy as np
import librosa
import time
import json
import os
import hashlib
from typing import Dict, Any, Optional


def _get_audio_cache_path(audio_path: str) -> str:
    """Generate cache file path for audio features."""
    # Use filename as cache key - simple and reliable
    filename = os.path.splitext(os.path.basename(audio_path))[0]
    cache_filename = f"{filename}_audio_features.json"
    return os.path.join(os.path.dirname(audio_path), ".audio_cache", cache_filename)


def _load_cached_features(cache_path: str) -> Optional[Dict[str, Any]]:
    """Load cached audio features if they exist."""
    try:
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"    - Warning: Could not load cache {cache_path}: {e}")
    return None


def _save_cached_features(cache_path: str, features: Dict[str, Any]) -> None:
    """Save audio features to cache."""
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(features, f, indent=2)
    except Exception as e:
        print(f"    - Warning: Could not save cache {cache_path}: {e}")


def extract_audio_features(audio_path: str, sr: Optional[int] = None, use_cache: bool = True) -> Dict[str, Any]:
    """
    Extract comprehensive audio features using Librosa.
    
    Args:
        audio_path: Path to audio file
        sr: Sample rate (None for native rate)
        use_cache: Whether to use cached features if available
    
    Returns:
        Dictionary of audio features for DSPy processing
    """
    # Load audio
    print(f"    - Loading audio file...")
    start = time.time()
    try:
        y, sr = librosa.load(audio_path, sr=sr)
        load_time = time.time() - start
        print(f"    - Audio loaded in {load_time:.2f}s ({len(y)/sr:.1f}s duration)")
    except Exception as e:
        print(f"    - ERROR loading audio: {e}")
        raise
    
    features = {}
    
    # Tempo and beat tracking
    print(f"    - Analyzing tempo and beats...")
    start = time.time()
    try:
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        beat_time = time.time() - start
        print(f"    - Beat tracking took {beat_time:.2f}s")
        features['bpm'] = float(tempo)
        features['bpm_range'] = str(int(tempo // 10) * 10)  # Floor to tens (128 -> 120)
    except Exception as e:
        print(f"    - ERROR in beat tracking: {e}")
        raise
    
    # Beat strength (used in AI prompt)
    print(f"    - Computing beat strength...")
    start = time.time()
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        features['beat_strength'] = float(np.mean(onset_env))
        beat_strength_time = time.time() - start
        print(f"    - Beat strength took {beat_strength_time:.2f}s")
    except Exception as e:
        print(f"    - ERROR in beat strength: {e}")
        raise
    
    # Key detection using chroma (used in AI prompt)
    print(f"    - Detecting key...")
    start = time.time()
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    chroma_mean = np.mean(chroma, axis=1)
    key_idx = np.argmax(chroma_mean)
    keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    features['key'] = keys[key_idx]
    key_time = time.time() - start
    print(f"    - Key detection took {key_time:.2f}s")
    
    # Spectral centroid only (used in AI prompt)
    print(f"    - Computing spectral centroid...")
    start = time.time()
    spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)
    features['spectral_centroid_mean'] = float(np.mean(spectral_centroids))
    spectral_time = time.time() - start
    print(f"    - Spectral centroid took {spectral_time:.2f}s")
    
    # Energy features (used in AI prompt)
    print(f"    - Computing energy features...")
    start = time.time()
    rms = librosa.feature.rms(y=y)
    features['energy_mean'] = float(np.mean(rms))
    features['energy_std'] = float(np.std(rms))
    features['dynamic_range'] = float(np.max(rms) - np.min(rms))
    energy_time = time.time() - start
    print(f"    - Energy features took {energy_time:.2f}s")
    
    # Onset detection (used in AI prompt)
    print(f"    - Detecting onsets...")
    start = time.time()
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units='time')
    duration = len(y) / sr
    features['onset_rate'] = len(onsets) / duration if duration > 0 else 0
    onset_time = time.time() - start
    print(f"    - Onset detection took {onset_time:.2f}s")
    
    # Harmonic-percussive separation (used in AI prompt)
    print(f"    - Computing harmonic/percussive ratio...")
    start = time.time()
    y_harmonic, y_percussive = librosa.effects.hpss(y)
    harmonic_energy = np.mean(librosa.feature.rms(y=y_harmonic))
    percussive_energy = np.mean(librosa.feature.rms(y=y_percussive))
    total_energy = harmonic_energy + percussive_energy
    features['harmonic_ratio'] = float(harmonic_energy / total_energy) if total_energy > 0 else 0.5
    hpss_time = time.time() - start
    print(f"    - Harmonic/percussive separation took {hpss_time:.2f}s")
    
    # Frequency band energy distribution (used in AI prompt)
    print(f"    - Computing frequency distribution...")
    start = time.time()
    # More efficient approach using power spectral density
    fft_data = np.fft.fft(y)
    freqs = np.fft.fftfreq(len(y), 1/sr)
    power = np.abs(fft_data[:len(freqs)//2])
    
    # Define frequency bands
    low_mask = (freqs[:len(freqs)//2] >= 20) & (freqs[:len(freqs)//2] < 250)
    mid_mask = (freqs[:len(freqs)//2] >= 250) & (freqs[:len(freqs)//2] < 4000)
    high_mask = freqs[:len(freqs)//2] >= 4000
    
    low_freq_energy = np.sum(power[low_mask])
    mid_freq_energy = np.sum(power[mid_mask])
    high_freq_energy = np.sum(power[high_mask])
    
    total_freq_energy = low_freq_energy + mid_freq_energy + high_freq_energy
    if total_freq_energy > 0:
        features['low_freq_energy'] = float(low_freq_energy / total_freq_energy)
        features['mid_freq_energy'] = float(mid_freq_energy / total_freq_energy)
        features['high_freq_energy'] = float(high_freq_energy / total_freq_energy)
    else:
        features['low_freq_energy'] = 0.33
        features['mid_freq_energy'] = 0.33
        features['high_freq_energy'] = 0.33
    freq_time = time.time() - start
    print(f"    - Frequency distribution took {freq_time:.2f}s")
    
    # Basic duration info
    features['duration_seconds'] = float(duration)
    features['duration_minutes'] = float(duration / 60)
    
    # Tempo stability (used in AI prompt)
    print(f"    - Computing tempo stability...")
    start = time.time()
    if len(beats) > 1:
        beat_times = librosa.frames_to_time(beats, sr=sr)
        inter_beat_intervals = np.diff(beat_times)
        features['tempo_stability'] = float(1.0 / (1.0 + np.std(inter_beat_intervals)))
    else:
        features['tempo_stability'] = 0.0
    tempo_stability_time = time.time() - start
    print(f"    - Tempo stability took {tempo_stability_time:.2f}s")
    
    
    return features


def get_camelot_key(key: str, mode: str = 'major') -> str:
    """
    Convert musical key to Camelot wheel notation.
    
    Args:
        key: Musical key (e.g., 'C', 'G#')
        mode: 'major' or 'minor'
    
    Returns:
        Camelot key (e.g., '8B', '5A')
    """
    camelot_major = {
        'C': '8B', 'G': '9B', 'D': '10B', 'A': '11B', 'E': '12B', 'B': '1B',
        'F#': '2B', 'Gb': '2B', 'Db': '3B', 'C#': '3B', 'Ab': '4B', 'G#': '4B',
        'Eb': '5B', 'D#': '5B', 'Bb': '6B', 'A#': '6B', 'F': '7B'
    }
    
    camelot_minor = {
        'A': '8A', 'E': '9A', 'B': '10A', 'F#': '11A', 'Gb': '11A', 'C#': '12A',
        'Db': '12A', 'G#': '1A', 'Ab': '1A', 'Eb': '2A', 'D#': '2A', 'Bb': '3A',
        'A#': '3A', 'F': '4A', 'C': '5A', 'G': '6A', 'D': '7A'
    }
    
    if mode == 'major':
        return camelot_major.get(key, '8B')
    else:
        return camelot_minor.get(key, '8A')


def format_features_for_llm(features: Dict[str, Any]) -> str:
    """
    Format audio features into a readable string for LLM processing.
    
    Args:
        features: Dictionary of audio features
    
    Returns:
        Formatted string description
    """
    description = f"""
Audio Analysis Results:
- BPM: {features['bpm']:.1f} (Range: {features['bpm_range']})
- Key: {features.get('key', 'Unknown')}
- Energy: {features['energy_mean']:.3f} (std: {features['energy_std']:.3f})
- Spectral Centroid: {features['spectral_centroid_mean']:.0f} Hz
- Harmonic/Percussive Ratio: {features['harmonic_ratio']:.2f}
- Onset Rate: {features['onset_rate']:.2f} per second
- Zero Crossing Rate: {features['zero_crossing_rate']:.3f}
- Tempo Stability: {features['tempo_stability']:.2f}
- Duration: {features['duration_minutes']:.1f} minutes

Frequency Distribution:
- Low (Bass): {features['low_freq_energy']:.2%}
- Mid: {features['mid_freq_energy']:.2%}
- High (Treble): {features['high_freq_energy']:.2%}
"""
    return description.strip()