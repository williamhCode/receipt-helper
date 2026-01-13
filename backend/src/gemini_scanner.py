"""
Gemini AI integration for receipt scanning.

This module handles receipt image/PDF processing using Google's Gemini AI to extract
structured data including merchant name, date, line items, and pricing.
"""

import os
import json
import logging
import tempfile
from datetime import date
from typing import Optional
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not set - receipt scanning will not work")

# Gemini model configuration
MODEL_NAME = "models/gemini-2.5-flash"  # Latest stable multimodal model


EXTRACTION_PROMPT = """You are a receipt OCR specialist. Extract structured data from this receipt image.

Return ONLY valid JSON with this exact structure (no markdown, no explanations):
{
  "merchant_name": "store or restaurant name",
  "receipt_date": "YYYY-MM-DD format or null if not found",
  "items": [
    {"name": "item description", "price": item price number, "taxable": true or false}
  ],
  "confidence": "high"
}

Instructions:
- Extract ALL line items from the receipt
- Set taxable individually based on if the item should be taxed
- Use null for receipt_date if the date is unclear or not visible
- Set confidence to "low" if: this is not a receipt, the image is too blurry to read, or critical data is missing

Return the JSON now:"""


async def scan_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Sends receipt image or PDF to Gemini AI and returns structured receipt data.

    Args:
        image_bytes: Raw bytes of the receipt image or PDF
        mime_type: MIME type of the file (image/jpeg, image/png, image/webp, application/pdf)

    Returns:
        dict: Structured receipt data with keys:
            - merchant_name (str)
            - receipt_date (str | None)
            - items (list[dict])
            - confidence (str)

    Raises:
        ValueError: If file is invalid or cannot be processed
        RuntimeError: If Gemini API call fails
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    try:
        logger.info(f"Processing receipt: {len(image_bytes)} bytes, type: {mime_type}")

        # Write bytes to temporary file
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "application/pdf": ".pdf"
        }.get(mime_type, ".jpg")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        # Upload file to Gemini
        uploaded_file = genai.upload_file(tmp_path, mime_type=mime_type)

        # Clean up temp file
        os.unlink(tmp_path)

        # Initialize Gemini model
        model = genai.GenerativeModel(MODEL_NAME)

        # Send file with prompt to Gemini
        response = model.generate_content([EXTRACTION_PROMPT, uploaded_file])

        if not response or not response.text:
            raise RuntimeError("Gemini returned empty response")

        logger.info(f"Gemini response: {response.text[:200]}...")

        # Parse JSON response
        # Remove markdown code blocks if present
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        data = json.loads(response_text)

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}\nResponse: {response.text}")
        raise RuntimeError(f"Failed to parse receipt data: {str(e)}")
    except Exception as e:
        logger.error(f"Receipt scanning error: {e}")
        raise RuntimeError(f"Receipt scanning failed: {str(e)}")


def validate_receipt_data(data: dict) -> tuple[bool, str]:
    """
    Validates that Gemini response has required fields and acceptable quality.

    Args:
        data: Dictionary returned from scan_receipt_image()

    Returns:
        tuple: (is_valid: bool, error_message: str)
        If is_valid is True, error_message will be empty string
    """
    # Check for required fields
    if "merchant_name" not in data:
        return False, "Missing merchant name"

    if "items" not in data or not isinstance(data["items"], list):
        return False, "Missing or invalid items list"

    if len(data["items"]) == 0:
        return False, "No items detected on receipt"

    # Check confidence
    confidence = data.get("confidence", "low").lower()
    if confidence == "low":
        return False, "Receipt image quality too low or not a valid receipt"

    # Validate merchant name is not empty
    if not data["merchant_name"] or not data["merchant_name"].strip():
        return False, "Could not determine merchant name"

    # Validate items have required fields
    for i, item in enumerate(data["items"]):
        if "name" not in item or not item["name"]:
            return False, f"Item {i+1} missing name"
        if "price" not in item:
            return False, f"Item {i+1} missing price"
        if not isinstance(item["price"], (int, float)):
            return False, f"Item {i+1} has invalid price"
        if item["price"] < 0:
            return False, f"Item {i+1} has negative price"
        if "taxable" not in item:
            # Default to true if missing
            item["taxable"] = True

    return True, ""


def generate_receipt_name(merchant: str, receipt_date: Optional[str]) -> str:
    """
    Generates a descriptive receipt name from merchant and date.

    Args:
        merchant: Merchant/store name
        receipt_date: ISO format date string (YYYY-MM-DD) or None

    Returns:
        str: Formatted receipt name

    Examples:
        - "Whole Foods - Jan 13, 2026"
        - "Target" (if no date)
    """
    merchant = merchant.strip()

    if not receipt_date:
        return merchant

    try:
        # Parse ISO date and format nicely
        date_obj = date.fromisoformat(receipt_date)
        formatted_date = date_obj.strftime("%b %d, %Y")
        return f"{merchant} - {formatted_date}"
    except (ValueError, TypeError):
        # If date parsing fails, just use merchant name
        logger.warning(f"Failed to parse receipt date: {receipt_date}")
        return merchant
