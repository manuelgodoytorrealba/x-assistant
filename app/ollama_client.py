import json
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


def generate_json(prompt: str, model: str = OLLAMA_MODEL) -> dict:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    raw_text = data.get("response", "").strip()

    if not raw_text:
        raise ValueError("Ollama devolvió una respuesta vacía")

    return json.loads(raw_text)