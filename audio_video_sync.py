#!/usr/bin/env python3
"""
Audio-Video Synchronization Script
Syncs an AIF audio file with a MOV video file by:
1. Finding the sync point using cross-correlation
2. Trimming the video to match the audio duration
3. Creating a new MOV file with the synced audio
"""

import argparse
import subprocess
import sys
import os
import numpy as np
from scipy import signal
import librosa
import tempfile
import json


def extract_audio_from_video(video_path, output_path=None):
    """Extract audio from video file to a temporary WAV file."""
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # PCM 16-bit
        '-ar', '44100',  # Sample rate
        '-ac', '2',  # Stereo
        '-y',  # Overwrite output
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e.stderr}")
        sys.exit(1)


def load_audio(file_path, sr=None):
    """Load audio file and return audio data and sample rate."""
    try:
        y, sr = librosa.load(file_path, sr=sr, mono=True)
        return y, sr
    except Exception as e:
        print(f"Error loading audio file {file_path}: {e}")
        sys.exit(1)


def find_sync_offset(reference_audio, target_audio, sr):
    """
    Find the time offset where reference_audio best aligns with target_audio.
    Returns offset in seconds.
    """
    print("Finding sync point using cross-correlation...")
    
    # Normalize audio signals
    reference_audio = reference_audio / np.max(np.abs(reference_audio))
    target_audio = target_audio / np.max(np.abs(target_audio))
    
    # Perform cross-correlation
    correlation = signal.correlate(target_audio, reference_audio, mode='valid', method='fft')
    
    # Find the peak
    peak_index = np.argmax(np.abs(correlation))
    
    # Convert to time offset
    offset_seconds = peak_index / sr
    
    # Calculate correlation coefficient at peak for confidence
    peak_correlation = correlation[peak_index] / (len(reference_audio) * np.std(reference_audio) * np.std(target_audio[:len(reference_audio)]))
    
    print(f"Found sync point at {offset_seconds:.2f} seconds (correlation: {peak_correlation:.3f})")
    
    return offset_seconds


def get_video_duration(video_path):
    """Get the duration of a video file in seconds."""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except (subprocess.CalledProcessError, KeyError, ValueError) as e:
        print(f"Error getting video duration: {e}")
        sys.exit(1)


def create_synced_video(video_path, audio_path, output_path, start_time, duration):
    """
    Create a new video file with:
    - Video trimmed from start_time for duration seconds
    - Audio replaced with the provided audio file
    """
    print(f"Creating synced video...")
    print(f"  Trimming video from {start_time:.2f}s for {duration:.2f}s")
    
    cmd = [
        'ffmpeg',
        '-ss', str(start_time),  # Start time
        '-i', video_path,  # Input video
        '-i', audio_path,  # Input audio
        '-t', str(duration),  # Duration
        '-c:v', 'copy',  # Copy video codec
        '-c:a', 'aac',  # Audio codec
        '-b:a', '192k',  # Audio bitrate
        '-map', '0:v:0',  # Use video from first input
        '-map', '1:a:0',  # Use audio from second input
        '-y',  # Overwrite output
        output_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"Successfully created synced video: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating synced video: {e.stderr}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Sync an AIF audio file with a MOV video file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python audio_video_sync.py audio.aif video.mov -o synced_output.mov
  
The script will:
1. Find where the audio aligns in the video
2. Trim the video to match the audio duration
3. Create a new video file with the synced audio
        """
    )
    
    parser.add_argument('audio_file', help='Path to the AIF audio file')
    parser.add_argument('video_file', help='Path to the MOV video file')
    parser.add_argument('-o', '--output', default='synced_output.mov',
                        help='Output file path (default: synced_output.mov)')
    parser.add_argument('--offset', type=float, default=None,
                        help='Manual offset in seconds (overrides auto-detection)')
    parser.add_argument('--sample-rate', type=int, default=44100,
                        help='Sample rate for audio processing (default: 44100)')
    
    args = parser.parse_args()
    
    # Validate input files exist
    if not os.path.exists(args.audio_file):
        print(f"Error: Audio file '{args.audio_file}' not found")
        sys.exit(1)
    if not os.path.exists(args.video_file):
        print(f"Error: Video file '{args.video_file}' not found")
        sys.exit(1)
    
    print(f"Processing files:")
    print(f"  Audio: {args.audio_file}")
    print(f"  Video: {args.video_file}")
    print(f"  Output: {args.output}")
    
    # Load the reference audio (AIF file)
    print(f"\nLoading audio file...")
    ref_audio, sr = load_audio(args.audio_file, sr=args.sample_rate)
    audio_duration = len(ref_audio) / sr
    print(f"  Audio duration: {audio_duration:.2f} seconds")
    
    # Extract and load audio from video
    print(f"\nExtracting audio from video...")
    temp_audio_path = None
    try:
        temp_audio_path = extract_audio_from_video(args.video_file)
        video_audio, _ = load_audio(temp_audio_path, sr=sr)
        video_duration = get_video_duration(args.video_file)
        print(f"  Video duration: {video_duration:.2f} seconds")
        
        # Find sync offset
        if args.offset is not None:
            offset = args.offset
            print(f"\nUsing manual offset: {offset:.2f} seconds")
        else:
            print(f"\nFinding sync offset...")
            offset = find_sync_offset(ref_audio, video_audio, sr)
        
        # Validate offset
        if offset < 0:
            print(f"Warning: Negative offset ({offset:.2f}s) - setting to 0")
            offset = 0
        
        if offset + audio_duration > video_duration:
            print(f"Warning: Audio extends beyond video end")
            print(f"  Video ends at: {video_duration:.2f}s")
            print(f"  Audio would end at: {offset + audio_duration:.2f}s")
            
            # Ask user if they want to continue
            response = input("Continue anyway? (y/n): ").lower()
            if response != 'y':
                print("Aborted by user")
                sys.exit(0)
        
        # Create the synced video
        print(f"\nCreating synced video...")
        create_synced_video(
            args.video_file,
            args.audio_file,
            args.output,
            offset,
            audio_duration
        )
        
        print(f"\nSuccess! Synced video saved to: {args.output}")
        print(f"  Start time: {offset:.2f}s")
        print(f"  Duration: {audio_duration:.2f}s")
        
    finally:
        # Clean up temporary file
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


if __name__ == '__main__':
    main()