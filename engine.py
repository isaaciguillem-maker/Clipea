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

def hex_to_ass_color(hex_color: str) -> str:
    """Converts #RRGGBB to ASS color &H00BBGGRR"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}"
    return "&H00FFFFFF"

def get_ass_style_and_events(chunks: list, style_params: dict) -> str:
    """
    Generates the ASS file content based on text chunks and style parameters.
    chunks: list of tuples (start_time_sec, end_time_sec, text)
    style_params: dict with font_name, font_size, primary_color_hex, alignment, outline_width, shadow_width, animation
    """
    font_name = style_params.get("font_name", "Arial")
    font_size = style_params.get("font_size", 140)
    primary_color = hex_to_ass_color(style_params.get("primary_color_hex", "#FFFFFF"))
    alignment_str = style_params.get("alignment", "Center")
    outline_width = style_params.get("outline_width", 8)
    shadow_width = style_params.get("shadow_width", 4)
    animation = style_params.get("animation", "Fade")

    # Map alignment to ASS alignment values and base Y coordinates for animations
    if alignment_str == "Top":
        align_code = 8
        base_y = 250
    elif alignment_str == "Bottom":
        align_code = 2
        base_y = 1650
    else: # Center
        align_code = 5
        base_y = 960

    base_x = 540 # Center of 1080p

    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},{shadow_width},{align_code},10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for (start_t, end_t, text) in chunks:
        start_time_str = ms_to_ass_time(start_t)
        end_time_str = ms_to_ass_time(end_t)

        # Build effect string
        effect_tags = ""
        fade_dur = 50 # 50ms fade
        anim_dur = 80 # 80ms movement/zoom

        if animation == "Fade":
            effect_tags = f"{{\\fad({fade_dur},{fade_dur})}}"
        elif animation == "Zoom In":
            effect_tags = f"{{\\fscx70\\fscy70\\t(0,{anim_dur},\\fscx100\\fscy100)\\fad({fade_dur},{fade_dur})}}"
        elif animation == "Slide Up":
            # \move(x1, y1, x2, y2, t1, t2)
            effect_tags = f"{{\\move({base_x}, {base_y+80}, {base_x}, {base_y}, 0, {anim_dur})\\fad({fade_dur},{fade_dur})}}"
        elif animation == "Slide Down":
            effect_tags = f"{{\\move({base_x}, {base_y-80}, {base_x}, {base_y}, 0, {anim_dur})\\fad({fade_dur},{fade_dur})}}"
        elif animation == "None":
            effect_tags = ""
        else:
            effect_tags = f"{{\\fad({fade_dur},{fade_dur})}}" # Default

        ass_content += f"Dialogue: 0,{start_time_str},{end_time_str},Default,,0,0,0,,{effect_tags}{text}\n"

    return ass_content

def transcribe_audio(audio_path: str, model_size: str = "medium") -> list:
    """
    Transcribes audio and returns a list of chunks: (start, end, text).
    """
    print(f"Loading Whisper model '{model_size}'...")
    try:
        model = WhisperModel(model_size, device="auto", compute_type="auto")
        print("Starting transcription...")
        segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
        segments = list(segments)
    except Exception as gpu_e:
        print(f"GPU/Transcription failed ({gpu_e}). Falling back to CPU...")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        print("Starting transcription (CPU fallback)...")
        segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
        segments = list(segments)

    print(f"Detected language '{info.language}' with probability {info.language_probability}")

    chunks = []
    for segment in segments:
        current_chunk = []
        current_chunk_length = 0

        for word in segment.words:
            word_text = word.word.strip()
            if not word_text:
                continue

            if current_chunk and (len(current_chunk) >= 2 or current_chunk_length + len(word_text) > 12):
                start_t = current_chunk[0].start
                end_t = current_chunk[-1].end
                text_str = " ".join([w.word.strip() for w in current_chunk])
                chunks.append((start_t, end_t, text_str))

                current_chunk = []
                current_chunk_length = 0

            current_chunk.append(word)
            current_chunk_length += len(word_text)

        if current_chunk:
            start_t = current_chunk[0].start
            end_t = current_chunk[-1].end
            text_str = " ".join([w.word.strip() for w in current_chunk])
            chunks.append((start_t, end_t, text_str))

    return chunks

def generate_ass_file(chunks: list, output_ass_path: str, style_params: dict):
    """Generates the ASS file given chunks and styles."""
    content = get_ass_style_and_events(chunks, style_params)
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Subtitles saved to {output_ass_path}")

def generate_preview_frame(video_path: str, style_params: dict, output_image_path: str) -> bool:
    """
    Generates a single frame preview of the video with the styled text.
    Returns True if successful.
    """
    try:
        temp_ass = "temp_preview.ass"
        # Create a dummy chunk that lasts for 10 seconds
        chunks = [(0.0, 10.0, "Sample Text")]
        generate_ass_file(chunks, temp_ass, style_params)

        ass_path_abs = os.path.abspath(temp_ass)
        ass_filter_path = ass_path_abs.replace("\\", "/").replace(":", "\\:")

        # Use FFmpeg to extract the first frame (or frame at 00:00:01) with subtitles burned in
        # -ss 00:00:00.500 ensures we grab a frame where the subtitle animation (if any) has started/finished
        command = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:00.500",
            "-i", video_path,
            "-vf", f"ass='{ass_filter_path}',scale=360:-1", # Scale down for preview performance
            "-vframes", "1",
            "-q:v", "2",
            output_image_path
        ]

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if os.path.exists(temp_ass):
            os.remove(temp_ass)

        if process.returncode != 0:
            print(f"Preview generation error:\n{process.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Preview error: {e}")
        return False

def generate_final_video(video_path: str, audio_path: str, ass_path: str, output_path: str) -> bool:
    try:
        print("Starting video generation...")
        ass_path_abs = os.path.abspath(ass_path)
        ass_filter_path = ass_path_abs.replace("\\", "/").replace(":", "\\:")

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

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            print(f"FFmpeg error:\n{process.stderr}")
            return False

        print(f"Video generated successfully at {output_path}")
        return True
    except Exception as e:
        print(f"Video generation error: {e}")
        return False
