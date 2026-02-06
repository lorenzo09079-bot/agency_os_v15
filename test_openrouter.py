# -*- coding: utf-8 -*-
"""Test RAW con requests - vede JSON completo da OpenRouter"""

import requests, json

API_KEY = "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"
URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://agency-os.local",
}

# --- TEST 1: Root LM ---
print("=== ROOT LM (Qwen3 Coder) ===")
resp = requests.post(URL, headers=headers, json={
    "model": "deepseek/deepseek-r1-0528:free",
    "messages": [{"role": "user", "content": "Rispondi solo: OK"}],
})
print(f"Status: {resp.status_code}")
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])

print()

# --- TEST 2: Sub-LLM ---
print("=== SUB-LLM (DeepSeek R1) ===")
resp = requests.post(URL, headers=headers, json={
    "model": "deepseek/deepseek-r1-0528:free",
    "messages": [{"role": "user", "content": "Rispondi solo: OK"}],
})
print(f"Status: {resp.status_code}")
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
