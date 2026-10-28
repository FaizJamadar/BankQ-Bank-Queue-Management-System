import enum
from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Date, Time
from sqlalchemy.orm import relationship
from database import Base


class RoleEnum(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    TELLER = "TELLER"
    SECURITY = "SECURITY"
    ADMIN = "ADMIN"


class StatusEnum(str, enum.Enum):
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    account_id = Column(Integer, primary_key=True, index=True)
    holder_name = Column(String(100), nullable=False)
    last4 = Column(String(4), unique=True, nullable=False)
    is_registered = Column(Integer, default=0, nullable=False)  # 0=unused, 1=registered


class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(15), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.CUSTOMER, nullable=False)


class Branch(Base):
    __tablename__ = "branches"
    branch_id = Column(Integer, primary_key=True, index=True)
    branch_name = Column(String(100), nullable=False)
    city = Column(String(50), nullable=False)
    counters = relationship("Counter", back_populates="branch")
    appointments = relationship("Appointment", back_populates="branch")


class Service(Base):
    __tablename__ = "services"
    service_id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String(100), nullable=False)
    service_code_prefix = Column(String(5), nullable=False)
    avg_duration_minutes = Column(Integer, nullable=False)


class Counter(Base):
    __tablename__ = "counters"
    counter_id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.branch_id"), nullable=False)
    counter_number = Column(Integer, nullable=False)
    assigned_teller_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    branch = relationship("Branch", back_populates="counters")
    teller = relationship("User", foreign_keys=[assigned_teller_id])


class Appointment(Base):
    __tablename__ = "appointments"
    appointment_id = Column(Integer, primary_key=True, index=True)
    token_number = Column(String(20), nullable=False)
    customer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.branch_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.service_id"), nullable=False)
    counter_id = Column(Integer, ForeignKey("counters.counter_id"), nullable=True)
    booking_date = Column(Date, nullable=False)
    slot_start_time = Column(Time, nullable=False)
    qr_hash = Column(String(64), unique=True, nullable=False)
    pin_code = Column(String(4), nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.BOOKED, nullable=False)
    customer = relationship("User", foreign_keys=[customer_id])
    branch = relationship("Branch", back_populates="appointments")
    service = relationship("Service")
    counter = relationship("Counter")
