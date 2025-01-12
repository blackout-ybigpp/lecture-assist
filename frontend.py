import asyncio
import streamlit as st
import sounddevice as sd
import websockets

# WebSocket 서버 주소
WEBSOCKET_URL = "wss://4fd7-54-145-137-212.ngrok-free.app/socket"
USER_ID = "123"
CHANNEL_ID = "456"
TITLE = "ddf"

# 스트림 설정
SAMPLE_RATE = 16000  # 서버와 동일한 샘플링 레이트
CHANNELS = 1         # 모노
BLOCKSIZE = 1024     # 전송 블록 크기

# 스트림 상태 관리
st.title("Real-Time Audio Streaming")
st.markdown("Click **Start Streaming** to send audio to the server.")
streaming_status = st.empty()
start_button = st.button("Start Streaming")
stop_button = st.button("Stop Streaming", disabled=True)

# 스트리밍 상태
is_streaming = False

async def audio_stream(loop):
    """
    마이크 입력 데이터를 WebSocket으로 스트리밍합니다.
    """
    global is_streaming
    url_with_params = f"{WEBSOCKET_URL}?user_id={USER_ID}&channel_id={CHANNEL_ID}&title={TITLE}"

    async with websockets.connect(url_with_params) as websocket:
        # Sounddevice 콜백 함수 정의
        def callback(indata, frames, time, status):
            if is_streaming:
                asyncio.run_coroutine_threadsafe(
                    websocket.send(indata.tobytes()), loop
                )

        # 마이크 입력 스트림 시작
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback, blocksize=BLOCKSIZE, dtype="int16"
        ):
            while is_streaming:
                await asyncio.sleep(0.1)  # 짧은 대기 시간으로 이벤트 루프 유지

async def main():
    """
    WebSocket으로 오디오 스트리밍을 제어합니다.
    """
    global is_streaming
    loop = asyncio.get_event_loop()
    streaming_status.text("Starting streaming...")
    try:
        is_streaming = True
        await audio_stream(loop)
    except Exception as e:
        streaming_status.text(f"Error: {e}")
    finally:
        is_streaming = False
        streaming_status.text("Streaming stopped.")

# 버튼 클릭 이벤트 처리
if start_button:
    asyncio.run(main())
    stop_button.disabled = False
    start_button.disabled = True

if stop_button and not stop_button.disabled:
    is_streaming = False
    stop_button.disabled = True
    start_button.disabled = False
