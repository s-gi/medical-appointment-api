# Medical Appointment API

A **secure**, production-ready REST API for managing medical practice appointments built with FastAPI and Python.

## Features

### Security (HIPAA-Conscious Design)
- **JWT Authentication** with access & refresh tokens (stateless)
- **Role-Based Access Control** (Admin, Doctor, Patient)
- **Password Security**: bcrypt hashing, strength validation (12+ chars, mixed case, numbers, symbols)
- **Account Lockout**: Automatic lockout after 5 failed login attempts
- **Data Encryption**: AES encryption for sensitive patient data (names, DOB, phone, insurance)
- **Rate Limiting**: Application-level protection against brute force
- **Security Headers**: HSTS, X-Frame-Options, X-Content-Type-Options
- **Audit Logging**: Track all user actions with IP and user agent
- **CORS Protection**: Configurable allowed origins
- **Input Validation**: Strict Pydantic models prevent injection attacks

### Appointment Management
- Browse available doctors by specialization
- View doctor schedules and available time slots
- Book, confirm, cancel, and complete appointments
- Filter appointments by date and status
- Doctor notes with encryption

### User Management
- Patient self-registration
- Admin-managed doctor accounts
- Account activation/deactivation
- Password change functionality

## Tech Stack

- **Framework**: FastAPI 0.110+
- **Database**: SQLite with SQLAlchemy 2.0 (async)
- **Authentication**: python-jose (JWT)
- **Password Hashing**: bcrypt
- **Encryption**: cryptography (Fernet/AES)
- **Validation**: Pydantic 2.0
- **Rate Limiting**: slowapi
- **Testing**: pytest + pytest-asyncio

## Run the Tests

Complete step 1 below (**Clone & Setup** — create the venv, install dependencies), then jump to [Testing](#testing). No `.env` configuration or running the server required.

## Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/s-gi/medical-appointment-api.git
cd medical-appointment-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment
```bash
cp .env.example .env
```

Edit `.env` with secure keys:
```env
SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_EMAIL=admin@clinic.com
ADMIN_PASSWORD=YourSecurePassword123!
```

### 3. Run the Server
```bash
uvicorn app.main:app --reload
```

### 4. Access the API
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/

## Testing

Each test calls the FastAPI app directly in-process via `httpx.ASGITransport` (no live server, no network socket) and gets its own isolated in-memory SQLite database through a fixture — so tests run fully independently and never touch each other's data.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py -v
```

**Test Coverage:**
| Category | Tests |
|----------|-------|
| Security (password, encryption, JWT) | 23 |
| Authentication endpoints | 18 |
| Doctor endpoints | 4 |
| Appointment endpoints | 14 |
| **Total** | **59** |

## API Endpoints

### Authentication
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/register` | Register patient | No |
| POST | `/auth/login` | Login & get tokens | No |
| POST | `/auth/refresh` | Refresh access token | No |
| POST | `/auth/logout` | Logout | Yes |
| POST | `/auth/change-password` | Change password | Yes |
| GET | `/auth/me` | Get current user | Yes |

### Doctors
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/doctors` | List doctors | No |
| GET | `/doctors/{id}` | Get doctor details | No |
| POST | `/doctors` | Create doctor | Admin |
| POST | `/doctors/{id}/schedules` | Add schedule | Doctor/Admin |
| PATCH | `/doctors/{id}/availability` | Update availability | Doctor/Admin |

### Appointments
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/appointments/available-slots` | Get available slots | No |
| POST | `/appointments` | Book appointment | Patient |
| GET | `/appointments` | List my appointments | Yes |
| GET | `/appointments/{id}` | Get appointment | Yes |
| PATCH | `/appointments/{id}/cancel` | Cancel appointment | Yes |
| PATCH | `/appointments/{id}/confirm` | Confirm appointment | Doctor/Admin |
| PATCH | `/appointments/{id}/complete` | Mark completed | Doctor/Admin |

### Admin
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/admin/users` | List all users | Admin |
| PATCH | `/admin/users/{id}/activate` | Activate user | Admin |
| PATCH | `/admin/users/{id}/deactivate` | Deactivate user | Admin |
| GET | `/admin/audit-logs` | View audit logs | Admin |
| GET | `/admin/stats` | System statistics | Admin |

## Security Architecture

### Authentication Flow
```
[Client] → POST /auth/login (email, password)
    ↓
[Server] → Verify password (bcrypt)
    ↓
[Server] → Generate JWT tokens (access + refresh)
    ↓
[Client] ← { access_token, refresh_token }
    ↓
[Client] → API requests with Authorization: Bearer <token>
```

### Data Protection
- **PHI (Protected Health Information)**: Encrypted at rest using AES-256
- **Passwords**: Hashed with bcrypt (12 rounds)
- **Tokens**: Signed JWTs (HS256) with explicit algorithm allow-listing on verification, configurable expiration

### DDoS/DoS Mitigation

This API implements **application-level rate limiting**. For production deployment, additional layers are recommended:

| Layer | Protection | Tool Examples |
|-------|------------|---------------|
| Edge/CDN | Volumetric attack mitigation | Cloudflare, AWS Shield |
| Load Balancer | Traffic distribution, IP blocking | nginx, AWS ALB |
| Application | Request rate limiting | slowapi (included) |

## Project Structure

```
medical-appointment-api/
├── app/
│   ├── auth/           # Auth dependencies
│   ├── models/         # SQLAlchemy models
│   ├── routes/         # API endpoints
│   ├── schemas/        # Pydantic models
│   ├── security/       # Encryption, JWT, password
│   ├── utils/          # Audit logging
│   ├── config.py       # Settings
│   ├── database.py     # DB connection
│   └── main.py         # FastAPI app
├── tests/
│   ├── conftest.py     # Test fixtures
│   ├── test_auth.py
│   ├── test_appointments.py
│   ├── test_doctors.py
│   └── test_security.py
├── .env.example
├── .gitignore
├── pytest.ini
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Production Deployment

### Recommendations
1. **Database**: Use PostgreSQL instead of SQLite
2. **HTTPS**: Deploy behind nginx/Caddy with TLS
3. **Secrets**: Use environment variables or secret managers (AWS Secrets Manager, HashiCorp Vault)
4. **Monitoring**: Add logging aggregation (ELK, CloudWatch)
5. **DDoS Protection**: Use Cloudflare or AWS Shield
6. **Backups**: Configure automated database backups

### Environment Variables
```bash
SECRET_KEY=<secure-random-key>
ENCRYPTION_KEY=<secure-random-key>
DATABASE_URL=postgresql+asyncpg://user:pass@host/db
ALLOWED_ORIGINS=https://your-frontend.com
ADMIN_EMAIL=admin@your-domain.com
ADMIN_PASSWORD=<strong-password>
```

## License

MIT License - see [LICENSE](LICENSE) for details.
