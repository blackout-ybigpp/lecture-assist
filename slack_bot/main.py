import base64
import os

import requests
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


def send_image_to_chat(channel_id, image):
    image_base64 = base64.b64encode(image).decode("utf-8")

    id = requests.post(
        f"{os.environ.get("IMAGE_SERVER")}", json={"image": image_base64}
    ).text

    client.chat_postMessage(
        channel=channel_id,
        blocks=[
            {
                "type": "image",
                "image_url": f"{os.environ.get("IMAGE_SERVER")}/{id}",
                "alt_text": "alt text for image",
            }
        ],
    )
