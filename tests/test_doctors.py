"""Integration tests for doctor endpoints."""
import pytest


class TestListDoctors:
    """Tests for listing doctors."""
    
    @pytest.mark.asyncio
    async def test_list_doctors_empty(self, client):
        """Empty doctor list should return empty array."""
        response = await client.get("/doctors")
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_list_doctors_public(self, client):
        """Doctor list should be publicly accessible."""
        response = await client.get("/doctors")
        assert response.status_code == 200


class TestGetDoctor:
    """Tests for getting doctor details."""
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_doctor(self, client):
        """Non-existent doctor should return 404."""
        response = await client.get("/doctors/nonexistent-id")
        assert response.status_code == 404


class TestDoctorCreation:
    """Tests for doctor creation (admin only)."""
    
    @pytest.mark.asyncio
    async def test_create_doctor_unauthorized(self, client):
        """Creating doctor without auth should fail."""
        response = await client.post("/doctors", json={
            "email": "doctor@test.com",
            "password": "DoctorPass123!",
            "first_name": "Jane",
            "last_name": "Smith",
            "specialization": "Cardiology",
            "license_number": "MD12345"
        })
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_create_doctor_patient_forbidden(self, client, patient_token):
        """Patient should not be able to create doctor."""
        response = await client.post("/doctors",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={
                "email": "doctor@test.com",
                "password": "DoctorPass123!",
                "first_name": "Jane",
                "last_name": "Smith",
                "specialization": "Cardiology",
                "license_number": "MD12345"
            }
        )
        assert response.status_code == 403
