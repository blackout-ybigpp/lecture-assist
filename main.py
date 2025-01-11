import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from contextlib import asynccontextmanager
import sys
import json
import websockets
import struct

from starlette.websockets import WebSocket, WebSocketDisconnect

from utils.buffer_manager import buffer_manager
import config
import asyncio
import aiohttp

import logging

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session


def get_signed_headers(region, url, method="GET"):
    session = get_session()
    credentials = session.get_credentials()
    auth = SigV4Auth(credentials, "transcribe", region)

    request = AWSRequest(method=method, url=url)
    auth.add_auth(request)

    return dict(request.headers)


from utils.summarize import summarize_text

# @asynccontextmanager
# async def lifespan(app: FastAPI):
# 애플리케이션 시작 시 실행할 코드
# scheduler = AsyncIOScheduler()
# scheduler.add_job(summarize_task, "interval", minutes=1)
# scheduler.start()
# try:
#     yield
# finally:
# 애플리케이션 종료 시 실행할 코드
# scheduler.shutdown()

# app = FastAPI(lifespan=lifespan)
app = FastAPI()

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)


@app.websocket("/socket")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            logger.info(f"Received audio data: {len(data)} bytes.")

            buffer_manager.add_data(data)
            stt_result = await send_to_stt(data)
            logger.debug(data)
            # print(data)
            # await send_webhook(config.WEBHOOK_URL, {"text": stt_result})
    except WebSocketDisconnect:
        print("WebSocket connection closed")


# async def summarize_task():
#     accumulated_text = buffer_manager.get_all_data()
#     summary = await summarize_text(accumulated_text)
#     save_summary(accumulated_text, summary)
#     await send_webhook(config.WEBHOOK_URL, {"summary": summary})
#     buffer_manager.clear()

# def save_summary(original_text: str, summary_text: str):
#     # 데이터베이스 저장 로직
#     pass

async def send_webhook(url: str, payload: dict):
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


AWS_REGION = 'us-east-1'  # 서울 리전


def get_signed_headers(url, region):
    session = get_session()
    credentials = session.get_credentials()
    request = AWSRequest(method="GET", url=url)
    SigV4Auth(credentials, "transcribe", region).add_auth(request)
    return dict(request.headers)


import wave
import io
import struct


def debug_audio_format(audio_data):
    """
    Debug and verify the audio format of PCM data.
    """
    try:
        # 메모리에서 PCM 데이터를 처리하기 위해 BytesIO 사용
        with io.BytesIO(audio_data) as pcm_stream:
            with wave.open(pcm_stream, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                sample_width = wav_file.getsampwidth()
                num_channels = wav_file.getnchannels()

                logger.info(f"Sample Rate: {sample_rate} Hz")
                logger.info(f"Sample Width: {sample_width * 8} bits")
                logger.info(f"Number of Channels: {num_channels}")

                if sample_rate != 16000 or sample_width != 2 or num_channels != 1:
                    logger.warning("Audio format does not match Amazon Transcribe requirements!")
                else:
                    logger.info("Audio format matches Amazon Transcribe requirements.")
    except wave.Error as e:
        logger.error(f"Wave file parsing error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


import ffmpeg
import io


def convert_webm_to_pcm(audio_data):
    """
    Convert WebM audio data (Opus codec) to PCM 16kHz, 16-bit, mono format.
    Args:
        audio_data (bytes): Input WebM audio data.
    Returns:
        bytes: PCM audio data.
    """
    try:
        input_stream = io.BytesIO(audio_data)

        # FFmpeg를 사용해 변환
        out, _ = (
            ffmpeg.input('pipe:0', format='webm')  # WebM 형식으로 입력
            .output('pipe:1', format='s16le', ac=1, ar=16000)  # PCM 16kHz, mono 출력
            .run(input=input_stream.read(), capture_stdout=True, capture_stderr=True)
        )
        return out
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        return None


def extract_metadata(audio_data):
    """
    Extract metadata from audio data using ffmpeg.
    Args:
        audio_data (bytes): Raw audio data (WebM format).
    Returns:
        dict: Metadata information.
    """
    try:
        # Bytes 데이터를 파일로 저장
        with open("temp_audio.webm", "wb") as temp_file:
            temp_file.write(audio_data)

        # FFmpeg 프로브로 메타데이터 추출
        metadata = ffmpeg.probe("temp_audio.webm")
        return metadata
    except ffmpeg.Error as e:
        print(f"FFmpeg error: {e.stderr.decode()}")
        return None


async def send_to_stt(audio_data):
    logger.info("Debugging audio format before sending to Transcribe.")

    metadata = extract_metadata(audio_data)

    logger.info(f"Metadata: {metadata}")

    # 오디오 데이터를 PCM 형식으로 변환
    pcm_audio = convert_webm_to_pcm(audio_data)
    if pcm_audio is None:
        logger.error("Audio conversion failed. Aborting.")
        return None

    transcribe_url = (
        f"wss://transcribestreaming.{AWS_REGION}.amazonaws.com:8443/stream-transcription-websocket"
        f"?language-code=ko-KR&media-encoding=pcm&sample-rate=16000"
    )

    headers = get_signed_headers(transcribe_url, AWS_REGION)

    try:
        logger.info("Starting connection to Amazon Transcribe WebSocket.")
        async with websockets.connect(transcribe_url, extra_headers=headers) as websocket:
            logger.info("WebSocket connection established.")

            # 음성 데이터를 전송
            logger.info("Sending audio data to Transcribe.")
            await websocket.send(pcm_audio)
            logger.info("Audio data sent successfully.")

            # Transcribe 응답 수신
            async for message in websocket:
                if isinstance(message, bytes):  # EventStream 데이터 처리
                    event = parse_event_stream(message)  # EventStream 파싱
                    if event:
                        logger.info(f"Parsed event: {event}")
                        if "Transcript" in event:
                            results = event["Transcript"]["Results"]
                            for result in results:
                                if not result["IsPartial"]:
                                    transcript = result["Alternatives"][0]["Transcript"]
                                    logger.info(f"Final transcript received: {transcript}")
                                    return transcript
                else:
                    logger.warning(f"Unexpected message type: {type(message)}")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"WebSocket connection closed with error: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

    logger.info("STT function completed.")
    return None


import struct
import json


def parse_event_stream(data):
    """
    Parse Amazon Transcribe EventStream data.

    Args:
        data (bytes): Binary data from Amazon Transcribe WebSocket.

    Returns:
        dict: Parsed JSON object.
    """
    try:
        # 총 메시지 길이 (4바이트, big-endian)
        total_length = struct.unpack(">I", data[:4])[0]
        logger.info(f"Total message length: {total_length}")

        # 헤더 길이 (2바이트, big-endian)
        headers_length = struct.unpack(">H", data[4:6])[0]
        logger.info(f"Headers length: {headers_length}")

        # 페이로드 추출
        payload = data[6 + headers_length:]  # 헤더 이후 데이터
        logger.info(f"Payload raw data: {payload[:50]}")  # 페이로드 일부 로그

        # 페이로드를 UTF-8로 디코딩하고 JSON으로 변환
        payload_json = payload.decode("utf-8")
        logger.info(f"Payload JSON: {payload_json}")
        return json.loads(payload_json)  # JSON 객체 반환
    except Exception as e:
        logger.error(f"Failed to parse EventStream: {e}")
        return None


@app.get("/buffer")
async def get_buffer():
    """
    현재 버퍼에 저장된 데이터를 반환합니다.
    """
    data = buffer_manager.get_all_data()
    return {"buffer": data}