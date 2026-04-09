import os
import threading
from tkinter import filedialog, messagebox, colorchooser
import customtkinter as ctk
from PIL import Image

from engine import transcribe_audio, generate_ass_file, generate_preview_frame, generate_final_video

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Lyrics Video Generator")
        self.geometry("1000x700")

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
        self.animation = ctk.StringVar(value="Fade")

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
            "animation": self.animation.get()
        }

    def on_style_change(self, *args):
        # Debounce the preview update
        if self.preview_debounce_timer is not None:
            self.after_cancel(self.preview_debounce_timer)
        self.preview_debounce_timer = self.after(500, self.update_preview)

    def create_widgets(self):
        # Main layout: 2 columns. Left: Controls, Right: Preview
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Panel (Controls)
        panel_controls = ctk.CTkScrollableFrame(self)
        panel_controls.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Title
        title_label = ctk.CTkLabel(panel_controls, text="Auto Lyrics Video", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(10, 20))

        # Files Section
        frame_files = ctk.CTkFrame(panel_controls)
        frame_files.pack(fill="x", pady=5)

        # Video
        lbl_video = ctk.CTkLabel(frame_files, text="1. Video:")
        lbl_video.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ent_video = ctk.CTkEntry(frame_files, textvariable=self.video_path, width=200, state="readonly")
        ent_video.grid(row=0, column=1, padx=5, pady=5)
        btn_video = ctk.CTkButton(frame_files, text="Browse", width=60, command=self.browse_video)
        btn_video.grid(row=0, column=2, padx=5, pady=5)

        # Audio
        lbl_audio = ctk.CTkLabel(frame_files, text="2. Audio:")
        lbl_audio.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ent_audio = ctk.CTkEntry(frame_files, textvariable=self.audio_path, width=200, state="readonly")
        ent_audio.grid(row=1, column=1, padx=5, pady=5)
        btn_audio = ctk.CTkButton(frame_files, text="Browse", width=60, command=self.browse_audio)
        btn_audio.grid(row=1, column=2, padx=5, pady=5)

        # Style Section
        frame_style = ctk.CTkFrame(panel_controls)
        frame_style.pack(fill="x", pady=15)

        lbl_style_title = ctk.CTkLabel(frame_style, text="Style Customization", font=ctk.CTkFont(weight="bold"))
        lbl_style_title.grid(row=0, column=0, columnspan=2, pady=5)

        # Font
        lbl_font = ctk.CTkLabel(frame_style, text="Font:")
        lbl_font.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        opt_font = ctk.CTkOptionMenu(frame_style, variable=self.font_name, values=["Arial", "Impact", "Verdana", "Comic Sans MS", "Times New Roman"], command=self.on_style_change)
        opt_font.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Size
        lbl_size = ctk.CTkLabel(frame_style, text="Size:")
        lbl_size.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        sld_size = ctk.CTkSlider(frame_style, variable=self.font_size, from_=50, to=250, command=self.on_style_change)
        sld_size.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # Color
        lbl_color = ctk.CTkLabel(frame_style, text="Color:")
        lbl_color.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.btn_color = ctk.CTkButton(frame_style, text="Pick Color", fg_color=self.primary_color_hex.get(), command=self.pick_color)
        self.btn_color.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        # Alignment
        lbl_align = ctk.CTkLabel(frame_style, text="Position:")
        lbl_align.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        opt_align = ctk.CTkOptionMenu(frame_style, variable=self.alignment, values=["Top", "Center", "Bottom"], command=self.on_style_change)
        opt_align.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

        # Animation
        lbl_anim = ctk.CTkLabel(frame_style, text="Animation:")
        lbl_anim.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        opt_anim = ctk.CTkOptionMenu(frame_style, variable=self.animation, values=["None", "Fade", "Zoom In", "Slide Up", "Slide Down"], command=self.on_style_change)
        opt_anim.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

        # Outline & Shadow
        lbl_outline = ctk.CTkLabel(frame_style, text="Outline:")
        lbl_outline.grid(row=6, column=0, padx=10, pady=5, sticky="w")
        sld_outline = ctk.CTkSlider(frame_style, variable=self.outline_width, from_=0, to=20, command=self.on_style_change)
        sld_outline.grid(row=6, column=1, padx=10, pady=5, sticky="ew")

        lbl_shadow = ctk.CTkLabel(frame_style, text="Shadow:")
        lbl_shadow.grid(row=7, column=0, padx=10, pady=5, sticky="w")
        sld_shadow = ctk.CTkSlider(frame_style, variable=self.shadow_width, from_=0, to=20, command=self.on_style_change)
        sld_shadow.grid(row=7, column=1, padx=10, pady=5, sticky="ew")

        # Output Section
        frame_out = ctk.CTkFrame(panel_controls)
        frame_out.pack(fill="x", pady=5)

        lbl_output = ctk.CTkLabel(frame_out, text="3. Output:")
        lbl_output.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ent_output = ctk.CTkEntry(frame_out, textvariable=self.output_path, width=200, state="readonly")
        ent_output.grid(row=0, column=1, padx=5, pady=5)
        btn_output = ctk.CTkButton(frame_out, text="Save As", width=60, command=self.browse_output)
        btn_output.grid(row=0, column=2, padx=5, pady=5)

        self.btn_generate = ctk.CTkButton(panel_controls, text="Generate Video", command=self.start_generation, font=ctk.CTkFont(size=16, weight="bold"), height=40)
        self.btn_generate.pack(pady=20)

        # Log
        self.textbox_log = ctk.CTkTextbox(panel_controls, height=100)
        self.textbox_log.pack(fill="x", pady=10)
        self.textbox_log.insert("0.0", "Logs will appear here...\n")
        self.textbox_log.configure(state="disabled")

        # Right Panel (Preview)
        panel_preview = ctk.CTkFrame(self)
        panel_preview.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        lbl_prev_title = ctk.CTkLabel(panel_preview, text="Live Preview", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_prev_title.pack(pady=10)

        self.lbl_preview_img = ctk.CTkLabel(panel_preview, text="Select a video to see preview", bg_color="gray20", width=360, height=640)
        self.lbl_preview_img.pack(pady=10)

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
            img = Image.open(img_path)
            # Resize image to fit the preview panel while maintaining aspect ratio (e.g. max height 640)
            img.thumbnail((360, 640))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
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
