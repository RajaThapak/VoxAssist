import pytest
from backend.rag.qdrant_kb import qdrant_manager
from backend.rag.seed_kb import SEED_KB_ARTICLES

@pytest.mark.asyncio
async def test_rag_embedding_and_retrieval():
    await qdrant_manager.init_db()
    
    test_cases = [
        ("Wi-Fi drops repeatedly or weak signal trouble", "kb_wifi_01"),
        ("VPN keeps disconnecting or fails authentication", "kb_vpn_01"),
        ("Docker Daemon Socket Failure and Port Binding", "kb_docker_01"),
        ("Git SSH Key Permission Denied and Agent Setup", "kb_git_01"),
        ("SentinelOne and CrowdStrike EDR False Positive", "kb_edr_01"),
        ("AWS and Azure CLI SSO Credentials Expiration", "kb_cloud_01")
    ]

    for query_text, expected_kb_id in test_cases:
        results = await qdrant_manager.search_kb(query_text, limit=1)
        assert len(results) > 0
        top_match = results[0]
        assert top_match["id"] == expected_kb_id
