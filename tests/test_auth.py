"""Integration tests for authentication endpoints."""
import pytest


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """Root endpoint should return healthy status."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "Medical Appointment API" in data["service"]


class TestPatientRegistration:
    """Tests for patient registration."""
    
    @pytest.mark.asyncio
    async def test_register_patient_success(self, client, valid_patient_data):
        """Valid registration should succeed."""
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == valid_patient_data["email"]
        assert data["role"] == "patient"
        assert data["is_active"] is True
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, valid_patient_data):
        """Duplicate email should fail."""
        await client.post("/auth/register", json=valid_patient_data)
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 409
    
    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client, valid_patient_data):
        """Invalid email should fail."""
        valid_patient_data["email"] = "not-an-email"
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_weak_password(self, client, valid_patient_data):
        """Weak password should fail."""
        valid_patient_data["password"] = "weak"
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_invalid_phone(self, client, valid_patient_data):
        """Invalid phone should fail."""
        valid_patient_data["phone"] = "123"
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_register_invalid_dob_format(self, client, valid_patient_data):
        """Invalid date format should fail."""
        valid_patient_data["date_of_birth"] = "01-15-1990"
        response = await client.post("/auth/register", json=valid_patient_data)
        assert response.status_code == 422


class TestLogin:
    """Tests for login endpoint."""
    
    @pytest.mark.asyncio
    async def test_login_success(self, client, patient_token):
        """Valid login should return tokens (patient_token fixture does login)."""
        assert patient_token is not None
        assert len(patient_token) > 0
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, valid_patient_data):
        """Wrong password should fail."""
        await client.post("/auth/register", json=valid_patient_data)
        response = await client.post("/auth/login", json={
            "email": valid_patient_data["email"],
            "password": "WrongPassword123!"
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Non-existent user should fail."""
        response = await client.post("/auth/login", json={
            "email": "nobody@test.com",
            "password": "SomePassword123!"
        })
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self, client):
        """Invalid email format should fail."""
        response = await client.post("/auth/login", json={
            "email": "not-valid",
            "password": "SomePassword123!"
        })
        assert response.status_code == 422


class TestTokenRefresh:
    """Tests for token refresh endpoint."""
    
    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client):
        """Valid refresh token should return new tokens."""
        # Register a new user for this test only
        reg_response = await client.post("/auth/register", json={
            "email": "refresh_test@test.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-15",
            "phone": "+1234567890"
        })
        assert reg_response.status_code == 201
        
        # Login
        login_response = await client.post("/auth/login", json={
            "email": "refresh_test@test.com",
            "password": "SecurePass123!"
        })
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh
        response = await client.post("/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, client):
        """Invalid refresh token should fail."""
        response = await client.post("/auth/refresh", json={
            "refresh_token": "invalid.token.here"
        })
        assert response.status_code == 401


class TestAuthenticatedEndpoints:
    """Tests for endpoints requiring authentication."""
    
    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client, valid_patient_data, patient_token):
        """Authenticated user should get their info."""
        response = await client.get("/auth/me", headers={
            "Authorization": f"Bearer {patient_token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == valid_patient_data["email"]
    
    @pytest.mark.asyncio
    async def test_get_me_no_token(self, client):
        """Request without token should fail."""
        response = await client.get("/auth/me")
        assert response.status_code in [401, 403]
    
    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client):
        """Invalid token should fail."""
        response = await client.get("/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert response.status_code == 401


class TestPasswordChange:
    """Tests for password change endpoint."""
    
    @pytest.mark.asyncio
    async def test_change_password_success(self, client):
        """Valid password change should succeed."""
        # Register new user for this test
        await client.post("/auth/register", json={
            "email": "pwchange@test.com",
            "password": "SecurePass123!",
            "first_name": "Test",
            "last_name": "User",
            "date_of_birth": "1990-01-15",
            "phone": "+1234567890"
        })
        
        # Login
        login_response = await client.post("/auth/login", json={
            "email": "pwchange@test.com",
            "password": "SecurePass123!"
        })
        token = login_response.json()["access_token"]
        
        # Change password
        response = await client.post("/auth/change-password", 
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "SecurePass123!",
                "new_password": "NewSecurePass456!"
            }
        )
        assert response.status_code == 200
        
        # Verify new password works
        login_response = await client.post("/auth/login", json={
            "email": "pwchange@test.com",
            "password": "NewSecurePass456!"
        })
        assert login_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client, patient_token):
        """Wrong current password should fail."""
        response = await client.post("/auth/change-password",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={
                "current_password": "WrongPassword123!",
                "new_password": "NewSecurePass456!"
            }
        )
        assert response.status_code == 400
