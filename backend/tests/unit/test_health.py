import pytest

@pytest.mark.asyncio
async def test_health_check_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Chargeback Shield API"
    assert "environment" in data
