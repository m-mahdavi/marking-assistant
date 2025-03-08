import os
import io
import time
import wave
import json
import tkinter as tk
import tkinter.filedialog
import streamlit as st
import streamlit_pdf_viewer
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
if "prompt" not in st.session_state:
    st.session_state.prompt = "Using the transcript below, generate a concise and constructive feedback for the student submission. Focus solely on the feedback, avoiding any metadata or additional commentary. Ensure the tone is formal, objective, and humanized, with no emotional language. Below is the transcript: "
if "reset_widgets" not in st.session_state:
    st.session_state.reset_widgets = False

# Expand Streamlit layout to full width
st.set_page_config(layout="wide")


# Reset widget values
def reset_widget_values():
    if st.session_state.reset_widgets:
        st.session_state.feedback_text = ""
        st.session_state.code_mark = ""
        st.session_state.text_mark = ""
        st.session_state.total_mark = ""
        st.session_state.reset_widgets = False


# Folder picker
def select_folder():
    root = tk.Tk()
    root.withdraw()
    folder_selected = tkinter.filedialog.askdirectory()
    if folder_selected:
        st.session_state.folder_path = folder_selected
        load_files(folder_selected)


# File loader
def load_files(folder):
    if os.path.isdir(folder):
        st.session_state.file_list = sorted([f for f in os.listdir(folder) if f.endswith((".html", ".docx", ".pdf"))])
        st.session_state.file_index = 0
        st.session_state.reset_widgets = True


# Recording and Transcribing
def record_and_transcribe():
    st.write(f"🎤 Recording for {recording_length} seconds...")

    progress_bar = st.progress(0)

    def update_progress(i):
        progress_bar.progress(i)

    audio_data = sd.rec(int(recording_length * fs), samplerate=fs, channels=1, dtype="int16")
    start_time = time.time()

    while time.time() - start_time < recording_length:
        elapsed_time = time.time() - start_time
        update_progress(int((elapsed_time / recording_length) * 100))
        time.sleep(0.1)

    sd.wait()
    update_progress(100)

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
        current_text = st.session_state.get("feedback_text", "")
        st.session_state.feedback_text = current_text + text + "\n\n"
    except sr.UnknownValueError:
        st.error("⚠️ Could not understand the audio.")
    except sr.RequestError:
        st.error("⚠️ Error with the speech recognition service.")


# Feedback Generation
def generate_feedback():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(f"{st.session_state.prompt} {st.session_state.feedback_text}")
    st.session_state.feedback_text = response.text


# Save Feedback
def save_feedback():
    feedback_data = {
        "mark": {
            "code": st.session_state.code_mark,
            "text": st.session_state.text_mark,
            "total": st.session_state.total_mark
        },
        "comment": st.session_state.feedback_text
    }
    file_path = os.path.join(st.session_state.folder_path, st.session_state.file_list[st.session_state.file_index])
    json_path = file_path.replace(os.path.splitext(file_path)[1], ".json")
    with open(json_path, "w") as f:
        json.dump(feedback_data, f, indent=4)


# Display content
def display_content():
    file_path = os.path.join(st.session_state.folder_path, st.session_state.file_list[st.session_state.file_index])
    file_ext = os.path.splitext(file_path)[-1].lower()

    st.write(f"**{st.session_state.file_index + 1} / {len(st.session_state.file_list)}** | {file_path}")

    json_path = file_path.replace(os.path.splitext(file_path)[1], ".json")
    if os.path.exists(json_path):
        st.write(json.load(open(json_path)))

    if file_ext == ".html":
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        st.components.v1.html(f'<div style="max-width:1200px; margin:auto;">{html_content}</div>', height=600, scrolling=True)
    elif file_ext == ".docx":
        with open(file_path, "rb") as f:
            st.download_button("📥 Download DOCX", f, file_name=os.path.basename(file_path), mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    elif file_ext == ".pdf":
        with open(file_path, "rb") as f:
            st.download_button("📥 Download PDF", f, file_name=os.path.basename(file_path), mime="application/pdf")
        streamlit_pdf_viewer.pdf_viewer(file_path, height=1300)


# UI Layout
st.title("🎙️ Marking Assistant")

# Reset widgets at the start of each run if needed
reset_widget_values()

col1, col2 = st.columns([1, 2])

with col1:
    col11, col22, col33 = st.columns(3)
    with col11:
        if st.button("📂 Select Folder"):
            select_folder()
    with col22:
        if st.button("🎤 Start Recording"):
            record_and_transcribe()
    with col33:
        if st.button("✍️ Generate Feedback"):
            generate_feedback()

    st.text_area("📜 Prompt:", key="prompt", height=50)
    st.text_area("📜 Comments:", key="feedback_text", height=200)

    col111, col222, col333 = st.columns(3)
    with col111:
        st.text_input("🔢 Code Mark:", key="code_mark")
    with col222:
        st.text_input("📄 Text Mark:", key="text_mark")
    with col333:
        st.text_input("🏆 Total Mark:", key="total_mark")

    col1111, col2222, col3333 = st.columns(3)
    with col1111:
        if st.button("💾 Save Feedback"):
            save_feedback()
    with col2222:
        if st.button("⏮️ Previous") and st.session_state.file_index > 0:
            st.session_state.file_index -= 1
            st.session_state.reset_widgets = True
    with col3333:
        if st.button("⏭️ Next") and st.session_state.file_index < len(st.session_state.file_list) - 1:
            st.session_state.file_index += 1
            st.session_state.reset_widgets = True 
            
with col2:
    if st.session_state.file_list:
        display_content()