"""
Gemini API Client — Google AI Studio (Gemini + Gemma models)
==============================================================
Uses REST API directly (no SDK dependency needed).

Gemini models: native JSON mode (responseMimeType)
Gemma models:  text mode + JSON prompt instructions (no JSON mode support)

Default: gemma-3-27b-it (Apache 2.0, 30 RPM, 14.4K RPD)

Rate limit handling:
  - 429 responses trigger exponential backoff
  - Retry-After header respected
  - All failures retry up to max_retries
"""

import json
import time
import re
import requests

import config

GEMINI_API_KEY = config.GEMINI_API_KEY
GEMINI_MODEL = config.GEMINI_MODEL
REQUEST_TIMEOUT = config.REQUEST_TIMEOUT
MAX_RETRIES = config.MAX_RETRIES

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Detect model type at load time — Gemma models don't support responseMimeType
_IS_GEMMA = 'gemma' in GEMINI_MODEL.lower()
if _IS_GEMMA:
    # Logged once at startup, not per-request
    pass


def generate_json(prompt, temperature=0.2, max_retries=None):
    """Generate JSON from Gemini/Gemma. Returns parsed dict or None."""
    if not GEMINI_API_KEY:
        print("    ❌ GEMINI_API_KEY not set in .env")
        return None

    if max_retries is None:
        max_retries = MAX_RETRIES

    url = f"{API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    gen_config = {
        "temperature": temperature,
        "maxOutputTokens": 4096,
    }

    # Gemini models support native JSON mode; Gemma models need prompt-based JSON
    if not _IS_GEMMA:
        gen_config["responseMimeType"] = "application/json"
        actual_prompt = prompt
    else:
        actual_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation, no code fences."

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": actual_prompt}
                ]
            }
        ],
        "generationConfig": gen_config,
    }

    backoff = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"}
            )

            # Rate limit handling (15K TPM or 30 RPM exceeded)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', max(backoff, 5)))
                print(f"    ⏳ Rate limit (attempt {attempt+1}/{max_retries}) — waiting {retry_after}s...")
                time.sleep(retry_after)
                backoff = min(backoff * 2, 60)
                continue

            if response.status_code == 503:
                print(f"    ⏳ Overloaded (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            if response.status_code == 400:
                print(f"    ❌ Bad request (attempt {attempt+1}): {response.text[:200]}")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

            response.raise_for_status()

            data = response.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                block_reason = data.get("promptFeedback", {}).get("blockReason")
                if block_reason:
                    print(f"    ⚠️ Blocked: {block_reason} (attempt {attempt+1})")
                    return {}
                print(f"    ⚠️ Empty response (attempt {attempt+1})")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            if not text.strip():
                print(f"    ⚠️ Empty text (attempt {attempt+1})")
                time.sleep(backoff)
                continue

            # Parse JSON
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Fallback: extract JSON from text
                json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', text)
                if json_match:
                    try:
                        return json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
                print(f"    ⚠️ Invalid JSON (attempt {attempt+1})")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

        except requests.exceptions.Timeout:
            print(f"    ⏳ Timeout (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except requests.exceptions.ConnectionError:
            print(f"    ❌ Connection error (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception as e:
            print(f"    ❌ Error: {e} (attempt {attempt+1})")
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                return None

    print(f"    ❌ Failed after {max_retries} attempts")
    return None


def generate(prompt, temperature=0.3):
    """Generate text from Gemini/Gemma. Returns raw string."""
    if not GEMINI_API_KEY:
        print("    ❌ GEMINI_API_KEY not set in .env")
        return None

    url = f"{API_BASE}/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if candidates:
            return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None
