from rlm.utils.llm import OpenAIClient
from config import API_KEY, BASE_URL, ROOT_MODEL

client = OpenAIClient(api_key=API_KEY, model=ROOT_MODEL, base_url=BASE_URL)

# Test 1: stringa (come lo chiami tu)
try:
    resp = client.completion("Rispondi solo: OK")
    print(f"Test 1 OK: {resp}")
except Exception as e:
    print(f"Test 1 ERRORE: {e}")

# Test 2: lista messaggi esplicita
try:
    resp = client.completion([{"role": "user", "content": "Rispondi solo: OK2"}])
    print(f"Test 2 OK: {resp}")
except Exception as e:
    print(f"Test 2 ERRORE: {e}")