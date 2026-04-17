"""
Unified AI Client — Routes to the configured provider
=======================================================
Usage:
    from ai_client import generate_json, generate, PROVIDER_NAME

Switches between Gemini, Groq, and Ollama based on AI_PROVIDER in .env
Validates API key at import time — fails fast with clear error.
"""

import sys
import config

PROVIDER_NAME = config.AI_PROVIDER

if PROVIDER_NAME == 'gemini':
    if not config.GEMINI_API_KEY:
        print(f"\n❌ GEMINI_API_KEY is not set in .env")
        print(f"   Get a free key at: https://aistudio.google.com/apikey")
        print(f"   Then add it to: {config.PROJECT_ROOT}/.env")
        print(f"\n   Or switch provider: AI_PROVIDER=groq or AI_PROVIDER=ollama\n")
        sys.exit(1)
    from gemini_client import generate_json, generate
    _model = config.GEMINI_MODEL

elif PROVIDER_NAME == 'groq':
    if not config.GROQ_API_KEY:
        print(f"\n❌ GROQ_API_KEY is not set in .env")
        print(f"   Get a free key at: https://console.groq.com/keys")
        print(f"   Then add it to: {config.PROJECT_ROOT}/.env")
        print(f"\n   Or switch provider: AI_PROVIDER=gemini or AI_PROVIDER=ollama\n")
        sys.exit(1)
    from groq_client import generate_json, generate
    _model = config.GROQ_MODEL

elif PROVIDER_NAME == 'ollama':
    from ollama_client import generate_json, generate
    _model = config.OLLAMA_MODEL

else:
    print(f"\n❌ Unknown AI_PROVIDER: '{PROVIDER_NAME}'")
    print(f"   Use 'gemini', 'groq', or 'ollama' in .env\n")
    sys.exit(1)

MODEL_NAME = _model

def get_provider_info():
    """Return a string describing the current provider config."""
    return f"{PROVIDER_NAME} ({MODEL_NAME})"
