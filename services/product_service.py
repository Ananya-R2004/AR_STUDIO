# services/product_service.py
import requests
import base64
import io
import os # Add os import if you're using it here

BRIA_API_BASE_URL = "https://engine.prod.bria-api.com/v1"

def _call_bria_api(endpoint, api_key, payload):
    """Helper to make API calls to Bria."""
    headers = {
        'Content-Type': 'application/json',
        'api_token': api_key
    }
    url = f"{BRIA_API_BASE_URL}{endpoint}"
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - {response.text}")
        return {"error": f"API Error: {response.text}"}
    except Exception as err:
        print(f"Other error occurred: {err}")
        return {"error": f"An unexpected error occurred: {err}"}

def create_product_packshot(
    api_key: str,
    image_bytes: bytes = None,
    image_url: str = None,
    sku: str = None,
    background_color: str = "#FFFFFF",
    force_rmbg: bool = False,
    content_moderation: bool = False
):
    """
    Calls the Bria API to create a product packshot.
    Accepts image bytes or a URL.
    """
    payload = {}
    if sku:
        payload["sku"] = sku
    if image_url:
        payload["image_url"] = image_url
    elif image_bytes:
        payload["file"] = base64.b64encode(image_bytes).decode('utf-8')
    else:
        return {"error": "Either image_bytes or image_url must be provided."}

    payload["background_color"] = background_color
    payload["force_rmbg"] = force_rmbg
    payload["content_moderation"] = content_moderation

    return _call_bria_api("/product/packshot", api_key, payload)

def add_product_shadow(
    api_key: str,
    image_bytes: bytes = None,
    image_url: str = None,
    sku: str = None,
    shadow_type: str = "regular",
    background_color: str = None, # None to get transparent background
    shadow_color: str = "#000000",
    shadow_offset: list = None, # [x, y]
    shadow_intensity: int = 60,
    shadow_blur: int = None,
    shadow_width: int = None,
    shadow_height: int = 70,
    force_rmbg: bool = False,
    preserve_alpha: bool = True,
    content_moderation: bool = False
):
    """
    Calls the Bria API to add shadow to a product cutout.
    Accepts image bytes or a URL.
    """
    payload = {}
    if sku:
        payload["sku"] = sku
    if image_url:
        payload["image_url"] = image_url
    elif image_bytes:
        payload["file"] = base64.b64encode(image_bytes).decode('utf-8')
    else:
        return {"error": "Either image_bytes or image_url must be provided."}

    payload["type"] = shadow_type
    if background_color: # Only include if not None (for transparent)
        payload["background_color"] = background_color
    payload["shadow_color"] = shadow_color
    if shadow_offset:
        payload["shadow_offset"] = shadow_offset
    payload["shadow_intensity"] = shadow_intensity
    if shadow_blur is not None:
        payload["shadow_blur"] = shadow_blur
    if shadow_width is not None:
        payload["shadow_width"] = shadow_width
    payload["shadow_height"] = shadow_height
    payload["force_rmbg"] = force_rmbg
    payload["preserve_alpha"] = preserve_alpha
    payload["content_moderation"] = content_moderation

    return _call_bria_api("/product/shadow", api_key, payload)


def create_lifestyle_shot_by_text(
    api_key: str,
    scene_description: str,
    image_bytes: bytes = None,
    image_url: str = None,
    sku: str = None,
    sync: bool = False,
    fast: bool = True,
    optimize_description: bool = True,
    num_results: int = 4,
    exclude_elements: str = None,
    placement_type: str = "original",
    original_quality: bool = False,
    aspect_ratio: str = None, # e.g., "1:1"
    shot_size: list = None, # [width, height]
    foreground_image_size: list = None, # [width, height]
    foreground_image_location: list = None, # [x, y]
    manual_placement_selection: list = None, # e.g., ["upper_left"]
    padding_values: list = None, # [left, right, top, bottom]
    force_rmbg: bool = False,
    content_moderation: bool = False
):
    """
    Calls the Bria API to create a lifestyle product shot by text.
    Accepts image bytes or a URL.
    """
    payload = {
        "scene_description": scene_description,
        "sync": sync,
        "fast": fast,
        "optimize_description": optimize_description,
        "num_results": num_results,
        "placement_type": placement_type,
        "original_quality": original_quality,
        "force_rmbg": force_rmbg,
        "content_moderation": content_moderation
    }

    if sku:
        payload["sku"] = sku
    if image_url:
        payload["image_url"] = image_url
    elif image_bytes:
        payload["file"] = base64.b64encode(image_bytes).decode('utf-8')
    else:
        return {"error": "Either image_bytes or image_url must be provided."}

    if exclude_elements:
        payload["exclude_elements"] = exclude_elements
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if shot_size:
        payload["shot_size"] = shot_size
    if foreground_image_size:
        payload["foreground_image_size"] = foreground_image_size
    if foreground_image_location:
        payload["foreground_image_location"] = foreground_image_location
    if manual_placement_selection:
        payload["manual_placement_selection"] = manual_placement_selection
    if padding_values:
        payload["padding_values"] = padding_values

    return _call_bria_api("/product/lifestyle_shot_by_text", api_key, payload)