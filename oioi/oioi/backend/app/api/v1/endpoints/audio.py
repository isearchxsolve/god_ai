"""Audio generation endpoint.

Synthesizes a real mood-matched ambient score locally (numpy -> WAV). This is
the free-tier Sound Director path: genuine, playable audio produced offline.
A premium TTS/music provider slot can be added behind the same interface.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_pipeline import synthesize_score
from app.core import db
from app.core.auth import get_current_user

router = APIRouter()

_MOOD_KEYWORDS = {
    "tense": ["tense", "danger", "battle", "fight", "chase", "dark", "fear"],
    "mystic": ["mystic", "magic", "dream", "spirit", "forest", "ancient", "temple"],
    "joyful": ["joy", "happy", "celebrat", "dance", "party", "laugh", "sunshine"],
    "sad": ["sad", "loss", "rain", "goodbye", "lonely", "tears", "memory"],
    "hopeful": ["hope", "hero", "journey", "dawn", "rise", "new", "adventure"],
}


def _detect_mood(text: str) -> str:
    low = (text or "").lower()
    for mood, words in _MOOD_KEYWORDS.items():
        if any(w in low for w in words):
            return mood
    return "hopeful"


class AudioSpeechRequest(BaseModel):
    input: str
    voice: Optional[str] = "score"
    model: Optional[str] = "numpy-synth"
    duration_seconds: Optional[float] = 12.0
    mood: Optional[str] = None
    project_id: Optional[str] = None


@router.post("/speech")
async def generate_speech(request: AudioSpeechRequest,
                          user: dict = Depends(get_current_user)):
    """Generate a real audio track (WAV) matched to the text's mood."""
    mood = request.mood or _detect_mood(request.input)
    duration = max(5.0, min(120.0, request.duration_seconds or 12.0))

    loop = asyncio.get_event_loop()
    audio_uri = await loop.run_in_executor(
        None, synthesize_score, duration, mood, "audio"
    )
    if not audio_uri:
        raise HTTPException(status_code=502, detail="Audio synthesis failed")

    asset = None
    if request.project_id:
        asset = await db.create_asset(
            request.project_id, user["id"], "audio", request.input[:60] or "Score",
            uri=audio_uri, prompt=request.input, model_id="numpy-synth",
            provider="local", metadata={"mood": mood, "duration_seconds": duration},
        )

    return {
        "status": "completed",
        "audio_url": audio_uri,
        "voice": request.voice,
        "mood": mood,
        "duration_seconds": duration,
        "text": request.input,
        "asset": asset,
    }
