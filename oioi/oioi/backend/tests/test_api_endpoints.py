import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from providers.registry import get_registry, reset_registry
from providers.base import (
    AIProviderAdapter,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
    ProviderHealth,
    ProviderStatus,
    Model,
)


class MockChatAdapter(AIProviderAdapter):
    def __init__(self, name: str = "mock_chat"):
        self.provider_name = name
        self.health_status = ProviderStatus.HEALTHY

    def get_provider_name(self) -> str:
        return self.provider_name

    async def chat_completion(self, *args, **kwargs):
        return {
            "id": "mock-1",
            "choices": [{"message": {"role": "assistant", "content": "Mocked AI response for animation scene"}}],
        }

    async def chat_completion_stream(self, *args, **kwargs):
        yield ChatCompletionResponse(
            id="mock-id",
            model="mock",
            choices=[{"index": 0, "message": {"role": "assistant", "content": "streamed"}, "finish_reason": "stop"}],
            usage={},
        )

    async def generate_image(self, *args, **kwargs):
        return "https://image.pollinations.ai/prompt/cyberpunk%20city"

    async def generate_video(self, *args, **kwargs):
        return "https://cdn.pollinations.ai/video/clip_scene_1.mp4"

    async def create_embedding(self, *args, **kwargs):
        from providers.base import EmbeddingResponse
        return EmbeddingResponse(object="list", data=[], model="mock-embed", usage={})

    async def list_models(self):
        return [Model(id="mock-model", object="model")]

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(provider="mock_chat", status=ProviderStatus.HEALTHY)


@pytest.fixture(autouse=True)
def setup_mock_registry():
    reset_registry()
    registry = get_registry()
    registry.register("mock_chat", MockChatAdapter(), priority=0, capabilities=("chat", "image", "video", "audio"))
    yield
    reset_registry()


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "providers" in data
    assert "nim" not in data  # NVIDIA removed per AC-10


def test_chat_completions_endpoint():
    client = TestClient(app)
    payload = {
        "messages": [{"role": "user", "content": "Write a script for cyberpunk samurai"}],
        "model": "gemini-2.5-flash",
    }
    response = client.post("/api/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data


def test_chat_stream_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/chat/stream?prompt=Hello")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_images_generations_endpoint():
    client = TestClient(app)
    payload = {
        "prompt": "Cyberpunk cityscape neon rain",
        "style": "Anime",
    }
    response = client.post("/api/v1/images/generations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0
    assert "url" in data["data"][0]


def test_videos_generations_endpoint():
    client = TestClient(app)
    payload = {
        "prompt": "Camera panning across cyberpunk skyscrapers",
    }
    response = client.post("/api/v1/videos/generations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "video_url" in data


def test_audio_speech_endpoint():
    client = TestClient(app)
    payload = {
        "input": "In the neon-lit shadows of Neo-Tokyo...",
    }
    response = client.post("/api/v1/audio/speech", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "audio_url" in data


def test_projects_crud_endpoint():
    client = TestClient(app)
    # Create project
    create_res = client.post("/api/v1/projects/", json={"title": "Cyber Samurai Animation"})
    assert create_res.status_code == 200
    proj = create_res.json()
    proj_id = proj["id"]

    # Get project
    get_res = client.get(f"/api/v1/projects/{proj_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Cyber Samurai Animation"


def test_pipeline_run_endpoint():
    """Default run is async: returns immediately with status=started + stream URL."""
    client = TestClient(app)
    payload = {
        "idea": "A robot finds a glowing blue flower on a dystopian planet",
        "style": "Sci-Fi",
    }
    response = client.post("/api/v1/projects/test-proj-123/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert len(data["stages"]) == 7
    assert "stream_url" in data
    assert "project_id" in data


def test_pipeline_run_wait_completes_end_to_end(tmp_path):
    """wait=true blocks until the real 7-agent pipeline finishes (AC-3).

    Network and ffmpeg I/O are mocked so the run is hermetic and fast, but the
    full orchestrator executes: scriptwriter -> art director -> character/scene
    designers -> storyboard -> animator -> sound director -> director.
    """
    from app.core import db

    db.set_db_path(str(tmp_path / "pipeline_test.db"))
    db._schema_ready = False

    script_json = (
        '{"title": "The Blue Flower", "logline": "A robot finds a glowing blue flower", '
        '"mood": "hopeful", '
        '"characters": [{"name": "Unit-7", "role": "protagonist", "description": "a curious little robot"}], '
        '"scenes": [{"index": 1, "name": "Discovery", "beat": "beginning", '
        '"description": "a robot discovers a glowing flower in the ruins", "mood": "hopeful", '
        '"characters_present": ["Unit-7"], "dialogue": "", "duration_seconds": 5}]}'
    )

    async def fake_chat(registry, messages, temperature=0.7, max_tokens=2048):
        return {"content": script_json, "provider": "mock_chat", "model": "mock-model"}

    async def fake_image(registry, prompt, size="1280x720", timeout=90, require_local=True):
        return {"uri": "/media/fake.png", "provider": "mock_chat", "model": "flux",
                "source_url": "https://mock/image.png", "local": True}

    with patch("agent_pipeline.call_chat_with_failover", new=fake_chat), \
         patch("agent_pipeline.generate_image_with_failover", new=fake_image), \
         patch("app.services.media.render_clip_from_image", return_value="/media/clip.mp4"), \
         patch("app.services.media.concat_clips", return_value="/media/final.mp4"), \
         patch("app.services.media.probe_duration", return_value=5.0), \
         patch("agent_pipeline.synthesize_score", return_value="/media/score.wav"):
        client = TestClient(app)
        payload = {
            "idea": "A robot finds a glowing blue flower on a dystopian planet",
            "style": "Sci-Fi",
            "wait": True,
        }
        try:
            response = client.post("/api/v1/projects/e2e-proj-1/pipeline/run", json=payload)
        finally:
            db.set_db_path("")
            db._schema_ready = False

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert len(data["stages"]) == 7
    assert all(s["status"] == "completed" for s in data["stages"])
    assert data["final_video_uri"] == "/media/final.mp4"


def test_models_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/models/")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["video_models"]) >= 25
    assert len(data["image_models"]) >= 25
    assert len(data["llm_models"]) >= 25


def test_styles_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/styles/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 150


def test_providers_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/providers/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "providers" in data
