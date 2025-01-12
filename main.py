import asyncio
import httpx

import boto3
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from RAG.vector_stt import process_stt_and_update
from pydantic import BaseModel
from RAG import rag_qa
from RAG import sum_sen
from RAG import sum_recent
from RAG import mindmap
from slack_bot import bot_main
from langchain_aws import BedrockEmbeddings
from starlette.responses import StreamingResponse

from fastapi.responses import FileResponse
import os

import logging

app = FastAPI()

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)

buffer = []
max_tokens = 30
overlap = 10
WEBHOOK_URL = "https://webhook.site/9d751c97-7ebd-47ec-9139-23b461fa6d6d"


class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        global buffer
        results = transcript_event.transcript.results
        for result in results:
            if result.is_partial:
                continue

            for alt in result.alternatives:
                transcript = alt.transcript
                logger.info(f"Transcript received: {transcript}")  # 텍스트 로그 출력
                await self.send_webhook(WEBHOOK_URL, {"text": transcript})
                buffer.append(transcript)  # 버퍼에 텍스트 추가

                # 현재 버퍼의 총 토큰 수 계산
                total_tokens = sum(len(t.split()) for t in buffer)

                # 토큰 임계값 초과 시 버퍼 내용 저장
                if total_tokens >= max_tokens:
                    await self.save_partial_buffer_to_database()

    async def send_webhook(self, url: str, payload: dict):
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)

    async def save_partial_buffer_to_database(self):
        """
        버퍼에서 일정 토큰 수만 추출하여 데이터베이스로 저장하고,
        나머지는 버퍼에 남겨둠.
        """
        global buffer
        # 현재 버퍼를 하나의 텍스트로 합침
        full_text = " ".join(buffer)
        tokens = full_text.split()  # 버퍼의 모든 텍스트를 토큰 단위로 분리

        # 저장할 토큰과 남길 토큰 분리
        to_save = tokens[:max_tokens]  # 저장할 첫 40 토큰
        to_keep = tokens[max_tokens - overlap:]  # 남겨둘 나머지 토큰

        # 저장할 텍스트와 남길 텍스트로 분리
        save_text = " ".join(to_save)
        buffer = [" ".join(to_keep)]  # 남겨진 토큰을 다시 버퍼에 저장

        # 로그로 저장 작업 출력 (실제 DB 코드로 대체 가능)
        bedrock = boto3.client(
            service_name="bedrock-runtime", region_name="us-east-1"
        )
        embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v1", client=bedrock
        )
        postgres_url = "postgresql://postgres:blackout-26+@blackout-26-2.cj24wem202yj.us-east-1.rds.amazonaws.com:5432/postgres"
        table_name = "vector_store"
        process_stt_and_update(
            [
                {
                    "Note": save_text,
                }
            ],
            postgres_url,
            table_name,
            embeddings,
        )
        table_name = "summary"
        result, summary = sum_sen.detect_and_summarize(save_text)
        if result == "True":
            print(f"Topic transition detected. Summary:\n{summary}")
            sum_sen.save_summary_to_db(postgres_url, table_name, summary, metadata=None)


async def websocket_audio_stream(websocket: WebSocket):
    """
    WebSocket에서 실시간으로 오디오 데이터를 가져옵니다.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted.")  # WebSocket 연결 수락 로그
    with open("debug_audio.raw", "wb") as f:
        while True:
            try:
                data = await websocket.receive_bytes()  # WebSocket으로부터 오디오 데이터 수신
                # logger.info(f"Received audio data: {len(data)} bytes.")  # 수신 데이터 크기 로그
                f.write(data)
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
        # logger.info(f"Sending audio chunk of size {len(audio_chunk)} bytes to Transcribe.")  # 전송 데이터 크기 로그
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
async def websocket_endpoint(websocket: WebSocket, user_id: str = None, channel_id: int = None, title: str = None):
    """
    WebSocket 엔드포인트로 들어온 데이터를 AWS Transcribe로 전달합니다.
    """
    logger.info(f"WebSocket endpoint triggered with user_id: {user_id}, channel_id: {channel_id}, title: {title}")

    try:
        await start_transcription(websocket)
    except Exception as e:
        logger.error(f"Error occurred: {e}")  # 예외 발생 로그


class Item(BaseModel):
    channel_id: str
    text: str


@app.post("/chat")
async def echo_message(item: Item):
    """
    클라이언트로부터 받은 메시지를 동일하게 반환하는 POST 엔드포인트입니다.
    """
    response = rag_qa.qa(item.text)
    print(response)
    bot_main.send_text_to_channel(item.channel_id, response)
    # return {"message": rag_qa.qa(item.message)}


@app.get("/recent")
async def summery_recent():
    # print(sum_recent.sum_recent())
    return sum_recent.sum_recent()


@app.get("/mindmap")
async def mind__map():
    file_path = mindmap.mind_map()
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    # FastAPI FileResponse 사용
    return FileResponse(file_path, media_type="image/png", filename="mind_map.png")
    # return mindmap.mind_map()