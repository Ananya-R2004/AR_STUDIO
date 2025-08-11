# services/image_features.py

import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
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

        # Determine how to extract the result URL based on the API response structure
        if "result" in result_data and isinstance(result_data["result"], list) and result_data["result"]:
            # For 'Generate Background' which returns an array of results
            # We'll take the first result URL for simplicity in this integration
            if isinstance(result_data["result"][0], list) and result_data["result"][0]:
                result_url = result_data["result"][0][0]
        elif "result_url" in result_data:
            # For 'Remove Background' and 'Blur Background'
            result_url = result_data["result_url"]

        if result_url:
            print(f"✅ {feature_name} successful. Bria Result URL (temporary): {result_url}")
            return result_url
        else:
            error_message = f"⚠️ Bria API returned 200 OK for {feature_name}, but 'result_url' or 'result' array was not found as expected. Response: {json.dumps(result_data)}"
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
        raise requests.exceptions.RequestException(timeout_error) from timeout_err
    except requests.exceptions.RequestException as req_err:
        unexpected_req_error = f"❌ An unexpected request error occurred for {feature_name}: {req_err}"
        print(unexpected_req_error)
        raise requests.exceptions.RequestException(unexpected_req_error) from req_err
    except json.JSONDecodeError as json_err:
        invalid_json_error = f"❌ Failed to parse JSON response from Bria API for {feature_name}. Response: '{response.text}'. Error: {json_err}"
        print(invalid_json_error)
        raise RuntimeError(invalid_json_error) from json_err


def generate_background(image_url: str, bg_prompt: str, num_results: int = 1, sync: bool = True, fast: bool = True) -> str:
    """
    Generates a new background for an image using Bria.ai's /background/replace endpoint.

    Args:
        image_url (str): The URL of the input image.
        bg_prompt (str): Text description of the new background.
        num_results (int): Number of results to generate (1-4). Note: sync=true often only returns 1 result.
        sync (bool): If True, response is synchronous. Recommended to use False for num_results > 1.
        fast (bool): If True, uses the fast generation mode.

    Returns:
        str: URL to the processed image with new background (temporary URL).
    """
    if not BRIA_API_TOKEN:
        raise ValueError("Missing BRIA_API_KEY in .env file.")

    endpoint = "https://engine.prod.bria-api.com/v1/background/replace"
    headers = {
        "Content-Type": "application/json",
        "api_token": BRIA_API_TOKEN
    }
    payload = {
        "image_url": image_url,
        "bg_prompt": bg_prompt,
        "num_results": num_results,
        "sync": sync,
        "fast": fast
    }
    print(f"Calling Bria.ai Generate Background for {image_url} with prompt '{bg_prompt}'")
    response = requests.post(endpoint, headers=headers, json=payload, timeout=120)
    return _handle_bria_api_response(response, "Generate Background", image_url)


def remove_image_background(image_url: str, preserve_partial_alpha: bool = True, sync: bool = True) -> str:
    """
    Removes the background from an image using Bria.ai's /background/remove endpoint.

    Args:
        image_url (str): The URL of the image to process.
        preserve_partial_alpha (bool): Controls whether partially transparent areas are retained.
        sync (bool): Determines if the response is synchronous.

    Returns:
        str: URL to the processed image with background removed (temporary URL).
    """
    if not BRIA_API_TOKEN:
        raise ValueError("Missing BRIA_API_KEY in .env file.")

    endpoint = "https://engine.prod.bria-api.com/v1/background/remove"
    headers = {
        "api_token": BRIA_API_TOKEN
    }
    # For file uploads, use 'files' parameter in requests.post
    # For image_url, it goes in 'data' for multipart/form-data
    data = {
        "image_url": image_url,
        "preserve_partial_alpha": str(preserve_partial_alpha).lower(), # Booleans need to be strings "true"/"false" for multipart data
        "sync": str(sync).lower()
    }

    print(f"Calling Bria.ai Remove Background for {image_url}")
    # Note: Bria's docs show multipart/form-data for /background/remove,
    # even when using image_url. requests.post handles this correctly with 'data'.
    response = requests.post(endpoint, headers=headers, data=data, timeout=60) # Timeout adjusted
    return _handle_bria_api_response(response, "Remove Image Background", image_url)


def blur_background(image_url: str, scale: int = 5, preserve_alpha: bool = True, sync: bool = True) -> str:
    """
    Applies a blur effect to the background of an image using Bria.ai's /background/blur endpoint.

    Args:
        image_url (str): The URL of the input image.
        scale (int): How blurry the background should be (1-5).
        preserve_alpha (bool): Controls whether alpha channel values are retained.
        sync (bool): Determines if the response is synchronous.

    Returns:
        str: URL to the processed image with blurred background (temporary URL).
    """
    if not BRIA_API_TOKEN:
        raise ValueError("Missing BRIA_API_KEY in .env file.")

    endpoint = "https://engine.prod.bria-api.com/v1/background/blur"
    headers = {
        "Content-Type": "application/json",
        "api_token": BRIA_API_TOKEN
    }
    payload = {
        "image_url": image_url,
        "scale": scale,
        "preserve_alpha": preserve_alpha,
        "sync": sync
    }
    print(f"Calling Bria.ai Blur Background for {image_url} with scale {scale}")
    response = requests.post(endpoint, headers=headers, json=payload, timeout=60) # Timeout adjusted
    return _handle_bria_api_response(response, "Blur Background", image_url)


# Example usage (for testing this file directly)
if __name__ == "__main__":
    test_image_url = "https://www.industrialempathy.com/img/remote/ZiClJf-1920w.jpg" # Example public image URL

    print("\n--- Testing Generate Background ---")
    try:
        gen_bg_url = generate_background(test_image_url, "in a futuristic city", num_results=1)
        print(f"Generated Background URL: {gen_bg_url}")
        # In a real app, you'd download and save/upload this URL as discussed previously
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Generate Background: {e}")

    print("\n--- Testing Remove Image Background ---")
    try:
        remove_bg_url = remove_image_background(test_image_url)
        print(f"Removed Background URL: {remove_bg_url}")
        # In a real app, you'd download and save/upload this URL
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Remove Image Background: {e}")

    print("\n--- Testing Blur Background ---")
    try:
        blur_bg_url = blur_background(test_image_url, scale=3)
        print(f"Blurred Background URL: {blur_bg_url}")
        # In a real app, you'd download and save/upload this URL
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Blur Background: {e}")