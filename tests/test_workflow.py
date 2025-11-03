"""Test end-to-end workflow: upload → classify → extract → checklist."""

import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path
from main import app


@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete workflow from client creation to checklist completion.
    
    Flow:
    1. Create client (simple complexity: T4 + id)
    2. Create intake
    3. Upload T4 document
    4. Upload ID document
    5. Classify documents
    6. Extract data from documents
    7. Verify checklist is complete and intake status is 'done'
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Create client
        client_data = {
            "name": "Test Client",
            "email": "test@example.com",
            "complexity": "simple"
        }
        response = await client.post("/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        # Step 2: Create intake
        intake_data = {
            "client_id": client_id,
            "fiscal_year": 2025
        }
        response = await client.post("/intakes", json=intake_data)
        assert response.status_code == 201
        intake_id = response.json()["id"]
        intake_status = response.json()["status"]
        assert intake_status == "open"
        
        # Step 3: Upload T4 document
        t4_path = Path("sample_docs/T4_sample.JPG")
        assert t4_path.exists(), "T4 sample file not found"
        
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        t4_doc_id = response.json()["id"]
        assert response.json()["doc_kind"] == "unknown"
        
        # Step 4: Upload ID document
        id_path = Path("sample_docs/drivers_license.jpg")
        assert id_path.exists(), "ID sample file not found"
        
        with open(id_path, "rb") as f:
            files = {"file": ("drivers_license.jpg", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        id_doc_id = response.json()["id"]
        assert response.json()["doc_kind"] == "unknown"
        
        # Step 5: Classify all documents in intake
        response = await client.post(f"/intakes/{intake_id}/classify")
        assert response.status_code == 200
        assert response.json()["total_classified"] == 2
        
        # Verify classifications
        classifications = response.json()["classifications"]
        doc_kinds = {c["document_id"]: c["doc_kind"] for c in classifications}
        assert doc_kinds[t4_doc_id] == "T4"
        assert doc_kinds[id_doc_id] == "id"
        
        # Step 6: Extract data from all documents
        response = await client.post(f"/intakes/{intake_id}/extract")
        assert response.status_code == 200
        assert response.json()["total_extracted"] == 2
        
        # Verify extractions
        extractions = response.json()["extractions"]
        for extraction in extractions:
            assert extraction["extracted_data"] is not None
            assert extraction["fields_extracted"] > 0
        
        # Step 7: Check checklist status
        response = await client.get(f"/intakes/{intake_id}/checklist")
        assert response.status_code == 200
        checklist = response.json()

        # Verify all items are received
        assert checklist["intake_status"] == "done"
        assert checklist["is_complete"] == True
        assert checklist["total_received"] == checklist["total_expected"]
        assert checklist["total_received"] == 2  # Simple client: T4 + ID
        assert checklist["overall_progress"] == 100.0

        # Verify checklist items
        for item in checklist["items"]:
            assert item["status"] == "received"
            assert item["is_complete"] == True


@pytest.mark.asyncio
async def test_partial_workflow():
    """Test workflow with only partial document upload (intake stays open)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client (average complexity: T4 + id + 2 receipts)
        client_data = {
            "name": "Partial Test Client",
            "email": "partial@example.com",
            "complexity": "average"
        }
        response = await client.post("/clients", json=client_data)
        assert response.status_code == 201
        client_id = response.json()["id"]
        
        # Create intake
        intake_data = {
            "client_id": client_id,
            "fiscal_year": 2025
        }
        response = await client.post("/intakes", json=intake_data)
        assert response.status_code == 201
        intake_id = response.json()["id"]
        
        # Upload only T4 (missing id and 2 receipts)
        t4_path = Path("sample_docs/T4_sample.JPG")
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        assert response.status_code == 201
        
        # Classify and extract
        await client.post(f"/intakes/{intake_id}/classify")
        await client.post(f"/intakes/{intake_id}/extract")
        
        # Check checklist - should still be open
        response = await client.get(f"/intakes/{intake_id}/checklist")
        assert response.status_code == 200
        checklist = response.json()
        
        # Intake should still be open (not all items received)
        assert checklist["intake_status"] == "open"
        assert checklist["is_complete"] == False
        assert checklist["total_received"] < checklist["total_expected"]
        # Average client needs T4 + ID + 2 receipts = 4 total, we only uploaded 1
        assert checklist["total_received"] == 1
        assert checklist["total_expected"] == 4


@pytest.mark.asyncio
async def test_classification_accuracy():
    """Test that classification correctly identifies document types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create client and intake
        client_data = {
            "name": "Classification Test",
            "email": "classify@example.com",
            "complexity": "simple"
        }
        response = await client.post("/clients", json=client_data)
        client_id = response.json()["id"]
        
        intake_data = {"client_id": client_id, "fiscal_year": 2025}
        response = await client.post("/intakes", json=intake_data)
        intake_id = response.json()["id"]
        
        # Upload and classify T4
        t4_path = Path("sample_docs/T4_sample.JPG")
        with open(t4_path, "rb") as f:
            files = {"file": ("T4_sample.JPG", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        t4_doc_id = response.json()["id"]
        
        response = await client.post(f"/documents/{t4_doc_id}/classify")
        assert response.status_code == 200
        assert response.json()["doc_kind"] == "T4"
        
        # Upload and classify ID
        id_path = Path("sample_docs/drivers_license.jpg")
        with open(id_path, "rb") as f:
            files = {"file": ("drivers_license.jpg", f, "image/jpeg")}
            response = await client.post(
                f"/intakes/{intake_id}/documents",
                files=files
            )
        id_doc_id = response.json()["id"]
        
        response = await client.post(f"/documents/{id_doc_id}/classify")
        assert response.status_code == 200
        assert response.json()["doc_kind"] == "id"
        
        # Upload and classify receipt
        receipt_path = Path("sample_docs/receipts/001.jpg")
        if receipt_path.exists():
            with open(receipt_path, "rb") as f:
                files = {"file": ("receipt_001.jpg", f, "image/jpeg")}
                response = await client.post(
                    f"/intakes/{intake_id}/documents",
                    files=files
                )
            receipt_doc_id = response.json()["id"]
            
            response = await client.post(f"/documents/{receipt_doc_id}/classify")
            assert response.status_code == 200
            assert response.json()["doc_kind"] == "receipt"

