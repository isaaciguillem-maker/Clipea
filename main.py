import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from engine import transcribe_audio_to_ass, generate_final_video

# Basic configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Auto Lyrics Video Generator")
        self.geometry("600x600")

        # Variables to store file paths
        self.video_path = ctk.StringVar()
        self.audio_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        self.model_size = ctk.StringVar(value="medium")

        # UI Elements
        self.create_widgets()

    def create_widgets(self):
        # Title
        title_label = ctk.CTkLabel(self, text="Auto Lyrics Video Generator", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=20)

        # File selection frame
        frame_files = ctk.CTkFrame(self)
        frame_files.pack(pady=10, padx=20, fill="x")

        # Video Input
        lbl_video = ctk.CTkLabel(frame_files, text="Input Video:")
        lbl_video.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        ent_video = ctk.CTkEntry(frame_files, textvariable=self.video_path, width=300, state="readonly")
        ent_video.grid(row=0, column=1, padx=10, pady=10)
        btn_video = ctk.CTkButton(frame_files, text="Browse", command=self.browse_video)
        btn_video.grid(row=0, column=2, padx=10, pady=10)

        # Audio Input
        lbl_audio = ctk.CTkLabel(frame_files, text="Input Audio:")
        lbl_audio.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ent_audio = ctk.CTkEntry(frame_files, textvariable=self.audio_path, width=300, state="readonly")
        ent_audio.grid(row=1, column=1, padx=10, pady=10)
        btn_audio = ctk.CTkButton(frame_files, text="Browse", command=self.browse_audio)
        btn_audio.grid(row=1, column=2, padx=10, pady=10)

        # Output File
        lbl_output = ctk.CTkLabel(frame_files, text="Output Video:")
        lbl_output.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        ent_output = ctk.CTkEntry(frame_files, textvariable=self.output_path, width=300, state="readonly")
        ent_output.grid(row=2, column=1, padx=10, pady=10)
        btn_output = ctk.CTkButton(frame_files, text="Save As", command=self.browse_output)
        btn_output.grid(row=2, column=2, padx=10, pady=10)

        # Options frame
        frame_options = ctk.CTkFrame(self)
        frame_options.pack(pady=10, padx=20, fill="x")

        lbl_model = ctk.CTkLabel(frame_options, text="Whisper Model:")
        lbl_model.grid(row=0, column=0, padx=10, pady=10)
        opt_model = ctk.CTkOptionMenu(frame_options, variable=self.model_size, values=["tiny", "base", "small", "medium", "large-v3"])
        opt_model.grid(row=0, column=1, padx=10, pady=10)

        # Generate Button
        self.btn_generate = ctk.CTkButton(self, text="Generate Video", command=self.start_generation, font=ctk.CTkFont(size=16, weight="bold"), height=50)
        self.btn_generate.pack(pady=20)

        # Status / Log Box
        self.textbox_log = ctk.CTkTextbox(self, width=560, height=150)
        self.textbox_log.pack(pady=10, padx=20)
        self.textbox_log.insert("0.0", "Welcome! Select files and click Generate.\n")
        self.textbox_log.configure(state="disabled")

    def log(self, message):
        # Schedule GUI updates safely on the main thread
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

    def browse_audio(self):
        filename = filedialog.askopenfilename(title="Select Audio", filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if filename:
            self.audio_path.set(filename)

    def browse_output(self):
        filename = filedialog.asksaveasfilename(title="Save Output Video", defaultextension=".mp4", filetypes=[("MP4 Video", "*.mp4")])
        if filename:
            self.output_path.set(filename)

    def start_generation(self):
        video = self.video_path.get()
        audio = self.audio_path.get()
        output = self.output_path.get()

        if not video or not audio or not output:
            messagebox.showwarning("Missing Files", "Please select input video, input audio, and output destination.")
            return

        self.btn_generate.configure(state="disabled")
        self.log("\n--- Starting Process ---")

        # Run in a separate thread to prevent GUI freezing
        threading.Thread(target=self.process_video, args=(video, audio, output), daemon=True).start()

    def process_video(self, video_path, audio_path, output_path):
        temp_ass_path = "temp_lyrics.ass"

        self.log("Step 1/2: Transcribing audio and generating lyrics...")
        success_transcription = transcribe_audio_to_ass(audio_path, temp_ass_path, model_size=self.model_size.get())

        if not success_transcription:
            self.log("ERROR: Failed to transcribe audio.")
            self.after(0, self.finish_process)
            return

        self.log("Step 2/2: Burning lyrics into video and adding audio track... (This may take a while)")
        success_video = generate_final_video(video_path, audio_path, temp_ass_path, output_path)

        if not success_video:
            self.log("ERROR: Failed to generate the final video.")
        else:
            self.log(f"SUCCESS! Video saved to:\n{output_path}")

        # Cleanup temp file
        if os.path.exists(temp_ass_path):
            try:
                os.remove(temp_ass_path)
            except:
                pass

        self.after(0, self.finish_process)

    def finish_process(self):
        self.btn_generate.configure(state="normal")
        self.log("--- Process Finished ---")

if __name__ == "__main__":
    app = App()
    app.mainloop()
