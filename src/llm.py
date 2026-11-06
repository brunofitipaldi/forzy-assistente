"""
llm.py — Clientes de modelos de linguagem e de embeddings
FIAP x Forzy | Challenge IA | Grupo 4M

Backends de geracao (variavel LLM_BACKEND):
  - "ollama" (padrao): modelo local, sem custo e sem envio de dados para fora da maquina
  - "groq": API na nuvem (requer GROQ_API_KEY), mesmo backend usado na Sprint 2
Embeddings: sempre via Ollama (EMBED_MODEL, padrao embeddinggemma).
"""
from __future__ import annotations

import os
import time

from pathlib import Path

import numpy as np
import requests

# carrega .env da raiz do projeto (sem dependencia externa); variaveis ja definidas no terminal prevalecem
_ENV = Path(__file__).resolve().parents[1] / ".env"
if _ENV.exists():
    for _l in _ENV.read_text(encoding="utf-8").splitlines():
        if "=" in _l and not _l.lstrip().startswith("#"):
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1" if LLM_BACKEND == "ollama" else "llama-3.1-8b-instant")
EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma")
TEMPERATURA = float(os.getenv("LLM_TEMPERATURA", "0.1"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "450"))


def gerar(mensagens: list[dict]) -> dict:
    """Envia as mensagens ao LLM e devolve {texto, modelo, segundos, tokens}."""
    t0 = time.time()
    if LLM_BACKEND == "groq":
        from groq import Groq
        r = Groq(api_key=os.environ["GROQ_API_KEY"]).chat.completions.create(
            model=LLM_MODEL, messages=mensagens, temperature=TEMPERATURA, max_tokens=MAX_TOKENS)
        texto, tokens = r.choices[0].message.content, r.usage.completion_tokens
    else:
        r = requests.post(f"{OLLAMA_URL}/api/chat", timeout=600, json={
            "model": LLM_MODEL, "messages": mensagens, "stream": False,
            "options": {"temperature": TEMPERATURA, "num_predict": MAX_TOKENS, "num_ctx": 8192}})
        r.raise_for_status()
        d = r.json()
        texto, tokens = d["message"]["content"], d.get("eval_count")
    return {"texto": texto.strip(), "modelo": f"{LLM_BACKEND}:{LLM_MODEL}",
            "segundos": round(time.time() - t0, 1), "tokens": tokens}


def embeddings(textos: list[str], consulta: bool = False) -> np.ndarray:
    """Embeddings L2-normalizados. Prefixos recomendados para o embeddinggemma."""
    pref = "task: search result | query: " if consulta else ""
    r = requests.post(f"{OLLAMA_URL}/api/embed", timeout=300,
                      json={"model": EMBED_MODEL, "input": [pref + t for t in textos]})
    r.raise_for_status()
    m = np.array(r.json()["embeddings"], dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def ollama_disponivel() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).ok
    except requests.RequestException:
        return False
