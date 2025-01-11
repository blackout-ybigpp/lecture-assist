import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from contextlib import asynccontextmanager

from starlette.websockets import WebSocket, WebSocketDisconnect

from utils.buffer_manager import buffer_manager
import config
import asyncio

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

@app.websocket("/socket")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            buffer_manager.add_data(data)
            stt_result = await send_to_stt(data)
            await send_webhook(config.WEBHOOK_URL, {"text": stt_result})
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

async def send_to_stt(audio_data):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.STT_SERVICE_URL,
            files={"file": audio_data}
        )
        return response.json().get("text")
