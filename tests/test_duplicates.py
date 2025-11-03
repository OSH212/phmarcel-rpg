"""Test duplicate document detection using SHA256 hashing."""

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from main import app


@pytest.mark.asyncio
async def test_duplicate_upload_same_intake():
    """Test that uploading the same file twice to the same intake is rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client and intake
        client_data = {
            "name": "Duplicate Test Client",
            "email": "duplicate@example.com",
            "complexity": "simple"
        }
        response = await client.post("/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        intake_data = {
            "client_id": client_id,
            "fiscal_year": 2025
        }
        response = await client.post("/intakes", json=intake_data)
        assert response.status_code == 201
        intake_id = response.json()["id"]
        
        # Upload T4 document first time
        t4_path = Path("sample_docs/T4_sample.JPG")
        assert t4_path.exists(), "T4 sample file not found"
        
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        first_upload_id = response.json()["id"]
        first_upload_sha256 = response.json()["sha256"]
        
        # Attempt to upload the same file again
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample_duplicate.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        
        # Should be rejected with 409 Conflict
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()
        assert first_upload_sha256 in response.json()["detail"]


@pytest.mark.asyncio
async def test_same_file_different_intakes_allowed():
    """Test that the same file can be uploaded to different intakes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client
        client_data = {
            "name": "Multi-Intake Test",
            "email": "multi@example.com",
            "complexity": "simple"
        }
        response = await client.post("/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        # Create first intake
        intake_data_1 = {
            "client_id": client_id,
            "fiscal_year": 2024
        }
        response = await client.post("/intakes", json=intake_data_1)
        assert response.status_code == 201
        intake_id_1 = response.json()["id"]
        
        # Create second intake
        intake_data_2 = {
            "client_id": client_id,
            "fiscal_year": 2025
        }
        response = await client.post("/intakes", json=intake_data_2)
        assert response.status_code == 201
        intake_id_2 = response.json()["id"]
        
        # Upload same file to first intake
        t4_path = Path("sample_docs/T4_sample.JPG")
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id_1}/documents",
                files=files
            )
        assert response.status_code == 201
        sha256_intake_1 = response.json()["sha256"]
        
        # Upload same file to second intake - should succeed
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id_2}/documents",
                files=files
            )
        assert response.status_code == 201
        sha256_intake_2 = response.json()["sha256"]
        
        # SHA256 should be the same (same file)
        assert sha256_intake_1 == sha256_intake_2
        
        # But both uploads should succeed (different intakes)
        assert response.json()["intake_id"] == intake_id_2


@pytest.mark.asyncio
async def test_different_files_same_intake_allowed():
    """Test that different files can be uploaded to the same intake."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client and intake
        client_data = {
            "name": "Multi-File Test",
            "email": "multifile@example.com",
            "complexity": "average"
        }
        response = await client.post("/clients", json=client_data)
        client_id = response.json()["id"]
        
        intake_data = {
            "client_id": client_id,
            "fiscal_year": 2025
        }
        response = await client.post("/intakes", json=intake_data)
        intake_id = response.json()["id"]
        
        # Upload T4
        t4_path = Path("sample_docs/T4_sample.JPG")
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        t4_sha256 = response.json()["sha256"]
        
        # Upload ID
        id_path = Path("sample_docs/drivers_license.jpg")
        with open(id_path, "rb") as f:
            files = {"file": ("drivers_license.jpg", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        id_sha256 = response.json()["sha256"]
        
        # SHA256 should be different (different files)
        assert t4_sha256 != id_sha256
        
        # Both uploads should succeed
        assert response.status_code == 201


@pytest.mark.asyncio
async def test_sha256_hash_consistency():
    """Test that SHA256 hash is calculated consistently."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client and two intakes
        client_data = {
            "name": "Hash Test",
            "email": "hash@example.com",
            "complexity": "simple"
        }
        response = await client.post("/clients", json=client_data)
        client_id = response.json()["id"]
        
        intake_data_1 = {"client_id": client_id, "fiscal_year": 2024}
        response = await client.post("/intakes", json=intake_data_1)
        intake_id_1 = response.json()["id"]
        
        intake_data_2 = {"client_id": client_id, "fiscal_year": 2025}
        response = await client.post("/intakes", json=intake_data_2)
        intake_id_2 = response.json()["id"]
        
        # Upload same file to both intakes
        t4_path = Path("sample_docs/T4_sample.JPG")
        
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response_1 = await client.post(
                f"/intakes/{intake_id_1}/documents",
                files=files
            )
        
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response_2 = await client.post(
                f"/intakes/{intake_id_2}/documents",
                files=files
            )
        
        # Both should succeed
        assert response_1.status_code == 201
        assert response_2.status_code == 201
        
        # SHA256 should be identical
        assert response_1.json()["sha256"] == response_2.json()["sha256"]
        
        # SHA256 should be 64 characters (hex)
        sha256 = response_1.json()["sha256"]
        assert len(sha256) == 64
        assert all(c in "0123456789abcdef" for c in sha256)

