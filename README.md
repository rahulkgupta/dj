# Audio-Video Sync Tool

A Python script that automatically synchronizes an AIF audio file with a MOV video file using cross-correlation to find the optimal alignment point.

## Features

- Automatically detects sync point between audio and video using cross-correlation
- Trims video to match the audio duration
- Creates a new MOV file without modifying the originals
- Supports manual offset override if needed

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install ffmpeg (required for video processing):
```bash
# On macOS with Homebrew
brew install ffmpeg

# On Ubuntu/Debian
sudo apt-get install ffmpeg

# On Windows
# Download from https://ffmpeg.org/download.html
```

## Usage

Basic usage:
```bash
python audio_video_sync.py audio.aif video.mov -o synced_output.mov
```

With manual offset (in seconds):
```bash
python audio_video_sync.py audio.aif video.mov -o synced_output.mov --offset 5.2
```

### Arguments

- `audio_file`: Path to the AIF audio file (will become the soundtrack)
- `video_file`: Path to the MOV video file (source video)
- `-o, --output`: Output file path (default: synced_output.mov)
- `--offset`: Manual offset in seconds (overrides auto-detection)
- `--sample-rate`: Sample rate for audio processing (default: 44100)

## How It Works

1. **Audio Extraction**: Extracts audio from the MOV file for comparison
2. **Cross-Correlation**: Uses signal processing to find where the AIF audio best aligns with the video's audio
3. **Video Trimming**: Trims the video starting from the sync point for the duration of the AIF file
4. **Audio Replacement**: Replaces the video's audio with the AIF file
5. **Output Creation**: Creates a new MOV file with the synced audio and trimmed video

## Important Notes

- The original MOV and AIF files are never modified
- The output video will be the same duration as the AIF audio file
- The video must be longer than or equal to the AIF audio duration
- Requires ffmpeg to be installed and available in PATH

## Example

If you have:
- `recording.aif`: A 30-second high-quality audio recording
- `video.mov`: A 60-second video that contains the same audio somewhere in it

Running:
```bash
python audio_video_sync.py recording.aif video.mov -o final.mov
```

Will create `final.mov` that:
- Is exactly 30 seconds long (matching the AIF duration)
- Starts at the point where the audio syncs
- Uses the AIF file as the audio track