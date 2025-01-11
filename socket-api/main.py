import asyncio
import os
import sys

import boto3
import websockets
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from langchain_aws import BedrockEmbeddings

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from RAG.vector_stt import process_stt_and_update

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 3
CHANNEL_NUMS = 1

CHUNK_SIZE = 1024 * 8
REGION = "us-east-1"

STRING_SIZE = 10


class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, output_stream):
        super().__init__(output_stream)
        self.acc = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        # This handler can be implemented to handle transcriptions as needed.
        # Here's an example to get started.
        results = transcript_event.transcript.results
        start_time = None
        for result in results:
            if result.is_partial:
                continue
            for alt in result.alternatives:
                metadata = alt.items[0]
                if start_time is None:
                    start_time = metadata.start_time
                self.acc += alt.transcript
                print(alt.transcript)

                if len(self.acc) > STRING_SIZE:
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
                                "Note": self.acc,
                                "start_time": start_time,
                                "end_time": metadata.end_time,
                            }
                        ],
                        postgres_url,
                        table_name,
                        embeddings,
                    )

                    start_time = None
                    self.acc = ""


async def handle_audio(websocket):
    print("Client connected")
    try:
        client = TranscribeStreamingClient(region=REGION)

        stream = await client.start_stream_transcription(
            language_code="ko-KR",
            media_sample_rate_hz=SAMPLE_RATE,
            media_encoding="flac",
        )

        async def write_chunks():
            async for message in websocket:
                await stream.input_stream.send_audio_event(audio_chunk=message)
            await stream.input_stream.end_stream()

        handler = MyEventHandler(stream.output_stream)
        await asyncio.gather(write_chunks(), handler.handle_events())
        print("done")
    except websockets.ConnectionClosed:
        print("Client disconnected")


async def main():
    async with websockets.serve(handle_audio, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
