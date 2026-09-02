"""Integration tests for appointment endpoints."""
import pytest
from datetime import datetime, timedelta


class TestAvailableSlots:
    """Tests for available slots endpoint."""
    
    @pytest.mark.asyncio
    async def test_available_slots_no_doctor(self, client):
        """Non-existent doctor should return 404."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        response = await client.get(f"/appointments/available-slots?doctor_id=fake-id&date={tomorrow}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_available_slots_past_date(self, client):
        """Past date should return 400."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        response = await client.get(f"/appointments/available-slots?doctor_id=fake-id&date={yesterday}")
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_available_slots_invalid_date_format(self, client):
        """Invalid date format should return 422."""
        response = await client.get("/appointments/available-slots?doctor_id=fake-id&date=01-15-2025")
        assert response.status_code == 422


class TestCreateAppointment:
    """Tests for creating appointments."""
    
    @pytest.mark.asyncio
    async def test_create_appointment_unauthorized(self, client):
        """Creating appointment without auth should fail."""
        response = await client.post("/appointments", json={
            "doctor_id": "fake-id",
            "appointment_datetime": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "reason": "Checkup"
        })
        assert response.status_code in [401, 403]  # Either is acceptable
    
    @pytest.mark.asyncio
    async def test_create_appointment_invalid_doctor(self, client, patient_token):
        """Appointment with non-existent doctor should fail."""
        response = await client.post("/appointments",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={
                "doctor_id": "nonexistent-doctor",
                "appointment_datetime": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "reason": "Checkup"
            }
        )
        assert response.status_code == 404


class TestListAppointments:
    """Tests for listing appointments."""
    
    @pytest.mark.asyncio
    async def test_list_appointments_unauthorized(self, client):
        """Listing appointments without auth should fail."""
        response = await client.get("/appointments")
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_list_appointments_empty(self, client, patient_token):
        """New patient should have no appointments."""
        response = await client.get("/appointments",
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert response.status_code == 200
        assert response.json() == []


class TestGetAppointment:
    """Tests for getting single appointment."""
    
    @pytest.mark.asyncio
    async def test_get_appointment_unauthorized(self, client):
        """Getting appointment without auth should fail."""
        response = await client.get("/appointments/fake-id")
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_get_appointment_not_found(self, client, patient_token):
        """Non-existent appointment should return 404."""
        response = await client.get("/appointments/nonexistent-id",
            headers={"Authorization": f"Bearer {patient_token}"}
        )
        assert response.status_code == 404


class TestCancelAppointment:
    """Tests for canceling appointments."""
    
    @pytest.mark.asyncio
    async def test_cancel_appointment_unauthorized(self, client):
        """Canceling without auth should fail."""
        response = await client.patch("/appointments/fake-id/cancel", json={})
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_cancel_appointment_not_found(self, client, patient_token):
        """Canceling non-existent appointment should fail."""
        response = await client.patch("/appointments/nonexistent-id/cancel",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"cancellation_reason": "Changed my mind"}
        )
        assert response.status_code == 404
