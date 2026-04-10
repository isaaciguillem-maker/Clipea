import os
import threading
from tkinter import filedialog, messagebox, colorchooser
import pygame
import cv2
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk

from engine import transcribe_audio, generate_ass_file, generate_preview_frame, generate_final_video

ctk.set_appearance_mode("Light")

# We will define custom colors for orange accents manually on widgets
# Base background: #F5F6FA (light grayish blue)
# Sidebar: #FFFFFF (white)
# Accent: #FF6B00 (vibrant orange)

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        pygame.mixer.init()

        self.title("Auto Lyrics Video Generator")
        self.geometry("1200x800")
        self.configure(fg_color="#F5F6FA")

        # State Variables
        self.current_phase = ctk.StringVar(value="Upload")
        self.video_path = ctk.StringVar()
        self.audio_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.model_size = ctk.StringVar(value="medium")

        # Style Variables (Persisted across phases)
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
        self.video_cap = None
        self.video_timer = None
        self.is_playing_video = False
        self.is_playing_audio = False

        self.create_widgets()
        self.show_phase("Upload")

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

    def change_phase(self, phase_name):
        # Validation before leaving Upload
        if phase_name in ["Customize", "Export"]:
            if not self.video_path.get() or not self.audio_path.get():
                messagebox.showwarning("Missing Files", "Please load both valid Audio and Video files before proceeding.")
                return

        self.show_phase(phase_name)

    def show_phase(self, phase_name):
        self.current_phase.set(phase_name)

        # Stop media players if switching phases
        self.is_playing_video = False
        self.is_playing_audio = False
        pygame.mixer.music.stop()

        # Update Top Bar UI
        self.btn_nav_upload.configure(fg_color=self.color_accent if phase_name == "Upload" else "transparent", text_color="white" if phase_name == "Upload" else self.color_text)
        self.btn_nav_customize.configure(fg_color=self.color_accent if phase_name == "Customize" else "transparent", text_color="white" if phase_name == "Customize" else self.color_text)
        self.btn_nav_export.configure(fg_color=self.color_accent if phase_name == "Export" else "transparent", text_color="white" if phase_name == "Export" else self.color_text)

        # Hide all phases
        self.phase_upload.grid_remove()
        self.phase_customize.grid_remove()
        self.phase_export.grid_remove()

        # Show target phase
        if phase_name == "Upload":
            self.phase_upload.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        elif phase_name == "Customize":
            self.phase_customize.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
            self.update_preview() # Ensure preview reflects current state
        elif phase_name == "Export":
            self.phase_export.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
            self.update_export_summary()

    def create_widgets(self):
        # Base colors
        self.color_accent = "#FF6B00"
        self.color_accent_hover = "#E65A00"
        self.color_panel = "#FFFFFF"
        self.color_bg = "#F5F6FA"
        self.color_text = "#333333"

        # Main layout: Row 0: Top Bar, Row 1: Active Phase Content
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.create_top_bar()

        # Container for phases
        self.phase_upload = self.create_phase_upload()
        self.phase_customize = self.create_phase_customize()
        self.phase_export = self.create_phase_export()

    def create_phase_upload(self):
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid_rowconfigure(0, weight=1)
        main_content.grid_columnconfigure(0, weight=1)
        main_content.grid_columnconfigure(1, weight=1)

        # Left Column: Upload Zones
        left_col = ctk.CTkFrame(main_content, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)

        lbl_upload_title = ctk.CTkLabel(left_col, text="Upload Media", font=ctk.CTkFont(size=24, weight="bold"), text_color=self.color_text)
        lbl_upload_title.pack(anchor="w", pady=(0, 20))

        # Audio Upload Zone
        self.frame_drop_audio = ctk.CTkFrame(left_col, height=150, fg_color=self.color_panel, border_width=2, border_color="#DDDDDD", corner_radius=10)
        self.frame_drop_audio.pack(fill="x", pady=10)
        self.frame_drop_audio.pack_propagate(False)
        self.frame_drop_audio.drop_target_register(DND_FILES)
        self.frame_drop_audio.dnd_bind('<<Drop>>', self.on_drop_audio)

        lbl_audio_icon = ctk.CTkLabel(self.frame_drop_audio, text="🎵", font=ctk.CTkFont(size=40))
        lbl_audio_icon.pack(pady=(20, 5))
        self.lbl_audio_status = ctk.CTkLabel(self.frame_drop_audio, text="Drag & Drop Audio here\n(.mp3, .wav)", text_color=self.color_text)
        self.lbl_audio_status.pack()
        btn_browse_a = ctk.CTkButton(self.frame_drop_audio, text="Browse Audio", width=100, fg_color="#E0E0E0", text_color=self.color_text, hover_color="#D0D0D0", command=self.browse_audio)
        btn_browse_a.pack(pady=10)

        # Video Upload Zone
        self.frame_drop_video = ctk.CTkFrame(left_col, height=150, fg_color=self.color_panel, border_width=2, border_color="#DDDDDD", corner_radius=10)
        self.frame_drop_video.pack(fill="x", pady=20)
        self.frame_drop_video.pack_propagate(False)
        self.frame_drop_video.drop_target_register(DND_FILES)
        self.frame_drop_video.dnd_bind('<<Drop>>', self.on_drop_video)

        lbl_video_icon = ctk.CTkLabel(self.frame_drop_video, text="🎞️", font=ctk.CTkFont(size=40))
        lbl_video_icon.pack(pady=(20, 5))
        self.lbl_video_status = ctk.CTkLabel(self.frame_drop_video, text="Drag & Drop Video here\n(.mp4, .mov)", text_color=self.color_text)
        self.lbl_video_status.pack()
        btn_browse_v = ctk.CTkButton(self.frame_drop_video, text="Browse Video", width=100, fg_color="#E0E0E0", text_color=self.color_text, hover_color="#D0D0D0", command=self.browse_video)
        btn_browse_v.pack(pady=10)

        # Right Column: Previews
        right_col = ctk.CTkFrame(main_content, fg_color=self.color_panel, corner_radius=10)
        right_col.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        lbl_preview_title = ctk.CTkLabel(right_col, text="Media Verification", font=ctk.CTkFont(size=18, weight="bold"), text_color=self.color_text)
        lbl_preview_title.pack(pady=10)

        # Video Player Area
        self.lbl_video_player = ctk.CTkLabel(right_col, text="No video loaded", bg_color="gray90", width=240, height=426, text_color="#888888")
        self.lbl_video_player.pack(pady=10)

        self.btn_play_video = ctk.CTkButton(right_col, text="▶ Play Video", state="disabled", command=self.toggle_video_play)
        self.btn_play_video.pack(pady=5)

        # Audio Player Area
        self.btn_play_audio = ctk.CTkButton(right_col, text="▶ Play Audio", state="disabled", command=self.toggle_audio_play)
        self.btn_play_audio.pack(pady=20)

        # Continue Button
        btn_continue = ctk.CTkButton(left_col, text="Continue to Customize ➔", font=ctk.CTkFont(weight="bold", size=16), height=50, fg_color=self.color_accent, hover_color=self.color_accent_hover, command=lambda: self.change_phase("Customize"))
        btn_continue.pack(side="bottom", fill="x", pady=20)

        return main_content

    def on_drop_audio(self, event):
        filepath = event.data.strip('{}')
        if filepath.lower().endswith(('.mp3', '.wav', '.m4a')):
            self.audio_path.set(filepath)
            self.lbl_audio_status.configure(text=f"Loaded: {os.path.basename(filepath)}")
            self.frame_drop_audio.configure(border_color="#4CAF50") # Green success
            self.btn_play_audio.configure(state="normal")
            try:
                pygame.mixer.music.load(filepath)
            except:
                pass
        else:
            messagebox.showerror("Invalid File", "Please drop a valid audio file.")

    def on_drop_video(self, event):
        filepath = event.data.strip('{}')
        if filepath.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            self.video_path.set(filepath)
            self.lbl_video_status.configure(text=f"Loaded: {os.path.basename(filepath)}")
            self.frame_drop_video.configure(border_color="#4CAF50") # Green success
            self.load_video_preview(filepath)
        else:
            messagebox.showerror("Invalid File", "Please drop a valid video file.")

    def browse_video(self):
        filename = filedialog.askopenfilename(title="Select Video", filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if filename:
            self.on_drop_video(type('Event', (), {'data': filename}))

    def browse_audio(self):
        filename = filedialog.askopenfilename(title="Select Audio", filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if filename:
            self.on_drop_audio(type('Event', (), {'data': filename}))

    def load_video_preview(self, filepath):
        if self.video_cap:
            self.video_cap.release()
        self.video_cap = cv2.VideoCapture(filepath)
        self.btn_play_video.configure(state="normal")
        self.show_video_frame()

    def show_video_frame(self):
        if not self.video_cap or not self.video_cap.isOpened():
            return
        ret, frame = self.video_cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame)
            img.thumbnail((240, 426))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
            self.lbl_video_player.configure(image=ctk_img, text="")
            self.current_preview_image = ctk_img

        if self.is_playing_video:
            fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            delay = int(1000 / fps) if fps > 0 else 30
            self.video_timer = self.after(delay, self.show_video_frame)
        else:
            if not ret: # Loop video or stop at end
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def toggle_video_play(self):
        if self.is_playing_video:
            self.is_playing_video = False
            self.btn_play_video.configure(text="▶ Play Video")
            if self.video_timer:
                self.after_cancel(self.video_timer)
        else:
            self.is_playing_video = True
            self.btn_play_video.configure(text="⏸ Pause Video")
            self.show_video_frame()

    def toggle_audio_play(self):
        if self.is_playing_audio:
            self.is_playing_audio = False
            pygame.mixer.music.pause()
            self.btn_play_audio.configure(text="▶ Play Audio")
        else:
            self.is_playing_audio = True
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.play()
            else:
                pygame.mixer.music.unpause()
            self.btn_play_audio.configure(text="⏸ Pause Audio")

    def create_top_bar(self):
        top_bar = ctk.CTkFrame(self, height=60, fg_color=self.color_panel, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        # Logo / Title
        lbl_title = ctk.CTkLabel(top_bar, text="Auto Lyrics Video", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.color_text)
        lbl_title.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        # Navigation
        frame_nav = ctk.CTkFrame(top_bar, fg_color="transparent")
        frame_nav.grid(row=0, column=1, pady=10)

        self.btn_nav_upload = ctk.CTkButton(frame_nav, text="1. Upload", font=ctk.CTkFont(weight="bold"), fg_color="transparent", text_color=self.color_text, hover_color="#E0E0E0", command=lambda: self.change_phase("Upload"))
        self.btn_nav_upload.pack(side="left", padx=5)

        self.btn_nav_customize = ctk.CTkButton(frame_nav, text="2. Customize", font=ctk.CTkFont(weight="bold"), fg_color="transparent", text_color=self.color_text, hover_color="#E0E0E0", command=lambda: self.change_phase("Customize"))
        self.btn_nav_customize.pack(side="left", padx=5)

        self.btn_nav_export = ctk.CTkButton(frame_nav, text="3. Export", font=ctk.CTkFont(weight="bold"), fg_color="transparent", text_color=self.color_text, hover_color="#E0E0E0", command=lambda: self.change_phase("Export"))
        self.btn_nav_export.pack(side="left", padx=5)

    def create_phase_export(self):
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid_rowconfigure(0, weight=1)
        main_content.grid_columnconfigure(0, weight=1)

        center_col = ctk.CTkFrame(main_content, width=600, fg_color=self.color_panel, corner_radius=15)
        center_col.grid(row=0, column=0, pady=40, padx=40)
        center_col.grid_propagate(False) # Keep fixed size
        center_col.configure(height=600, width=500)

        lbl_title = ctk.CTkLabel(center_col, text="Export & Generate", font=ctk.CTkFont(size=24, weight="bold"), text_color=self.color_text)
        lbl_title.pack(pady=(30, 20))

        # Project Summary Area
        frame_summary = ctk.CTkFrame(center_col, fg_color=self.color_bg, corner_radius=10)
        frame_summary.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(frame_summary, text="Project Summary", font=ctk.CTkFont(weight="bold"), text_color=self.color_text).pack(pady=(10, 5))

        self.lbl_sum_video = ctk.CTkLabel(frame_summary, text="Video: Not Loaded", text_color=self.color_text)
        self.lbl_sum_video.pack()
        self.lbl_sum_audio = ctk.CTkLabel(frame_summary, text="Audio: Not Loaded", text_color=self.color_text)
        self.lbl_sum_audio.pack(pady=(0, 10))

        # Export Settings Area
        frame_settings = ctk.CTkFrame(center_col, fg_color=self.color_bg, corner_radius=10)
        frame_settings.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(frame_settings, text="Export Destination", font=ctk.CTkFont(weight="bold"), text_color=self.color_text).pack(pady=(10, 5))

        self.lbl_export_dest = ctk.CTkLabel(frame_settings, text="No destination selected", text_color="#888888")
        self.lbl_export_dest.pack()

        btn_browse_out = ctk.CTkButton(frame_settings, text="Browse Destination", fg_color="#E0E0E0", text_color=self.color_text, hover_color="#D0D0D0", command=self.browse_output)
        btn_browse_out.pack(pady=(5, 10))

        # Status & Progress
        self.lbl_status = ctk.CTkLabel(center_col, text="Ready to generate.", font=ctk.CTkFont(size=14), text_color=self.color_text)
        self.lbl_status.pack(pady=(20, 5))

        self.progress_bar = ctk.CTkProgressBar(center_col, progress_color=self.color_accent, width=400)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)

        # Generate Button
        self.btn_generate_final = ctk.CTkButton(center_col, text="Generate Video", font=ctk.CTkFont(size=18, weight="bold"), height=60, fg_color=self.color_accent, hover_color=self.color_accent_hover, command=self.start_generation)
        self.btn_generate_final.pack(pady=30)

        return main_content

    def update_export_summary(self):
        vid_name = os.path.basename(self.video_path.get()) if self.video_path.get() else "Not Loaded"
        aud_name = os.path.basename(self.audio_path.get()) if self.audio_path.get() else "Not Loaded"
        self.lbl_sum_video.configure(text=f"Video: {vid_name}")
        self.lbl_sum_audio.configure(text=f"Audio: {aud_name}")

    def create_phase_customize(self):
        main_content = ctk.CTkFrame(self, fg_color="transparent")
        main_content.grid_rowconfigure(0, weight=1)
        main_content.grid_columnconfigure(0, weight=0) # Left sidebar
        main_content.grid_columnconfigure(1, weight=1) # Center preview
        main_content.grid_columnconfigure(2, weight=0) # Right sidebar

        # ==========================================
        # LEFT SIDEBAR: Presets
        # ==========================================
        left_panel = ctk.CTkFrame(main_content, width=200, fg_color=self.color_panel, corner_radius=10)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_panel.grid_propagate(False)

        lbl_presets = ctk.CTkLabel(left_panel, text="Presets", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.color_text)
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
        preview_container = ctk.CTkFrame(center_panel, fg_color=self.color_panel, corner_radius=15)
        preview_container.pack(expand=True)

        self.lbl_preview_img = ctk.CTkLabel(preview_container, text="Select a video to see preview", bg_color="gray90", text_color="#888888", width=360, height=640)
        self.lbl_preview_img.pack(padx=20, pady=20)

        # ==========================================
        # RIGHT SIDEBAR: Customization
        # ==========================================
        right_panel = ctk.CTkScrollableFrame(main_content, width=320, fg_color=self.color_panel, corner_radius=10)
        right_panel.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        lbl_style_title = ctk.CTkLabel(right_panel, text="Style Customization", font=ctk.CTkFont(size=16, weight="bold"), text_color=self.color_text)
        lbl_style_title.pack(pady=20, padx=20, anchor="w")

        # Font
        frame_font = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_font.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_font, text="Font", text_color=self.color_text).pack(anchor="w")
        opt_font = ctk.CTkOptionMenu(frame_font, variable=self.font_name, values=["Arial", "Impact", "Verdana", "Comic Sans MS", "Times New Roman"], fg_color="#F0F0F0", text_color=self.color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_font.pack(fill="x", pady=(5,0))

        # Size
        frame_size = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_size.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_size, text="Size", text_color=self.color_text).pack(anchor="w")
        sld_size = ctk.CTkSlider(frame_size, variable=self.font_size, from_=50, to=250, button_color=self.color_accent, button_hover_color=self.color_accent_hover, progress_color=self.color_accent, command=self.on_style_change)
        sld_size.pack(fill="x", pady=(5,0))

        # Color
        frame_color = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_color.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_color, text="Primary Color", text_color=self.color_text).pack(anchor="w")
        self.btn_color = ctk.CTkButton(frame_color, text="Pick Color", fg_color=self.primary_color_hex.get(), text_color="black", border_width=1, border_color="#CCCCCC", command=self.pick_color)
        self.btn_color.pack(fill="x", pady=(5,0))

        # Alignment
        frame_align = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_align.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_align, text="Position", text_color=self.color_text).pack(anchor="w")
        opt_align = ctk.CTkOptionMenu(frame_align, variable=self.alignment, values=["Top", "Center", "Bottom"], fg_color="#F0F0F0", text_color=self.color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_align.pack(fill="x", pady=(5,0))

        # Animations
        frame_anim = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_anim.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame_anim, text="Entry Anim", text_color=self.color_text).pack(anchor="w")
        opt_anim_in = ctk.CTkOptionMenu(frame_anim, variable=self.entry_animation, values=["None", "Fade", "Zoom In", "Slide Up", "Slide Down"], fg_color="#F0F0F0", text_color=self.color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_anim_in.pack(fill="x", pady=(5,10))

        ctk.CTkLabel(frame_anim, text="Exit Anim", text_color=self.color_text).pack(anchor="w")
        opt_anim_out = ctk.CTkOptionMenu(frame_anim, variable=self.exit_animation, values=["None", "Fade", "Zoom Out", "Slide Up", "Slide Down"], fg_color="#F0F0F0", text_color=self.color_text, button_color="#E0E0E0", button_hover_color="#D0D0D0", command=self.on_style_change)
        opt_anim_out.pack(fill="x", pady=(5,0))

        # Outline & Shadow
        frame_fx = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_fx.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(frame_fx, text="Outline Width", text_color=self.color_text).pack(anchor="w")
        sld_outline = ctk.CTkSlider(frame_fx, variable=self.outline_width, from_=0, to=20, button_color=self.color_accent, button_hover_color=self.color_accent_hover, progress_color=self.color_accent, command=self.on_style_change)
        sld_outline.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(frame_fx, text="Shadow Width", text_color=self.color_text).pack(anchor="w")
        sld_shadow = ctk.CTkSlider(frame_fx, variable=self.shadow_width, from_=0, to=20, button_color=self.color_accent, button_hover_color=self.color_accent_hover, progress_color=self.color_accent, command=self.on_style_change)
        sld_shadow.pack(fill="x", pady=(0, 5))

        # Checkbox
        chk_upper = ctk.CTkCheckBox(right_panel, text="ALL UPPERCASE", variable=self.uppercase, text_color=self.color_text, fg_color=self.color_accent, hover_color=self.color_accent_hover, command=self.on_style_change)
        chk_upper.pack(padx=20, pady=15, anchor="w")

        # Sync Offset
        frame_offset = ctk.CTkFrame(right_panel, fg_color="transparent")
        frame_offset.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame_offset, text="Sync Offset", text_color=self.color_text).pack(anchor="w")

        offset_inner = ctk.CTkFrame(frame_offset, fg_color="transparent")
        offset_inner.pack(fill="x")
        self.lbl_offset_val = ctk.CTkLabel(offset_inner, text="0 ms", width=50, text_color=self.color_text)
        self.lbl_offset_val.pack(side="right", padx=5)
        sld_offset = ctk.CTkSlider(offset_inner, variable=self.sync_offset_ms, from_=-1000, to=1000, button_color=self.color_accent, button_hover_color=self.color_accent_hover, progress_color=self.color_accent, command=self.on_offset_change)
        sld_offset.pack(side="left", fill="x", expand=True)

        # Log Textbox (hidden until needed, but we keep it small at the bottom)
        self.textbox_log = ctk.CTkTextbox(right_panel, height=80, fg_color="#F0F0F0", text_color=self.color_text)
        self.textbox_log.pack(fill="x", padx=20, pady=20)
        self.textbox_log.insert("0.0", "Logs...\n")
        self.textbox_log.configure(state="disabled")

        # Continue Button
        btn_continue = ctk.CTkButton(right_panel, text="Continue to Export ➔", font=ctk.CTkFont(weight="bold", size=16), height=50, fg_color=self.color_accent, hover_color=self.color_accent_hover, command=lambda: self.change_phase("Export"))
        btn_continue.pack(fill="x", padx=20, pady=10)

        return main_content

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
            self.lbl_export_dest.configure(text=os.path.basename(filename))

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
            messagebox.showwarning("Missing Export Destination", "Please browse and select an output destination for the video.")
            return

        self.btn_generate_final.configure(state="disabled")
        self.lbl_status.configure(text="Processing (Step 1/2): Transcribing audio with AI...", text_color="#FF6B00")
        self.progress_bar.set(0.1)

        params = self.get_style_params()
        threading.Thread(target=self.process_video, args=(video, audio, output, params), daemon=True).start()

    def process_video(self, video_path, audio_path, output_path, style_params):
        temp_ass_path = "temp_lyrics.ass"

        # Transcription
        chunks = transcribe_audio(audio_path, model_size=self.model_size.get())

        if not chunks:
            self.after(0, lambda: self.lbl_status.configure(text="ERROR: Failed to transcribe audio.", text_color="red"))
            self.after(0, self.finish_process)
            return

        self.after(0, lambda: self.progress_bar.set(0.5))
        self.after(0, lambda: self.lbl_status.configure(text="Processing (Step 2/2): Burning lyrics into video..."))

        generate_ass_file(chunks, temp_ass_path, style_params)

        success_video = generate_final_video(video_path, audio_path, temp_ass_path, output_path)

        if not success_video:
            self.after(0, lambda: self.lbl_status.configure(text="ERROR: Failed to generate final video.", text_color="red"))
        else:
            self.after(0, lambda: self.lbl_status.configure(text=f"SUCCESS! Video saved to: {os.path.basename(output_path)}", text_color="#4CAF50"))
            self.after(0, lambda: self.progress_bar.set(1.0))

        if os.path.exists(temp_ass_path):
            try: os.remove(temp_ass_path)
            except: pass

        self.after(0, self.finish_process)

    def finish_process(self):
        self.btn_generate_final.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
