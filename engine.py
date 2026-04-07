import os
import subprocess
from faster_whisper import WhisperModel

def ms_to_ass_time(ms: float) -> str:
    """Converts seconds float to ASS time format: H:MM:SS.cs"""
    ms = int(ms * 100) # hundredths of a second
    hours = ms // 360000
    ms %= 360000
    minutes = ms // 6000
    ms %= 6000
    seconds = ms // 100
    cs = ms % 100
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"

def transcribe_audio_to_ass(audio_path: str, output_ass_path: str, model_size: str = "medium") -> bool:
    """
    Transcribes audio and generates an ASS subtitle file with a modern style.
    Returns True if successful, False otherwise.
    """
    try:
        print(f"Loading Whisper model '{model_size}'...")
        try:
            # device="auto" tries GPU first.
            model = WhisperModel(model_size, device="auto", compute_type="auto")
            print("Starting transcription...")
            # The exception often happens here because CUDA libraries are lazily loaded
            segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=False)
            segments = list(segments) # force generation to trigger any lazy load errors
        except Exception as gpu_e:
            print(f"GPU/Transcription failed ({gpu_e}). Falling back to CPU...")
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            print("Starting transcription (CPU fallback)...")
            segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=False)
            segments = list(segments)

        print(f"Detected language '{info.language}' with probability {info.language_probability}")

        # ASS header with styles
        # Style format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,90,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,10,10,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        # Convert segments to ASS events
        for segment in segments:
            start_time = ms_to_ass_time(segment.start)
            end_time = ms_to_ass_time(segment.end)
            text = segment.text.strip()

            # Simple fade effect for modern feel: {\fad(150,150)}
            fade_effect = r"{\fad(150,150)}"
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{fade_effect}{text}\n"

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        print(f"Subtitles saved to {output_ass_path}")
        return True
    except Exception as e:
        print(f"Transcription error: {e}")
        return False

def generate_final_video(video_path: str, audio_path: str, ass_path: str, output_path: str) -> bool:
    """
    Combines video, audio, and ASS subtitles into a final video.
    Returns True if successful, False otherwise.
    """
    try:
        print("Starting video generation...")

        # Ensure the paths are absolute and formatted correctly for FFmpeg's ass filter
        ass_path_abs = os.path.abspath(ass_path)
        # FFmpeg on Windows needs escaping for absolute paths in the ass filter,
        # e.g., C:\path\to\sub.ass -> C\\:/path/to/sub.ass
        # A simpler cross-platform way is to run ffmpeg in the directory or use relative paths if possible.
        # But we will use the standard path format. If it causes issues on Windows, we'll format it.
        ass_filter_path = ass_path_abs.replace("\\", "/").replace(":", "\\:")

        # Build FFmpeg command
        # -i video: input video
        # -i audio: input audio
        # -map 0:v: use video stream from first input
        # -map 1:a: use audio stream from second input
        # -c:v libx264: encode video with h264
        # -vf ass='...': apply ASS subtitles
        # -c:a aac: encode audio with aac
        # -shortest: end when the shortest input ends (usually the audio)
        # -y: overwrite output
        command = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v",
            "-map", "1:a",
            "-vf", f"ass='{ass_filter_path}'",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

        # Run FFmpeg
        # subprocess.run will wait for it to finish
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            print(f"FFmpeg error:\n{process.stderr}")
            return False

        print(f"Video generated successfully at {output_path}")
        return True
    except Exception as e:
        print(f"Video generation error: {e}")
        return False
