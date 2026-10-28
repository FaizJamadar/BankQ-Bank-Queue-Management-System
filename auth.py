import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import jwt
from pydantic import BaseModel

from database import get_db
from models import User, RoleEnum, BankAccount

SECRET_KEY = os.getenv("SECRET_KEY", "bankq-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    full_name: str
    phone_number: str
    password: str
    last4: str
    role: RoleEnum = RoleEnum.CUSTOMER


def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = int(payload.get("sub"))
    except (jwt.PyJWTError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_role(*roles: RoleEnum):
    def dependency(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    # Verify bank account last 4 digits
    account = db.query(BankAccount).filter(BankAccount.last4 == req.last4).first()
    if not account:
        raise HTTPException(status_code=400, detail="Bank account not found. Invalid last 4 digits.")
    if account.is_registered == 1:
        raise HTTPException(status_code=400, detail="This bank account is already linked to another user.")
    if db.query(User).filter(User.phone_number == req.phone_number).first():
        raise HTTPException(status_code=400, detail="Phone number already registered")
    user = User(
        full_name=req.full_name,
        phone_number=req.phone_number,
        password_hash=pwd_context.hash(req.password),
        role=req.role,
    )
    db.add(user)
    account.is_registered = 1
    db.commit()
    db.refresh(user)
    return {"user_id": user.user_id, "message": "Registered successfully", "role": user.role.value}


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == form.username).first()
    if not user or not pwd_context.verify(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_token({"sub": user.user_id, "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}
