import pytest

@pytest.mark.asyncio
async def test_health_check_endpoint(async_client):
    response = await async_client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "VoxAssist Voice Helpdesk"
    assert isinstance(data.get("redis"), bool)
    assert isinstance(data.get("mongo"), bool)
    assert isinstance(data.get("qdrant"), bool)

@pytest.mark.asyncio
async def test_kb_articles_endpoint(async_client):
    response = await async_client.get("/api/kb")
    assert response.status_code == 200
    data = response.json()
    articles = data.get("articles", [])
    assert len(articles) >= 20
    assert any(a["id"] == "kb_wifi_01" for a in articles)
    assert any(a["id"] == "kb_vpn_01" for a in articles)
    assert any(a["id"] == "kb_docker_01" for a in articles)
