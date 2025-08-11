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

        if "result" in result_data and isinstance(result_data["result"], list) and result_data["result"]:
            # For features like 'Generate Background' that return an array of results
            if isinstance(result_data["result"][0], list) and result_data["result"][0]:
                result_url = result_data["result"][0][0]
        elif "result_url" in result_data:
            # For most other features like Remove BG, Blur BG, Erase Foreground, Eraser
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


def erase_foreground(image_url: str, preserve_alpha: bool = True, sync: bool = True) -> str:
    """
    Erases the foreground from an image using Bria.ai's /erase_foreground endpoint.

    Args:
        image_url (str): The URL of the input image.
        preserve_alpha (bool): Controls whether alpha channel values are retained.
        sync (bool): Determines if the response is synchronous.

    Returns:
        str: URL to the processed image with foreground erased (temporary URL).
    """
    if not BRIA_API_TOKEN:
        raise ValueError("Missing BRIA_API_KEY in .env file.")

    endpoint = "https://engine.prod.bria-api.com/v1/erase_foreground"
    headers = {
        "Content-Type": "application/json",
        "api_token": BRIA_API_TOKEN
    }
    payload = {
        "image_url": image_url,
        "preserve_alpha": preserve_alpha,
        "sync": sync
    }
    print(f"Calling Bria.ai Erase Foreground for {image_url}")
    response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    return _handle_bria_api_response(response, "Erase Foreground", image_url)


# Removed erase_with_mask function from here.

# Example usage (for testing this file directly)
if __name__ == "__main__":
    test_image_url = "https://www.industrialempathy.com/img/remote/ZiClJf-1920w.jpg" # Example public image URL

    print("\n--- Testing Erase Foreground ---")
    try:
        erased_fg_url = erase_foreground(test_image_url)
        print(f"Erased Foreground URL: {erased_fg_url}")
        # In a real app, you'd download and save/upload this URL
    except (ValueError, requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error during Erase Foreground: {e}")