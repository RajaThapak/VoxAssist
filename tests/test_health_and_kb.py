import pytest
import httpx

BASE_URL = "http://localhost:8000"

@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        assert data.get("service") == "VoxAssist Voice Helpdesk"
        assert data.get("redis") is True
        assert data.get("mongo") is True
        assert data.get("qdrant") is True

@pytest.mark.asyncio
async def test_kb_articles_endpoint():
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/kb")
        assert response.status_code == 200
        data = response.json()
        articles = data.get("articles", [])
        assert len(articles) == 20
        assert any(a["id"] == "kb_wifi_01" for a in articles)
        assert any(a["id"] == "kb_vpn_01" for a in articles)
        assert any(a["id"] == "kb_docker_01" for a in articles)
