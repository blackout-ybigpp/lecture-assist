import streamlit as st
import asyncio
import websockets
import sounddevice as sd
import numpy as np
from io import BytesIO
import wave

# Streamlit UI
st.title("Real-Time Voice Input with Streamlit")
st.text("Press the button to start recording your voice.")

# Parameters
SAMPLE_RATE = 16000  # 48 kHz
CHANNELS = 1  # Mono audio
DURATION = 5  # Duration for testing purposes (in seconds)
BUFFER_SIZE = 1024  # Buffer size for WebSocket streaming
SERVER_URL = "ws://localhost:8000/stream"  # Replace with your backend WebSocket server URL

# Audio Recording Function
def record_audio():
    st.write("Recording...")
    audio_data = BytesIO()

    def callback(indata, frames, time, status):
        audio_data.write(indata.tobytes())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback):
        sd.sleep(int(DURATION * 1000))

    audio_data.seek(0)
    return audio_data

# WebSocket Stream Function
async def stream_audio_to_server(audio_data):
    async with websockets.connect(SERVER_URL) as websocket:
        # Read audio data in chunks and send to server
        while chunk := audio_data.read(BUFFER_SIZE):
            await websocket.send(chunk)

        # End of audio stream
        await websocket.send(b"END")

        # Receive response
        response = await websocket.recv()
        st.text(f"Transcription from server: {response}")

# Button to Start Recording
if st.button("Start Recording"):
    audio_data = record_audio()
    st.text("Audio recording finished.")

    # Send audio data to the server
    asyncio.run(stream_audio_to_server(audio_data))
