"""
Groq API Client — OpenAI-compatible REST API
==============================================
Uses Groq's OpenAI-compatible chat completions endpoint.
JSON mode via response_format for structured output.

Recommended model: llama-3.1-8b-instant
Free tier: 30 RPM, 14.4K req/day, 6K tok/min, 500K tok/day

Alternative models (set GROQ_MODEL in .env):
  - llama-3.3-70b-versatile: Better quality, but 1K req/day limit
  - qwen/qwen3-32b: 60 RPM but 1K req/day
  - meta-llama/llama-4-scout-17b-16e-instruct: Good balance
"""

import json
import time
import requests
import re

import config

GROQ_API_KEY = config.GROQ_API_KEY
GROQ_MODEL = config.GROQ_MODEL
REQUEST_TIMEOUT = config.REQUEST_TIMEOUT
MAX_RETRIES = config.MAX_RETRIES

API_URL = "https://api.groq.com/openai/v1/chat/completions"


def generate_json(prompt, temperature=0.2, max_retries=None):
    """Generate JSON from Groq. Returns parsed dict or None."""
    if not GROQ_API_KEY:
        print("    ❌ GROQ_API_KEY not set in .env")
        return None

    if max_retries is None:
        max_retries = MAX_RETRIES

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a medical education expert. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    backoff = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL,
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            # Rate limit handling
            if response.status_code == 429:
                retry_after = int(response.headers.get('retry-after', backoff))
                print(f"    ⏳ Groq rate limit (attempt {attempt+1}/{max_retries}) — waiting {retry_after}s...")
                time.sleep(retry_after)
                backoff = min(backoff * 2, 60)
                continue

            if response.status_code == 503:
                print(f"    ⏳ Groq overloaded (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            response.raise_for_status()

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                print(f"    ⚠️ Groq empty response (attempt {attempt+1})")
                time.sleep(backoff)
                continue

            text = choices[0].get("message", {}).get("content", "")

            if not text.strip():
                print(f"    ⚠️ Groq empty text (attempt {attempt+1})")
                time.sleep(backoff)
                continue

            # Parse JSON — JSON mode should give valid JSON
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
                print(f"    ⚠️ Groq invalid JSON (attempt {attempt+1})")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue

        except requests.exceptions.Timeout:
            print(f"    ⏳ Groq timeout (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except requests.exceptions.ConnectionError:
            print(f"    ❌ Groq connection error (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception as e:
            error_str = str(e)
            if '502' in error_str or '504' in error_str:
                print(f"    ⏳ Groq gateway error (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                print(f"    ❌ Groq error: {e} (attempt {attempt+1})")
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30)
                else:
                    return None

    print(f"    ❌ Groq failed after {max_retries} attempts")
    return None


def generate(prompt, temperature=0.3):
    """Generate text from Groq. Returns raw string."""
    if not GROQ_API_KEY:
        print("    ❌ GROQ_API_KEY not set in .env")
        return None

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": 2048,
    }

    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return None
    except Exception as e:
        print(f"    ❌ Groq Error: {e}")
        return None
