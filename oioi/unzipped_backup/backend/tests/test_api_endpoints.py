import pytest
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
        async def gen():
            yield ChatCompletionResponse(
                id="mock-id",
                model="mock",
                choices=[{"index": 0, "message": {"role": "assistant", "content": "streamed"}, "finish_reason": "stop"}],
                usage={},
            )
        return gen()

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
    client = TestClient(app)
    payload = {
        "idea": "A robot finds a glowing blue flower on a dystopian planet",
        "style": "Sci-Fi",
    }
    response = client.post("/api/v1/projects/test-proj-123/pipeline/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert len(data["stages"]) == 7


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
