# services/image_expansion.py.

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
BRIA_API_TOKEN = os.getenv("BRIA_API_KEY")

if not BRIA_API_TOKEN:
    print("Warning: BRIA_API_KEY not found. Please set it in your .env file for Bria.ai API calls.")

def _handle_bria_api_response(response: requests.Response, feature_name: str, input_url: str):
    """
    Helper function to process Bria.ai API responses and handle errors.
    """
    try:
        response.raise_for_status() # Raises HTTPError for 4xx/5xx responses
        result_data = response.json()
        result_url = None

        # Image Expansion returns 'result_url' directly
        if "result_url" in result_data:
            result_url = result_data["result_url"]
        elif "result" in result_data and isinstance(result_data["result"], list) and result_data["result"]:
            # For features that return an array of results (like 'Generate Background' used previously)
            if isinstance(result_data["result"][0], list) and result_data["result"][0]:
                result_url = result_data["result"][0][0] # Handle nested list if it appears
            else:
                result_url = result_data["result"][0] # Handle direct list of URLs
        
        if result_url:
            print(f"✅ {feature_name} successful. Bria Result URL (temporary): {result_url}")
            return result_url
        else:
            error_message = f"⚠️ Bria API returned 200 OK for {feature_name}, but 'result_url' or 'result' was not found as expected. Response: {json.dumps(result_data)}"
            print(error_message)
            raise RuntimeError(error_message)

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        error_text = http_err.response.text

        if status_code == 460:
            detailed_error = f"❌ {feature_name} failed: 460 - 'Failed to download image from provided URL'. " \
                             f"Please ensure '{input_url}' is directly accessible and not behind firewalls/authentication."
            print(detailed_error)
            raise RuntimeError(detailed_error)
        elif status_code == 422:
            # Handle specific 422 errors, e.g., "Input image contains fully transparent pixels along any edge"
            detailed_error = f"❌ {feature_name} failed (Validation Error): {error_text}. " \
                             f"Check input parameters or image properties (e.g., no full transparency at edges for expansion)."
            print(detailed_error)
            raise RuntimeError(detailed_error)
        else:
            general_error = f"❌ {feature_name} failed: HTTP Status {status_code} - {error_text}"
            print(general_error)
            raise RuntimeError(general_error)
            
    except requests.exceptions.ConnectionError as conn_err:
        network_error = f"❌ Connection Error for {feature_name}: Could not connect to Bria API. Details: {conn_err}"
        print(network_error)
        raise requests.exceptions.RequestException(network_error) from conn_err
    except requests.exceptions.Timeout as timeout_err:
        timeout_error = f"❌ Timeout Error for {feature_name}: Bria API did not respond within the expected time. Details: {timeout_err}"
        print(timeout_error)
        raise requests.exceptions.RequestException(timeout_err) from timeout_err
    except requests.exceptions.RequestException as req_err:
        unexpected_req_error = f"❌ An unexpected request error occurred for {feature_name}: {req_err}"
        print(unexpected_req_error)
        raise requests.exceptions.RequestException(unexpected_req_error) from req_err
    except json.JSONDecodeError as json_err:
        invalid_json_error = f"❌ Failed to parse JSON response from Bria API for {feature_name}. Response: '{response.text}'. Error: {json_err}"
        print(invalid_json_error)
        raise RuntimeError(invalid_json_error) from json_err


def expand_image(
    image_url: str,
    aspect_ratio: str = None, # e.g., "1:1", "16:9", or float like 0.5
    canvas_size: list[int] = None, # [width, height], e.g., [1500, 1000]
    original_image_size: list[int] = None, # [width, height]
    original_image_location: list[int] = None, # [x, y]
    prompt: str = None,
    seed: int = None,
    negative_prompt: str = None,
    preserve_alpha: bool = True,
    sync: bool = True,
    content_moderation: bool = False
) -> str:
    """
    Expands an image using Bria.ai's /image_expansion endpoint.

    Args:
        image_url (str): The URL of the input image.
        aspect_ratio (str or float, optional): Target aspect ratio ("1:1", "16:9", or float between 0.5-3.0).
        canvas_size (list[int], optional): Desired output canvas dimensions [width, height].
                                            Used if aspect_ratio is not provided.
        original_image_size (list[int], optional): Desired size of the original image within the canvas.
                                                   Required if aspect_ratio is not provided and canvas_size is used.
        original_image_location (list[int], optional): Top-left corner position of the original image within canvas.
                                                      Required if aspect_ratio is not provided and canvas_size is used.
        prompt (str, optional): Text prompt to guide expansion.
        seed (int, optional): Seed for predictable generation.
        negative_prompt (str, optional): Negative prompt to avoid certain elements.
        preserve_alpha (bool): Controls whether alpha channel values are retained.
        sync (bool): Determines if the response is synchronous.
        content_moderation (bool): Enables content moderation.

    Returns:
        str: URL to the expanded image (temporary URL).
    """
    if not BRIA_API_TOKEN:
        raise ValueError("Missing BRIA_API_KEY in .env file.")

    endpoint = "https://engine.prod.bria-api.com/v1/image_expansion"
    headers = {
        "Content-Type": "application/json",
        "api_token": BRIA_API_TOKEN
    }
    payload = {
        "image_url": image_url,
        "preserve_alpha": preserve_alpha,
        "sync": sync,
        "content_moderation": content_moderation
    }

    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    else:
        # If aspect_ratio is not provided, canvas_size, original_image_size, and original_image_location must be
        if not (canvas_size and original_image_size and original_image_location):
            raise ValueError(
                "When 'aspect_ratio' is not provided, 'canvas_size', 'original_image_size', "
                "and 'original_image_location' must all be specified."
            )
        payload["canvas_size"] = canvas_size
        payload["original_image_size"] = original_image_size
        payload["original_image_location"] = original_image_location

    if prompt:
        payload["prompt"] = prompt
    if seed is not None:
        payload["seed"] = seed
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt

    print(f"Calling Bria.ai Image Expansion for {image_url}")
    response = requests.post(endpoint, headers=headers, json=payload, timeout=120) # Increased timeout
    return _handle_bria_api_response(response, "Image Expansion", image_url)


# Example usage (for testing this file directly)
if __name__ == "__main__":
    test_image_url = "https://www.gstatic.com/webp/gallery/1.jpg" # Using a more reliable test URL

    print("\n--- Testing Image Expansion (Aspect Ratio) ---")
    try:
        expanded_url_ar = expand_image(
            image_url=test_image_url,
            aspect_ratio="16:9",
            prompt="a cozy living room with a fireplace"
        )
        print(f"Expanded Image URL (Aspect Ratio 16:9): {expanded_url_ar}")
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Image Expansion (Aspect Ratio): {e}")

    print("\n--- Testing Image Expansion (Precise Control) ---")
    # You need to know the original image's dimensions for precise control
    # Let's assume test_image_url is ~500x375 for this example
    # For accurate testing, you'd inspect the actual image dimensions first.
    original_img_width = 500
    original_img_height = 375
    
    # Target a 1000x700 canvas, placing original image at [250, 175] (center-ish)
    try:
        expanded_url_precise = expand_image(
            image_url=test_image_url,
            canvas_size=[1000, 700],
            original_image_size=[original_img_width, original_img_height],
            original_image_location=[250, 175], # Adjust based on how you want to expand
            prompt="more of the beautiful landscape"
        )
        print(f"Expanded Image URL (Precise Control): {expanded_url_precise}")
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Image Expansion (Precise Control): {e}")