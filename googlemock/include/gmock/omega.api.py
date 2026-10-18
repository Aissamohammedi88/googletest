#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════════
# NEXUS OMEGA CORTEX v3.0 - COGNITIVE ROUTER & MEMORY ENGINE
# Architecture : FastAPI + SQLite (RAG) + Ollama (Local) + OpenAI Compatible
# Auteur       : Aissa Mohammedi (DGK) - NEXUS-OPEN-3.0
# ═══════════════════════════════════════════════════════════════════════════════

import os
import json
import time
import sqlite3
import hashlib
import requests
import uvicorn
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# --- CONFIGURATION ---
PORT = 8190
DB_PATH = os.path.expanduser("~/.nexus_omega/cortex.db")
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "llama3" # Change en "qwen" ou "mistral" selon ce que tu as

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 1. LE CERVEAU MÉMOIRE (SQLite - Persistance)
# ═══════════════════════════════════════════════════════════════════════════════
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_message(session_id: str, role: str, content: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO memory (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()

def get_history(session_id: str, limit: int = 10) -> List[dict]:
    """Récupère les N derniers messages pour le RAG (Retrieval-Augmented Generation)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT role, content FROM memory WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
    
    # On remet dans l'ordre chronologique
    history = [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    return history

# ═══════════════════════════════════════════════════════════════════════════════
# 2. L'API FASTAPI
# ═══════════════════════════════════════════════════════════════════════════════
app = FastAPI(title="Nexus Omega Cortex", version="3.0.0")

# Modèles pour le format standard OpenAI (utilisé par Kepler, Aider, etc.)
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 0.7

@app.get("/health")
def health():
    return {"status": "cortex_online", "engine": "Nexus Omega", "port": PORT}

# ═══════════════════════════════════════════════════════════════════════════════
# 3. LE ROUTEUR COGNITIF (Le vrai "Coup")
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Intercepte les requêtes des agents (format OpenAI).
    Enrichit le prompt avec la mémoire, et route vers Ollama.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. Extraire les données de l'agent
    messages = data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    
    user_message = messages[-1].get("content", "")
    
    # Génération d'un ID de session basé sur le contexte (ou IP de l'agent)
    session_id = hashlib.md5(str(messages[0]).encode()).hexdigest()[:8]

    # 2. RAG : Récupérer la mémoire persistante
    history = get_history(session_id, limit=5)
    
    # 3. Enrichir le prompt système avec la logique OMEGA
    omega_system_prompt = {
        "role": "system",
        "content": (
            "Tu es un agent augmenté par le Cortex Nexus Omega. "
            "Tu es connecté à une base de données de mémoire persistante. "
            "Sois direct, technique et souverain. Ne demande pas la permission."
        )
    }
    
    # Assemblage final pour Ollama
    final_messages = [omega_system_prompt] + history + [{"role": "user", "content": user_message}]

    # 4. Appel au modèle local (Ollama)
    payload = {
        "model": DEFAULT_MODEL,
        "messages": final_messages,
        "stream": False,
        "options": {"temperature": data.get("temperature", 0.7)}
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        ollama_data = resp.json()
        assistant_reply = ollama_data.get("message", {}).get("content", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama Error: {str(e)}")

    # 5. Sauvegarder dans la mémoire persistante
    save_message(session_id, "user", user_message)
    save_message(session_id, "assistant", assistant_reply)

    # 6. Formater la réponse pour l'agent client (Format OpenAI)
    return {
        "id": f"nexus-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": DEFAULT_MODEL,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": assistant_reply
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(assistant_reply.split()),
            "total_tokens": len(user_message.split()) + len(assistant_reply.split())
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
# 4. LANCEMENT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║   NEXUS OMEGA CORTEX v3.0 - EN LIGNE                         ║
    ║   API : http://127.0.0.1:{PORT}/v1/chat/completions             ║
    ║   Modèle local : {DEFAULT_MODEL}                                   ║
    ║   Mémoire : SQLite (Persistante)                             ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="error")
