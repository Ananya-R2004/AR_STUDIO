import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env..
load_dotenv()

API_TOKEN = os.getenv("BRIA_API_KEY")
BASE_URL = "https://engine.prod.bria-api.com/v1/product/cutout"

def product_cutout(image_url, sku="12345", force_rmbg=False, preserve_alpha=True, content_moderation=False):
    if not API_TOKEN:
        raise ValueError("Missing BRIA_API_TOKEN in .env file")

    headers = {
        "Content-Type": "application/json",
        "api_token": API_TOKEN
    }

    payload = {
        "sku": sku,
        "image_url": image_url,
        "force_rmbg": force_rmbg,
        "preserve_alpha": preserve_alpha,
        "content_moderation": content_moderation
    }

    response = requests.post(BASE_URL, json=payload, headers=headers)

    if response.status_code == 200:
        result = response.json()
        print("✅ Cutout created successfully!")
        print("🖼️ Cutout URL:", result.get("result_url"))
        return result.get("result_url")
    else:
        print(f"❌ Failed with status code {response.status_code}")
        print("🔍 Response:", response.text)
        return None
