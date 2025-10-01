# services/background_service.py.

from typing import Dict, Any, Optional
import requests
import base64
import os
from dotenv import load_dotenv

# Load your .env file for the API key
load_dotenv()
BRIA_API_KEY = os.getenv("BRIA_API_KEY")
if not BRIA_API_KEY:
    raise RuntimeError("BRIA_API_KEY not found in environment variables")


def remove_background(
    api_key: Optional[str] = None,
    image_data: bytes = None,
    image_url: str = None,
    force: bool = False,
    content_moderation: bool = False
) -> bytes:
    """
    Remove the background from an image.

    Args:
        api_key: Bria AI API key (defaults to BRIA_API_KEY from .env)
        image_data: Raw image bytes (JPEG/PNG)
        image_url: Public URL of the image (alternative to image_data)
        force: Whether to force background removal even if alpha channel exists
        content_moderation: Whether to enable content moderation

    Returns:
        Raw bytes of the background‑removed image (PNG with transparency)

    Raises:
        ValueError: if neither image_data nor image_url is provided
        Exception: on HTTP or API errors
    """
    key = api_key or BRIA_API_KEY
    if not key:
        raise RuntimeError("API key must be provided")

    url = "https://engine.prod.bria-api.com/v1/product/remove_background"
    headers = {
        "api_token": key,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Build payload
    payload: Dict[str, Any] = {
        "force": force,
        "content_moderation": content_moderation
    }

    if image_url:
        payload["image_url"] = image_url
    elif image_data:
        payload["file"] = base64.b64encode(image_data).decode("utf-8")
    else:
        raise ValueError("Either image_data or image_url must be provided")

    try:
        # Debug logs (you can remove these in production)
        print(f"[remove_background] POST {url}")
        print(f"[remove_background] Headers: {headers}")
        print(f"[remove_background] Payload keys: {list(payload.keys())}")

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # The API returns JSON with a 'result_url' or possibly inline base64
        data = response.json()
        if "result_url" in data:
            # Fetch the PNG from the returned URL
            img_resp = requests.get(data["result_url"])
            img_resp.raise_for_status()
            return img_resp.content
        elif "file" in data:
            # If the API inlines base64‑encoded PNG
            return base64.b64decode(data["file"])
        else:
            raise Exception(f"Unexpected response format: {data}")

    except Exception as e:
        raise Exception(f"Background removal failed: {str(e)}")
