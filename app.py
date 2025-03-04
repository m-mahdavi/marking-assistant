import os
import io
import time
import wave
import json
import tkinter as tk
import tkinter.filedialog
import streamlit as st
import sounddevice as sd
import speech_recognition as sr
import google.generativeai as genai


# Constants
fs = 44100  # Sample rate
recording_length = 20

# Initialize session state
if "file_index" not in st.session_state:
    st.session_state.file_index = 0
if "file_list" not in st.session_state:
    st.session_state.file_list = []
if "folder_path" not in st.session_state:
    st.session_state.folder_path = ""
if "transcripts" not in st.session_state:
    st.session_state.transcripts = []
if "feedback_text" not in st.session_state:
    st.session_state.feedback_text = ""

# Expand Streamlit layout to full width
st.set_page_config(layout="wide")


# Folder picker
def select_folder():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    folder_selected = tkinter.filedialog.askdirectory()
    if folder_selected:
        st.session_state.folder_path = folder_selected
        load_html_files(folder_selected)


# HTML file loader
def load_html_files(folder):
    if os.path.isdir(folder):
        st.session_state.file_list = sorted(
            [f for f in os.listdir(folder) if f.endswith(".html") and not os.path.exists(os.path.join(folder, f.replace(".html", ".json")))]
        )
        st.session_state.file_index = 0


# Recording and Transcribing
def record_and_transcribe():
    st.write(f"🎤 Recording for {recording_length} seconds...")

    # Progress bar setup
    progress_bar = st.progress(0)
    def update_progress(i):
        progress_bar.progress(i)

    # Start recording
    audio_data = sd.rec(int(recording_length * fs), samplerate=fs, channels=1, dtype="int16")
    start_time = time.time()

    while time.time() - start_time < recording_length:
        elapsed_time = time.time() - start_time
        progress = int((elapsed_time / recording_length) * 100)
        update_progress(progress)
        time.sleep(0.1)

    sd.wait()
    update_progress(100)

    # Convert audio to WAV format and transcribe
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(audio_data.tobytes())

    wav_buffer.seek(0)
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_buffer) as source:
        audio = recognizer.record(source)
    
    try:
        text = recognizer.recognize_google(audio)
        st.session_state.transcripts.append(text)
    except sr.UnknownValueError:
        st.error("⚠️ Could not understand the audio.")
    except sr.RequestError:
        st.error("⚠️ Error with the speech recognition service.")


# Feedback Generation
def generate_feedback():
    transcript = "\n".join(st.session_state.transcripts)
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(f"Use the below transcript to generate a short constructive feedback for a student submission. Here is the transcript: {transcript}")
    st.session_state.feedback_text = response.text


# Save Feedback
def save_feedback(file_path):
    feedback_dictionary = {
        "mark": {
            "code": st.session_state.code_mark,
            "text": st.session_state.text_mark,
            "total": st.session_state.total_mark
        },
        "comment": st.session_state.feedback_text
    }
    feedback_json = json.dumps(feedback_dictionary, indent=4)
    with open(file_path.replace(".html", ".json"), "w") as f:
        f.write(feedback_json)


# Display HTML content
def display_html_content(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Render HTML content with custom CSS
    custom_css = """
    <style>
        .html-container {
            width: 100%;
            max-width: 1200px;
            margin: auto;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)
    st.components.v1.html(f'<div class="html-container">{html_content}</div>', height=600, scrolling=True)


# UI Layout
st.title("🎙️ Marking Assistant")
col1, col2 = st.columns([1, 2])

with col1:
    if st.button("📂 Select Folder"):
        select_folder()
    
    if st.session_state.folder_path:
        file_path = os.path.join(st.session_state.folder_path, st.session_state.file_list[st.session_state.file_index])
        st.write(f"{file_path} ({len(st.session_state.file_list)} left)")
    
    if st.button("🎤 Start Recording"):
        record_and_transcribe()

    col11, col22 = st.columns([4, 1])
    
    with col11:
        if st.button("✍️ Generate Feedback"):
            generate_feedback()
        st.text_area("📜 Comments:", value=st.session_state.feedback_text, height=400)
    
    with col22:
        st.session_state.code_mark = st.text_input("🔢 Code Mark:", value="0")
        st.session_state.text_mark = st.text_input("📄 Text Mark:", value="0")
        st.session_state.total_mark = st.text_input("🏆 Total Mark:", value="0")
        if st.button("💾 Save Feedback"):
            save_feedback(file_path)

with col2:
    if st.session_state.file_list:
        display_html_content(file_path)
   