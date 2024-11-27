import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import Base, create_app
from datetime import date

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

# Create the engine and session for testing
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)

# Create the database tables
Base.metadata.create_all(bind=engine)

# Create the FastAPI app with the test database
app = create_app(database_url=SQLALCHEMY_DATABASE_URL, engine=engine, session_local=TestingSessionLocal)


# Asynchronous client fixture
@pytest_asyncio.fixture(scope="module")
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# Fixture to create an expense and provide its ID
@pytest_asyncio.fixture(scope="module")
async def test_expense_id(async_client):
    today_str = date.today().strftime("%Y-%m-%d")
    response = await async_client.post(
        "/api/expenses/",
        json={
            "description": "Test Expense",
            "amount": 100.0,
            "date": today_str
        }
    )
    assert response.status_code == 200
    data = response.json()
    expense_id = data["id"]
    return expense_id


# Test to create an expense
@pytest.mark.asyncio
async def test_create_expense(async_client):
    today_str = date.today().strftime("%Y-%m-%d")
    response = await async_client.post(
        "/api/expenses/",
        json={
            "description": "Another Test Expense",
            "amount": 200.0,
            "date": today_str
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Another Test Expense"
    assert data["amount"] == 200.0


# Test to read expenses
@pytest.mark.asyncio
async def test_read_expenses(async_client, test_expense_id):
    response = await async_client.get("/api/expenses/")
    assert response.status_code == 200
    data = response.json()
    # Uncomment the line below to print the expenses data for debugging
    # print("Response Data:", data)
    assert len(data) >= 1
    # Check that the test_expense_id is in the returned data
    assert any(expense["id"] == test_expense_id for expense in data)


# Test to get total expenses
@pytest.mark.asyncio
async def test_total_expenses_api(async_client):
    response = await async_client.get("/api/expenses/total")
    assert response.status_code == 200
    total = response.json()
    # Since we have two expenses: 100.0 and 200.0
    expected_total = 300.0
    assert total == expected_total


# Test to update an expense
@pytest.mark.asyncio
async def test_update_expense(async_client, test_expense_id):
    today_str = date.today().strftime("%Y-%m-%d")
    response = await async_client.put(
        f"/api/expenses/{test_expense_id}",
        json={
            "description": "Updated Test Expense",
            "amount": 150.0,
            "date": today_str
        }
    )
    if response.status_code != 200:
        print("Update Expense Response:", response.status_code, response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated Test Expense"
    assert data["amount"] == 150.0


# Test to delete an expense
@pytest.mark.asyncio
async def test_delete_expense(async_client, test_expense_id):
    response = await async_client.delete(f"/api/expenses/{test_expense_id}")
    if response.status_code != 200:
        print("Delete Expense Response:", response.status_code, response.text)
    assert response.status_code == 200
    data = response.json()
    assert data["detail"] == "Expense deleted"

    # Verify that the expense is deleted
    response = await async_client.get("/api/expenses/")
    assert response.status_code == 200
    data = response.json()
    # Uncomment the line below to print the expenses data after deletion
    # print("Expenses Data After Deletion:", data)
    assert not any(expense["id"] == test_expense_id for expense in data)


# Test the web routes
@pytest.mark.asyncio
async def test_web_routes(async_client):
    # Test the home page
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "Expense Tracker" in response.text

    # Test the add expense page
    response = await async_client.get("/add")
    assert response.status_code == 200
    assert "Add New Expense" in response.text
