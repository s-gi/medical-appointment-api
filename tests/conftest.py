import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client():
    """Create test client with fresh database per test."""
    from app.database import get_db
    from app.main import app
    
    # Each test gets a completely new in-memory database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async def override_get_db():
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def valid_patient_data():
    """Valid patient registration data."""
    return {
        "email": "patient@test.com",
        "password": "SecurePass123!",
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": "1990-01-15",
        "phone": "+1234567890"
    }


@pytest.fixture
def valid_login_data():
    """Valid login data."""
    return {
        "email": "patient@test.com",
        "password": "SecurePass123!"
    }


@pytest.fixture
async def patient_token(client, valid_patient_data, valid_login_data):
    """Register patient and get access token."""
    await client.post("/auth/register", json=valid_patient_data)
    response = await client.post("/auth/login", json=valid_login_data)
    return response.json()["access_token"]
