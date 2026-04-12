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
    style_params: dict with font_name, font_size, primary_color_hex, alignment, outline_width, shadow_width, animations, offset, uppercase
    """
    font_name = style_params.get("font_name", "Arial")
    font_size = style_params.get("font_size", 140)
    primary_color = hex_to_ass_color(style_params.get("primary_color_hex", "#FFFFFF"))
    alignment_str = style_params.get("alignment", "Center")
    outline_width = style_params.get("outline_width", 8)
    shadow_width = style_params.get("shadow_width", 4)
    glow_intensity = style_params.get("glow_intensity", 0)
    entry_anim = style_params.get("entry_animation", "Fade")
    exit_anim = style_params.get("exit_animation", "Fade")
    uppercase = style_params.get("uppercase", False)
    sync_offset_ms = style_params.get("sync_offset_ms", 0)

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
"""
    if glow_intensity > 0:
        # Glow style uses primary color as outline, wide outline, no shadow
        ass_content += f"Style: Glow,{font_name},{font_size},{primary_color},&H000000FF,{primary_color},&H00000000,-1,0,0,0,100,100,0,0,1,{glow_intensity},0,{align_code},10,10,10,1\n"

    ass_content += """
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    for (start_t, end_t, text) in chunks:
        # Apply sync offset (in seconds)
        adjusted_start = max(0.0, start_t + (sync_offset_ms / 1000.0))
        adjusted_end = max(0.1, end_t + (sync_offset_ms / 1000.0))

        # Ensure start is strictly before end
        if adjusted_start >= adjusted_end:
            adjusted_start = adjusted_end - 0.1

        start_time_str = ms_to_ass_time(adjusted_start)
        end_time_str = ms_to_ass_time(adjusted_end)

        if uppercase:
            text = text.upper()

        # Duration in ms
        dur_ms = int((adjusted_end - adjusted_start) * 1000)

        # Build effect string
        fade_in = 50 if entry_anim == "Fade" else 0
        fade_out = 50 if exit_anim == "Fade" else 0
        anim_dur = 80 # 80ms movement/zoom

        # Initialize tags
        tags = []

        # Fade tags
        if entry_anim != "None" or exit_anim != "None":
            # If not explicitly fade, we still use a tiny fade to smooth out appearing/disappearing
            fade_in_val = 50 if entry_anim in ["Fade", "Zoom In", "Slide Up", "Slide Down"] else 0
            fade_out_val = 50 if exit_anim in ["Fade", "Zoom Out", "Slide Up", "Slide Down"] else 0
            tags.append(f"\\fad({fade_in_val},{fade_out_val})")

        # Zoom tags
        if entry_anim == "Zoom In":
            tags.append(f"\\fscx70\\fscy70\\t(0,{anim_dur},\\fscx100\\fscy100)")

        if exit_anim == "Zoom Out":
            t_start = max(0, dur_ms - anim_dur)
            tags.append(f"\\t({t_start},{dur_ms},\\fscx70\\fscy70)")

        # Slide tags. ASS only allows one \move tag per event.
        # If both are slide, we use \move for entry, and fallback exit to fade-only.
        # We handle Slide Up/Down
        is_move_used = False
        if entry_anim == "Slide Up":
            tags.append(f"\\move({base_x}, {base_y+80}, {base_x}, {base_y}, 0, {anim_dur})")
            is_move_used = True
        elif entry_anim == "Slide Down":
            tags.append(f"\\move({base_x}, {base_y-80}, {base_x}, {base_y}, 0, {anim_dur})")
            is_move_used = True

        if exit_anim == "Slide Up" and not is_move_used:
            t_start = max(0, dur_ms - anim_dur)
            tags.append(f"\\move({base_x}, {base_y}, {base_x}, {base_y-80}, {t_start}, {dur_ms})")
            is_move_used = True
        elif exit_anim == "Slide Down" and not is_move_used:
            t_start = max(0, dur_ms - anim_dur)
            tags.append(f"\\move({base_x}, {base_y}, {base_x}, {base_y+80}, {t_start}, {dur_ms})")
            is_move_used = True

        # If no \move is used but position is default, we can just optionally use \pos
        # But ASS default position based on alignment is fine if no \pos or \move is present.

        effect_tags_str = "".join(tags)

        if glow_intensity > 0:
            # We need two lines: Layer 0 for glow, Layer 1 for actual text
            # Glow needs \blur tag
            glow_tags = f"{{{effect_tags_str}\\blur{glow_intensity}}}" if effect_tags_str else f"{{\\blur{glow_intensity}}}"
            main_tags = f"{{{effect_tags_str}}}" if effect_tags_str else ""

            ass_content += f"Dialogue: 0,{start_time_str},{end_time_str},Glow,,0,0,0,,{glow_tags}{text}\n"
            ass_content += f"Dialogue: 1,{start_time_str},{end_time_str},Default,,0,0,0,,{main_tags}{text}\n"
        else:
            effect_tags = f"{{{effect_tags_str}}}" if effect_tags_str else ""
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

        # Override sync_offset_ms for the preview so the text always appears at 0.5s
        # regardless of the user's timeline offset settings.
        preview_style = style_params.copy()
        preview_style["sync_offset_ms"] = 0

        generate_ass_file(chunks, temp_ass, preview_style)

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
