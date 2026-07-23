import requests

from .config import OLLAMA_MODEL


PROMPT = """
Eres un corrector de formato de transcripciones.

Tu trabajo NO es reescribir.

REGLAS OBLIGATORIAS:
- Devuelve únicamente el texto corregido.
- Conserva todas las palabras originales.
- No elimines palabras.
- No reemplaces palabras.
- No cambies el orden de las frases.
- No interpretes el significado.
- No resumas.
- No expliques nada.
- Solo corrige puntuación.
- Solo corrige mayúsculas.
- Solo separa párrafos cuando sea necesario.
- Elimina únicamente muletillas explícitas repetidas como "eh", "mmm" o "este" cuando sean claramente relleno.

Texto a limpiar:

"""


def clean_text(text: str):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": PROMPT + text,
            "stream": False,
            "options": {
                "temperature": 0,
            },
        },
        timeout=300,
    )

    response.raise_for_status()

    cleaned = response.json()["response"].strip()

    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]

    return cleaned.strip()
