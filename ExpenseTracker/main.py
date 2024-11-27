from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import Column, Integer, String, Float, Date, func, extract, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.engine import Engine
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from starlette.templating import Jinja2Templates
import os

# Ensure the correct working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base class for SQLAlchemy models
Base = declarative_base()

# Expense model for SQLAlchemy
class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True)
    amount = Column(Float)
    date = Column(Date)

# Pydantic models
class ExpenseCreate(BaseModel):
    description: str
    amount: float
    date: date

class ExpenseUpdate(ExpenseCreate):
    pass  # Inherits fields from ExpenseCreate

class ExpenseRead(ExpenseCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)  # For Pydantic v2 compatibility

# Function to create the FastAPI app with injected dependencies
def create_app(
    database_url: Optional[str] = None,
    engine: Optional[Engine] = None,
    session_local: Optional[sessionmaker] = None,
):
    app = FastAPI()

    # Set up templates using absolute path
    templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

    # Database setup
    if database_url is None:
        database_url = f"sqlite:///{os.path.join(BASE_DIR, 'expenses.db')}"

    if engine is None:
        engine = create_engine(database_url, connect_args={"check_same_thread": False})

    if session_local is None:
        session_local = sessionmaker(bind=engine, autoflush=False)

    # Create the database tables
    Base.metadata.create_all(bind=engine)

    # Dependency to get DB session
    def get_db():
        db = session_local()
        try:
            yield db
        finally:
            db.close()

    # Web Routes

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request, db: Session = Depends(get_db)):
        expenses = db.query(Expense).all()
        total = db.query(func.sum(Expense.amount)).scalar() or 0.0
        return templates.TemplateResponse(
            request,
            "index.html",
            {"expenses": expenses, "total": total}
        )

    @app.get("/add", response_class=HTMLResponse)
    async def add_expense_form(request: Request):
        return templates.TemplateResponse(request, "add_expense.html", {})

    @app.post("/add")
    async def add_expense(
        description: str = Form(...),
        amount: float = Form(...),
        date: date = Form(...),
        db: Session = Depends(get_db)
    ):
        db_expense = Expense(description=description, amount=amount, date=date)
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)
        return RedirectResponse(url="/", status_code=303)

    @app.get("/update/{expense_id}", response_class=HTMLResponse)
    async def update_expense_form(expense_id: int, request: Request, db: Session = Depends(get_db)):
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        return templates.TemplateResponse(
            request,
            "update_expense.html",
            {"expense": expense}
        )

    @app.post("/update/{expense_id}")
    async def update_expense(
        expense_id: int,
        description: str = Form(...),
        amount: float = Form(...),
        date: date = Form(...),
        db: Session = Depends(get_db)
    ):
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if db_expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        db_expense.description = description
        db_expense.amount = amount
        db_expense.date = date
        db.commit()
        db.refresh(db_expense)
        return RedirectResponse(url="/", status_code=303)

    @app.post("/delete/{expense_id}")
    async def delete_expense(expense_id: int, db: Session = Depends(get_db)):
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if db_expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        db.delete(db_expense)
        db.commit()
        return RedirectResponse(url="/", status_code=303)

    # API Routes

    @app.post("/api/expenses/", response_model=ExpenseRead)
    def create_expense_api(expense: ExpenseCreate, db: Session = Depends(get_db)):
        db_expense = Expense(**expense.model_dump())
        db.add(db_expense)
        db.commit()
        db.refresh(db_expense)
        return ExpenseRead.model_validate(db_expense)

    @app.get("/api/expenses/", response_model=List[ExpenseRead])
    def read_expenses_api(db: Session = Depends(get_db)):
        expenses = db.query(Expense).all()
        return [ExpenseRead.model_validate(expense) for expense in expenses]

    @app.get("/api/expenses/total", response_model=float)
    def total_expenses_api(db: Session = Depends(get_db)):
        current_month = date.today().month
        current_year = date.today().year
        total = db.query(func.sum(Expense.amount)).filter(
            extract('month', Expense.date) == current_month,
            extract('year', Expense.date) == current_year
        ).scalar()
        return total or 0.0

    @app.put("/api/expenses/{expense_id}", response_model=ExpenseRead)
    def update_expense_api(
        expense_id: int,
        expense: ExpenseUpdate,
        db: Session = Depends(get_db)
    ):
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if db_expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        db_expense.description = expense.description
        db_expense.amount = expense.amount
        db_expense.date = expense.date
        db.commit()
        db.refresh(db_expense)
        return ExpenseRead.model_validate(db_expense)

    @app.delete("/api/expenses/{expense_id}")
    def delete_expense_api(expense_id: int, db: Session = Depends(get_db)):
        db_expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if db_expense is None:
            raise HTTPException(status_code=404, detail="Expense not found")
        db.delete(db_expense)
        db.commit()
        return {"detail": "Expense deleted"}

    # Return the app instance
    return app

# Create the app instance using default settings
app = create_app()
