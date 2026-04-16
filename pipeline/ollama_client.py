"""
Ollama API Client — Optimized for low-resource servers
========================================================
- Longer timeouts (5 min) to avoid 504s behind reverse proxies
- Uses /no_think tag for qwen3 to skip chain-of-thought (2-3x faster)
- Configurable via OLLAMA_API and OLLAMA_MODEL in synapse/.env
"""

import requests
import json
import os
import time
import re

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'synapse', '.env')
    load_dotenv(_env_path)
except ImportError:
    pass

OLLAMA_URL = os.environ.get('OLLAMA_API', 'http://127.0.0.1:11434').rstrip('/')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:8b')

# Long timeout — critical for CPU-only instances behind reverse proxies
REQUEST_TIMEOUT = 300  # 5 minutes


def generate(prompt, temperature=0.3):
    """Generate text from Ollama. Returns raw string."""
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 2048,    # cap output length
            "num_ctx": 4096,        # smaller context = faster
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json().get('response', '')
    except Exception as e:
        print(f"    ❌ Ollama Error: {e}")
        return None


def generate_json(prompt, temperature=0.2, max_retries=3):
    """Generate JSON from Ollama with retries. Returns parsed dict or None."""
    url = f"{OLLAMA_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 4096,
            "num_ctx": 4096,
        }
    }

    backoff = 5
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            text = response.json().get('response', '')

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
            else:
                print(f"    ⚠️ No JSON in response (attempt {attempt+1})")
                return {}

        except json.JSONDecodeError:
            print(f"    ⚠️ Invalid JSON (attempt {attempt+1})")
            return {}
        except requests.exceptions.Timeout:
            print(f"    ⏳ Timeout (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
        except Exception as e:
            error_str = str(e)
            if '504' in error_str or '502' in error_str:
                print(f"    ⏳ Gateway timeout (attempt {attempt+1}/{max_retries}) — waiting {backoff}s...")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                print(f"    ❌ Ollama Error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                else:
                    return None

    return None
