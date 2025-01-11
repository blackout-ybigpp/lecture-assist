import asyncio
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import logging

app = FastAPI()

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)

class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                transcript = alt.transcript
                logger.info(f"Transcript received: {transcript}")  # 텍스트 로그 출력
                print(transcript)  # 출력된 텍스트를 원하는 곳으로 보내도록 수정 가능


async def websocket_audio_stream(websocket: WebSocket):
    """
    WebSocket에서 실시간으로 오디오 데이터를 가져옵니다.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted.")  # WebSocket 연결 수락 로그
    while True:
        try:
            data = await websocket.receive_bytes()  # WebSocket으로부터 오디오 데이터 수신
            logger.info(f"Received audio data: {len(data)} bytes.")  # 수신 데이터 크기 로그
            yield data  # AWS Transcribe로 전송할 데이터를 yield
        except WebSocketDisconnect:
            logger.info("WebSocket connection closed.")  # WebSocket 연결 종료 로그
            break


async def write_chunks_to_transcribe(stream, websocket: WebSocket):
    """
    WebSocket에서 받은 데이터를 AWS Transcribe로 전달.
    """
    logger.info("Starting to write audio chunks to Transcribe.")  # 데이터 전송 시작 로그
    async for audio_chunk in websocket_audio_stream(websocket):
        logger.info(f"Sending audio chunk of size {len(audio_chunk)} bytes to Transcribe.")  # 전송 데이터 크기 로그
        await stream.input_stream.send_audio_event(audio_chunk=audio_chunk)
    logger.info("All audio chunks sent. Ending stream.")  # 전송 완료 로그
    await stream.input_stream.end_stream()


async def start_transcription(websocket: WebSocket):
    """
    WebSocket에서 받은 데이터를 AWS Transcribe로 처리.
    """
    logger.info("Initializing AWS Transcribe client.")  # 클라이언트 초기화 로그
    client = TranscribeStreamingClient(region="us-east-1")  # AWS 리전 설정

    # AWS Transcribe 스트림 시작
    stream = await client.start_stream_transcription(
        language_code="ko-KR",  # 언어 설정 (한국어는 ko-KR)
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )
    logger.info("AWS Transcribe stream started.")  # 스트림 시작 로그

    # AWS Transcribe 이벤트 처리 핸들러
    handler = MyEventHandler(stream.output_stream)

    # 데이터 전송 및 이벤트 핸들링
    logger.info("Starting transcription and event handling.")  # 트랜스크립션 처리 시작 로그
    await asyncio.gather(write_chunks_to_transcribe(stream, websocket), handler.handle_events())
    logger.info("Transcription and event handling completed.")  # 트랜스크립션 처리 완료 로그


@app.websocket("/socket")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 엔드포인트로 들어온 데이터를 AWS Transcribe로 전달합니다.
    """
    logger.info("WebSocket endpoint triggered.")  # 엔드포인트 호출 로그
    try:
        await start_transcription(websocket)
    except Exception as e:
        logger.error(f"Error occurred: {e}")  # 예외 발생 로그
