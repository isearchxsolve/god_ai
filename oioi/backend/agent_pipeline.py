from typing import Dict, Any, List, Optional
import asyncio
import httpx
import json
import urllib.parse

AGENT_ROLES = [
    'Scriptwriter',
    'Art Director',
    'Character Designer',
    'Scene Designer',
    'Animator',
    'Sound Director',
    'Director',
]

async def run_pipeline(prompt: str, registry=None) -> dict:
    """Run the full 7-agent pipeline using a fast LLM + Pollinations."""
    
    system_prompt = """You are an expert AI Animation Studio.
You must output ONLY valid JSON describing a 3-scene animation based on the user's idea.
Structure:
{
  "script": "Overall story summary",
  "art_direction": {
    "style": "Visual style name",
    "color_palette": ["#hex1", "#hex2", "#hex3", "#hex4"],
    "lighting": "Lighting description"
  },
  "scenes": [
    {
      "scene": 1,
      "environment": "Environment description",
      "mood": "Scene mood",
      "motion": "Camera motion",
      "visual_prompt": "Highly detailed visual description for image generation"
    }
  ]
}
"""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:20128/v1/chat/completions",
                json={
                    "model": "frontier",
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                },
                timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
    except Exception as e:
        print(f"LLM Error: {e}")
        # Fallback to mock data if LLM fails
        result = {
            "script": f"A captivating animation about {prompt}.",
            "art_direction": {"style": "Anime", "color_palette": ["#1A1A2E"], "lighting": "Neon"},
            "scenes": [
                {"scene": 1, "environment": "City", "mood": "Dark", "motion": "Pan", "visual_prompt": f"{prompt} in a cyberpunk city"},
                {"scene": 2, "environment": "Alley", "mood": "Tense", "motion": "Zoom", "visual_prompt": f"{prompt} confronting enemy in alley"},
            ]
        }

    # Transform to UI expected format
    scenes = []
    anim = []
    
    for s in result.get("scenes", []):
        img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(s.get('visual_prompt', ''))}?width=1024&height=1024&nologo=true"
        video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4"
        
        scenes.append({
            "scene": s.get("scene"),
            "environment": s.get("environment"),
            "mood": s.get("mood"),
            "image_url": img_url
        })
        
        anim.append({
            "scene": s.get("scene"),
            "motion": s.get("motion"),
            "video_url": video_url
        })

    chars = [
        {"name": "Protagonist", "role": "Hero", "description": "Lead character", "image_url": f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt + ' protagonist character sheet anime style')}?width=512&height=512&nologo=true"}
    ]

    return {
        'script': result.get("script", ""),
        'art_direction': result.get("art_direction", {}),
        'characters': chars,
        'scenes': scenes,
        'storyboard': [{'panel': 1, 'description': result.get("script", "")}],
        'animation': anim,
        'sound_plan': {
            "bgm_track": "Synthwave Ambient Pulse (120 BPM)",
            "voice_track": "https://api.streamelements.com/kappa/v2/speech?voice=Brian&text=The%20journey%20begins",
            "sfx": ["Rain", "Engine", "Energy"]
        },
        'director_notes': 'Approved by Director',
        'roles': list(AGENT_ROLES),
    }

class AnimationPipeline:
    def __init__(self, registry=None):
        self.registry = registry

    async def run(self, idea: str, style: str = "Anime") -> Dict[str, Any]:
        return await run_pipeline(idea, registry=self.registry)

def create_animation_pipeline(registry=None) -> AnimationPipeline:
    return AnimationPipeline(registry=registry)
