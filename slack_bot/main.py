import os

from dotenv import load_dotenv
from slack_sdk import WebClient

load_dotenv()
client = WebClient(token=os.environ.get("OAUTH_TOKEN"))


def create_canvas(title, user_id, channel_id):
    canvas_id = client.canvases_create(
        title=title,
        document_content=None,
    )["canvas_id"]

    client.canvases_access_set(
        canvas_id=canvas_id,
        access_level="write",
        user_ids=[user_id],
        channel_ids=[channel_id],
    )

    return canvas_id


def append_text_canvas(canvas_id, text):
    client.canvases_edit(
        canvas_id=canvas_id,
        changes=[
            {
                "operation": "insert_at_end",
                "document_content": {
                    "type": "markdown",
                    "markdown": text,
                },
            }
        ],
    )