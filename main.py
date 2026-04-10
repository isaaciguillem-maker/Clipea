import os
import threading
from tkinter import filedialog, messagebox, colorchooser
import customtkinter as ctk
from PIL import Image

from engine import transcribe_audio, generate_ass_file, generate_preview_frame, generate_final_video

ctk.set_appearance_mode("Light")

# We will define custom colors for orange accents manually on widgets
# Base background: #F5F6FA (light grayish blue)
# Sidebar: #FFFFFF (white)
# Accent: #FF6B00 (vibrant orange)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Lyrics Video Generator")
        self.geometry("1200x800")
        self.configure(fg_color="#F5F6FA")

        # Variables
        self.video_path = ctk.StringVar()
        self.audio_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.model_size = ctk.StringVar(value="medium")

        # Style Variables
        self.font_name = ctk.StringVar(value="Arial")
        self.font_size = ctk.IntVar(value=140)
        self.primary_color_hex = ctk.StringVar(value="#FFFFFF")
        self.alignment = ctk.StringVar(value="Center")
        self.outline_width = ctk.IntVar(value=8)
        self.shadow_width = ctk.IntVar(value=4)
        self.entry_animation = ctk.StringVar(value="Fade")
        self.exit_animation = ctk.StringVar(value="Fade")
        self.uppercase = ctk.BooleanVar(value=False)
        self.sync_offset_ms = ctk.IntVar(value=0)

        self.preview_debounce_timer = None
        self.current_preview_image = None

        self.create_widgets()

    def get_style_params(self):
        return {
            "font_name": self.font_name.get(),
            "font_size": self.font_size.get(),
            "primary_color_hex": self.primary_color_hex.get(),
            "alignment": self.alignment.get(),
            "outline_width": self.outline_width.get(),
            "shadow_width": self.shadow_width.get(),
            "entry_animation": self.entry_animation.get(),
            "exit_animation": self.exit_animation.get(),
            "uppercase": self.uppercase.get(),
            "sync_offset_ms": self.sync_offset_ms.get()
        }

    def on_offset_change(self, value):
        self.lbl_offset_val.configure(text=f"{int(value)} ms")
        self.on_style_change()

    def on_style_change(self, *args):
        # Debounce the preview update
        if self.preview_debounce_timer is not None:
            self.after_cancel(self.preview_debounce_timer)
        self.preview_debounce_timer = self.after(500, self.update_preview)

    def create_widgets(self):
        # Base colors
        color_accent = "#FF6B00"
        color_accent_hover = "#E65A00"
        color_panel = "#FFFFFF"
        color_text = "#333333"

        # Main layout:
        # Row 0: Top Bar
        # Row 1: Main Content (3 columns: Left Sidebar, Center Preview, Right Sidebar)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ==========================================
        # TOP BAR
        # ==========================================
        top_bar = ctk.CTkFrame(self, height=60, fg_color=color_panel, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(0, weight=1)

        # Logo / Title
        lbl_title = ctk.CTkLabel(top_bar, text="Auto Lyrics Video", font=ctk.CTkFont(size=20, weight="bold"), text_color=color_text)
        lbl_title.pack(side="left", padx=20, pady=15)

        # File selection frame inside top bar
        frame_top_files = ctk.CTkFrame(top_bar, fg_color="transparent")
        frame_top_files.pack(side="left", padx=20, pady=10)

        btn_video = ctk.CTkButton(frame_top_files, text="📂 Video", width=100, fg_color=color_panel, text_color=color_text, border_width=1, border_color="#DDDDDD", hover_color="#F0F0F0", command=self.browse_video)
        btn_video.pack(side="left", padx=5)

        btn_audio = ctk.CTkButton(frame_top_files, text="🎵 Audio", width=100, fg_color=color_panel, text_color=color_text, border_width=1, border_color="#DDDDDD", hover_color="#F0F0F0", command=self.browse_audio)
        btn_audio.pack(side="left", padx=5)

        # Export Selection
        frame_top_export = ctk.CTkFrame(top_bar, fg_color="transparent")
        frame_top_export.pack(side="right", padx=20, pady=10)

        btn_output = ctk.CTkButton(frame_top_export, text="💾 Save As", width=100, fg_color=color_panel, text_color=color_text, border_width=1, border_color="#DDDDDD", hover_color="#F0F0F0", command=self.browse_output)
        btn_output.pack(side="left", padx=5)

        self.btn_generate = ctk.CTkButton(frame_top_export, text="Export Video", font=ctk.CTkFont(weight="bold"), fg_color=color_accent, hover_color=color_accent_hover, command=self.start_generation)
        self.btn_generate.pack(side="left", padx=5)

        # ==========================================
        # MAIN CONTENT AREA
        # ==========================================
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)

        main_content.grid_rowconfigure(0, weight=1)
        main_content.grid_columnconfigure(0, weight=0) # Left sidebar
        main_content.grid_columnconfigure(1, weight=1) # Center preview
        main_content.grid_columnconfigure(2, weight=0) # Right sidebar

        # ==========================================
        # LEFT SIDEBAR: Presets
        # ==========================================
        left_panel = ctk.CTkFrame(main_content, width=200, fg_color=color_panel, corner_radius=10)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_panel.grid_propagate(False)

        lbl_presets = ctk.CTkLabel(left_panel, text="Presets", font=ctk.CTkFont(size=16, weight="bold"), text_color=color_text)
        lbl_presets.pack(pady=20, padx=20, anchor="w")

        # Placeholder for future presets
        lbl_preset_ph = ctk.CTkLabel(left_panel, text="(Plantillas estarán\ndisponibles aquí)", text_color="#888888")
        lbl_preset_ph.pack(pady=10)

        # ==========================================
        # CENTER: Live Preview
        # ==========================================
        center_panel = ctk.CTkFrame(main_content, fg_color="transparent")
        center_panel.grid(row=0, column=1, sticky="nsew", padx=10)

        # A frame to hold the preview image with a subtle shadow/border look
        preview_container = ctk.CTkFrame(center_panel, fg_color=color_panel, corner_radius=15)
        preview_container.pack(expand=True)

        self.lbl_preview_img = ctk.CTkLabel(preview_container, text="Select a video to see preview", bg_color="gray90", text_color="#888888", width=360, height=640)
        self.lbl_preview_img.pack(padx=20, pady=20)

        # ==========================================
        # RIGHT SIDEBAR: Customization
        # ==========================================
        right_panel = ctk.CTkScrollableFrame(main_content, width=320, fg_color=color_panel, corner_radius=10)
        right_panel.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        lbl_style_title = ctk.CTkLabel(right_panel, text="Style Customization", font=ctk.CTkFont(size=16, weight="bold"), text_color=color_text)
        lbl_style_title.pack(pady=20, padx=20, anchor="w")

        # Font
        frame_font = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_font.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_font, text="Font", text_color=color_text).pack(anchor="w")
        opt_font = ctk.CTkOptionMenu(frame_font, variable=self.font_name, values=["Arial", "Impact", "Verdana", "Comic Sans MS", "Times New Roman"], fg_color="#F0F0F0", text_color=color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_font.pack(fill="x", pady=(5,0))

        # Size
        frame_size = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_size.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_size, text="Size", text_color=color_text).pack(anchor="w")
        sld_size = ctk.CTkSlider(frame_size, variable=self.font_size, from_=50, to=250, button_color=color_accent, button_hover_color=color_accent_hover, progress_color=color_accent, command=self.on_style_change)
        sld_size.pack(fill="x", pady=(5,0))

        # Color
        frame_color = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_color.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_color, text="Primary Color", text_color=color_text).pack(anchor="w")
        self.btn_color = ctk.CTkButton(frame_color, text="Pick Color", fg_color=self.primary_color_hex.get(), text_color="black", border_width=1, border_color="#CCCCCC", command=self.pick_color)
        self.btn_color.pack(fill="x", pady=(5,0))

        # Alignment
        frame_align = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_align.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_align, text="Position", text_color=color_text).pack(anchor="w")
        opt_align = ctk.CTkOptionMenu(frame_align, variable=self.alignment, values=["Top", "Center", "Bottom"], fg_color="#F0F0F0", text_color=color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_align.pack(fill="x", pady=(5,0))

        # Animations
        frame_anim = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_anim.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_anim, text="Entry Anim", text_color=color_text).pack(anchor="w")
        opt_anim_in = ctk.CTkOptionMenu(frame_anim, variable=self.entry_animation, values=["None", "Fade", "Zoom In", "Slide Up", "Slide Down"], fg_color="#F0F0F0", text_color=color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_anim_in.pack(fill="x", pady=(5,10))

        ctk.CTkLabel(frame_anim, text="Exit Anim", text_color=color_text).pack(anchor="w")
        opt_anim_out = ctk.CTkOptionMenu(frame_anim, variable=self.exit_animation, values=["None", "Fade", "Zoom Out", "Slide Up", "Slide Down"], fg_color="#F0F0F0", text_color=color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_anim_out.pack(fill="x", pady=(5,0))

        # Outline & Shadow
        frame_fx = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_fx.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frame_fx, text="Outline Width", text_color=color_text).pack(anchor="w")
        sld_outline = ctk.CTkSlider(frame_fx, variable=self.outline_width, from_=0, to=20, button_color=color_accent, button_hover_color=color_accent_hover, progress_color=color_accent, command=self.on_style_change)
        sld_outline.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(frame_fx, text="Shadow Width", text_color=color_text).pack(anchor="w")
        sld_shadow = ctk.CTkSlider(frame_fx, variable=self.shadow_width, from_=0, to=20, button_color=color_accent, button_hover_color=color_accent_hover, progress_color=color_accent, command=self.on_style_change)
        sld_shadow.pack(fill="x", pady=(0, 5))

        # Checkbox
        chk_upper = ctk.CTkCheckBox(right_panel, text="ALL UPPERCASE", variable=self.uppercase, text_color=color_text, fg_color=color_accent, hover_color=color_accent_hover, command=self.on_style_change)
        chk_upper.pack(padx=20, pady=15, anchor="w")

        # Sync Offset
        frame_offset = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_offset.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_offset, text="Sync Offset", text_color=color_text).pack(anchor="w")

        offset_inner = ctk.CTkFrame(frame_offset, fg_color="transparent")
        offset_inner.pack(fill="x")
        self.lbl_offset_val = ctk.CTkLabel(offset_inner, text="0 ms", width=50, text_color=color_text)
        self.lbl_offset_val.pack(side="right", padx=5)
        sld_offset = ctk.CTkSlider(offset_inner, variable=self.sync_offset_ms, from_=-1000, to=1000, button_color=color_accent, button_hover_color=color_accent_hover, progress_color=color_accent, command=self.on_offset_change)
        sld_offset.pack(side="left", fill="x", expand=True)

        # Log Textbox (hidden until needed, but we keep it small at the bottom)
        self.textbox_log = ctk.CTkTextbox(right_panel, height=80, fg_color="#F0F0F0", text_color=color_text)
        self.textbox_log.pack(fill="x", padx=20, pady=20)
        self.textbox_log.insert("0.0", "Logs...\n")
        self.textbox_log.configure(state="disabled")

    def pick_color(self):
        color_code = colorchooser.askcolor(title="Choose color")[1]
        if color_code:
            self.primary_color_hex.set(color_code)
            # Update button color visually
            self.btn_color.configure(fg_color=color_code)
            # Update text color so it remains visible if background is bright
            self.btn_color.configure(text_color="black" if self.is_bright(color_code) else "white")
            self.on_style_change()

    def is_bright(self, hex_color):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return luma > 128

    def log(self, message):
        self.after(0, self._log_main_thread, message)

    def _log_main_thread(self, message):
        self.textbox_log.configure(state="normal")
        self.textbox_log.insert("end", message + "\n")
        self.textbox_log.see("end")
        self.textbox_log.configure(state="disabled")
        self.update_idletasks()

    def browse_video(self):
        filename = filedialog.askopenfilename(title="Select Video", filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if filename:
            self.video_path.set(filename)
            self.update_preview()

    def browse_audio(self):
        filename = filedialog.askopenfilename(title="Select Audio", filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if filename:
            self.audio_path.set(filename)

    def browse_output(self):
        filename = filedialog.asksaveasfilename(title="Save Output Video", defaultextension=".mp4", filetypes=[("MP4 Video", "*.mp4")])
        if filename:
            self.output_path.set(filename)

    def update_preview(self):
        video = self.video_path.get()
        if not video or not os.path.exists(video):
            return

        self.lbl_preview_img.configure(text="Generating preview...")
        # Run in thread to not freeze UI
        threading.Thread(target=self._generate_and_show_preview, args=(video,), daemon=True).start()

    def _generate_and_show_preview(self, video_path):
        preview_img_path = "temp_preview.jpg"
        success = generate_preview_frame(video_path, self.get_style_params(), preview_img_path)

        if success and os.path.exists(preview_img_path):
            self.after(0, self._set_preview_image, preview_img_path)
        else:
            self.after(0, lambda: self.lbl_preview_img.configure(text="Preview generation failed."))

    def _set_preview_image(self, img_path):
        try:
            with Image.open(img_path) as img:
                # Copy the image into memory and close the file handle immediately.
                # This prevents "Permission Denied" errors on Windows when ffmpeg tries to overwrite it.
                img_copy = img.copy()

            # Resize image to fit the preview panel while maintaining aspect ratio (e.g. max height 640)
            img_copy.thumbnail((360, 640))
            ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=(img_copy.width, img_copy.height))
            self.lbl_preview_img.configure(image=ctk_img, text="")
            self.current_preview_image = ctk_img # keep reference
        except Exception as e:
            self.lbl_preview_img.configure(text=f"Error loading preview: {e}")

    def start_generation(self):
        video = self.video_path.get()
        audio = self.audio_path.get()
        output = self.output_path.get()

        if not video or not audio or not output:
            messagebox.showwarning("Missing Files", "Please select input video, input audio, and output destination.")
            return

        self.btn_generate.configure(state="disabled")
        self.log("\n--- Starting Process ---")

        params = self.get_style_params()
        threading.Thread(target=self.process_video, args=(video, audio, output, params), daemon=True).start()

    def process_video(self, video_path, audio_path, output_path, style_params):
        temp_ass_path = "temp_lyrics.ass"

        self.log("Step 1/2: Transcribing audio and grouping lyrics...")
        chunks = transcribe_audio(audio_path, model_size=self.model_size.get())

        if not chunks:
            self.log("ERROR: Failed to transcribe audio or audio is empty.")
            self.after(0, self.finish_process)
            return

        generate_ass_file(chunks, temp_ass_path, style_params)

        self.log("Step 2/2: Burning lyrics into video and adding audio track... (This may take a while)")
        success_video = generate_final_video(video_path, audio_path, temp_ass_path, output_path)

        if not success_video:
            self.log("ERROR: Failed to generate the final video.")
        else:
            self.log(f"SUCCESS! Video saved to:\n{output_path}")

        if os.path.exists(temp_ass_path):
            try: os.remove(temp_ass_path)
            except: pass

        self.after(0, self.finish_process)

    def finish_process(self):
        self.btn_generate.configure(state="normal")
        self.log("--- Process Finished ---")

if __name__ == "__main__":
    app = App()
    app.mainloop()
