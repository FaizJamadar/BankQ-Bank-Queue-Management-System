import hashlib
import random
import httpx
from datetime import date, time
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import Base, engine, get_db
from models import Appointment, Branch, Counter, Service, StatusEnum, RoleEnum
from auth import router as auth_router, get_current_user, require_role

Base.metadata.create_all(bind=engine)

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
BANK_CONTEXT = "You are BankQ Assistant, a helpful chatbot for BankQ — a bank queue management system. The bank offers: Cash Deposit, Cash Withdrawal, Loan Inquiry, Account Opening, Demand Draft. Branches in Bangalore, Delhi, Mumbai. Customers book slots online (9AM-5PM, 30-min slots) and check in with a 4-digit PIN at the kiosk. ONLY answer BankQ and banking related questions. If asked anything unrelated, politely say you can only help with BankQ topics. Be short and friendly."

app = FastAPI(title="BankQ - Bank Queue Management System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, branch_id: int, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(branch_id, []).append(ws)

    def disconnect(self, branch_id: int, ws: WebSocket):
        self.active.get(branch_id, []).remove(ws)

    async def broadcast(self, branch_id: int, message: dict):
        for ws in self.active.get(branch_id, []):
            await ws.send_json(message)


manager = ConnectionManager()

# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_qr_hash(customer_id: int, branch_id: int, slot: time, booking_date: date) -> str:
    raw = f"{customer_id}-{branch_id}-{slot}-{booking_date}"
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_pin() -> str:
    return str(random.randint(1000, 9999))


def generate_token(prefix: str, branch_id: int, booking_date: date, db: Session) -> str:
    count = (
        db.query(Appointment)
        .filter(
            Appointment.branch_id == branch_id,
            Appointment.booking_date == booking_date,
            Appointment.token_number.like(f"{prefix}-%"),
        )
        .count()
    )
    return f"{prefix}-{100 + count + 1}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class BookRequest(BaseModel):
    branch_id: int
    service_id: int
    booking_date: date
    slot_start_time: time


class QRVerifyRequest(BaseModel):
    qr_hash: Optional[str] = None
    pin_code: Optional[str] = None


class CallNextRequest(BaseModel):
    branch_id: int
    counter_id: int


# ── Lookup Routes ────────────────────────────────────────────────────────────

@app.get("/branches")
def get_branches(db: Session = Depends(get_db)):
    branches = db.query(Branch).all()
    return [{"branch_id": b.branch_id, "branch_name": b.branch_name, "city": b.city} for b in branches]

@app.get("/services")
def get_services(db: Session = Depends(get_db)):
    services = db.query(Service).all()
    return [{"service_id": s.service_id, "service_name": s.service_name, "service_code_prefix": s.service_code_prefix, "avg_duration_minutes": s.avg_duration_minutes} for s in services]

@app.get("/counters")
def get_counters(branch_id: int, db: Session = Depends(get_db)):
    counters = db.query(Counter).filter(Counter.branch_id == branch_id).all()
    return [{"counter_id": c.counter_id, "counter_number": c.counter_number, "branch_id": c.branch_id} for c in counters]

@app.post("/ai/chat")
async def ai_chat(req: ChatRequest):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={
                    "model": "openai/gpt-oss-20b",
                    "messages": [
                        {"role": "system", "content": BANK_CONTEXT},
                        {"role": "user", "content": req.message},
                    ],
                    "max_tokens": 200,
                },
            )
            result = resp.json()
            reply = result["choices"][0]["message"]["content"]
            return {"reply": reply}
    except Exception:
        return {"reply": "I can only help with BankQ and banking related questions. Try asking about booking a slot, services, branches, or kiosk check-in! 😊"}


@app.get("/appointments/my")
def my_appointments(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    appts = (
        db.query(Appointment)
        .filter(Appointment.customer_id == current_user.user_id)
        .order_by(Appointment.booking_date.desc(), Appointment.slot_start_time.desc())
        .all()
    )
    return [
        {
            "appointment_id": a.appointment_id,
            "token_number": a.token_number,
            "pin_code": a.pin_code,
            "status": a.status,
            "booking_date": str(a.booking_date),
            "slot_start_time": str(a.slot_start_time)[:5],
            "branch_name": a.branch.branch_name,
            "service_name": a.service.service_name,
        }
        for a in appts
    ]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/appointments/book", status_code=201)
async def book_appointment(
    req: BookRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Double-booking check
    conflict = (
        db.query(Appointment)
        .filter(
            Appointment.customer_id == current_user.user_id,
            Appointment.branch_id == req.branch_id,
            Appointment.booking_date == req.booking_date,
            Appointment.slot_start_time == req.slot_start_time,
            Appointment.status.notin_([StatusEnum.CANCELLED]),
        )
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Slot already booked for this customer")

    service = db.query(Service).filter(Service.service_id == req.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    branch = db.query(Branch).filter(Branch.branch_id == req.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    qr_hash = generate_qr_hash(
        current_user.user_id, req.branch_id, req.slot_start_time, req.booking_date
    )
    token = generate_token(service.service_code_prefix, req.branch_id, req.booking_date, db)

    pin = generate_pin()
    appointment = Appointment(
        token_number=token,
        customer_id=current_user.user_id,
        branch_id=req.branch_id,
        service_id=req.service_id,
        booking_date=req.booking_date,
        slot_start_time=req.slot_start_time,
        qr_hash=qr_hash,
        pin_code=pin,
        status=StatusEnum.BOOKED,
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return {"appointment_id": appointment.appointment_id, "token": token, "qr_hash": qr_hash, "pin_code": pin}


@app.post("/kiosk/verify")
async def kiosk_verify(
    req: QRVerifyRequest,
    db: Session = Depends(get_db),
    _=Depends(require_role(RoleEnum.SECURITY, RoleEnum.ADMIN)),
):
    if not req.qr_hash and not req.pin_code:
        raise HTTPException(status_code=400, detail="Provide qr_hash or pin_code")

    if req.pin_code:
        appt = db.query(Appointment).filter(Appointment.pin_code == req.pin_code).first()
    else:
        appt = db.query(Appointment).filter(Appointment.qr_hash == req.qr_hash).first()

    if not appt:
        raise HTTPException(status_code=404, detail="Invalid QR code or PIN")
    if appt.status != StatusEnum.BOOKED:
        raise HTTPException(status_code=400, detail=f"Token already in status: {appt.status}")

    appt.status = StatusEnum.CHECKED_IN
    db.commit()

    await manager.broadcast(
        appt.branch_id,
        {"event": "CHECKED_IN", "token": appt.token_number, "appointment_id": appt.appointment_id},
    )
    return {"message": "Check-in successful", "token": appt.token_number}


@app.post("/teller/call-next")
async def call_next(
    req: CallNextRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.TELLER, RoleEnum.ADMIN)),
):
    # Verify counter belongs to teller
    counter = db.query(Counter).filter(
        Counter.counter_id == req.counter_id,
        Counter.branch_id == req.branch_id,
    ).first()
    if not counter:
        raise HTTPException(status_code=404, detail="Counter not found")

    next_appt = (
        db.query(Appointment)
        .filter(
            Appointment.branch_id == req.branch_id,
            Appointment.status == StatusEnum.CHECKED_IN,
        )
        .order_by(Appointment.slot_start_time, Appointment.appointment_id)
        .first()
    )
    if not next_appt:
        raise HTTPException(status_code=404, detail="No checked-in customers waiting")

    next_appt.status = StatusEnum.IN_PROGRESS
    next_appt.counter_id = req.counter_id
    db.commit()

    await manager.broadcast(
        req.branch_id,
        {
            "event": "CALLED",
            "token": next_appt.token_number,
            "counter": counter.counter_number,
            "appointment_id": next_appt.appointment_id,
        },
    )
    return {"token": next_appt.token_number, "counter": counter.counter_number}


@app.post("/teller/complete")
async def complete_token(
    appointment_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role(RoleEnum.TELLER, RoleEnum.ADMIN)),
):
    appt = db.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status != StatusEnum.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Token is not IN_PROGRESS")

    appt.status = StatusEnum.COMPLETED
    db.commit()

    await manager.broadcast(
        appt.branch_id,
        {"event": "COMPLETED", "token": appt.token_number, "appointment_id": appt.appointment_id},
    )
    return {"message": "Token completed", "token": appt.token_number}


@app.websocket("/ws/queue/{branch_id}")
async def queue_websocket(branch_id: int, websocket: WebSocket):
    await manager.connect(branch_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive, ignore pings
    except WebSocketDisconnect:
        manager.disconnect(branch_id, websocket)
