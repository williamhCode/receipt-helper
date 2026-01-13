#!/usr/bin/env python3
"""
Script to list all available Gemini models.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not set")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# List all models
print("Available Gemini Models:")
print("=" * 80)

for model in genai.list_models():
    print(f"\nModel: {model.name}")
    print(f"  Display Name: {model.display_name}")
    print(f"  Description: {model.description}")
    print(f"  Supported methods: {model.supported_generation_methods}")

print("\n" + "=" * 80)
print("\nModels that support 'generateContent':")
print("-" * 80)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"  {model.name}")
