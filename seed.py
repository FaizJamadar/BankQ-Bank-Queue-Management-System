import hashlib
import random
from datetime import date
from passlib.context import CryptContext
from database import SessionLocal, engine
from models import Base, Branch, Service, Counter, User, Appointment, BankAccount, RoleEnum, StatusEnum

Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

def hp(pw):
    return pwd_context.hash(pw)

try:
    if db.query(BankAccount).count() == 0:
        db.add_all([
            BankAccount(holder_name='Ravi Kumar',  last4='1234', is_registered=0),
            BankAccount(holder_name='Anita Desai', last4='5678', is_registered=0),
            BankAccount(holder_name='Demo User 1', last4='4444', is_registered=0),
            BankAccount(holder_name='Demo User 2', last4='7777', is_registered=0),
        ])
        db.commit()
        print(f"BankAccounts: {db.query(BankAccount).count()} inserted")
    else:
        print(f"BankAccounts: {db.query(BankAccount).count()} already exist")

    if db.query(Branch).count() == 0:
        db.add_all([
            Branch(branch_name='MG Road Main Branch',    city='Bangalore'),
            Branch(branch_name='Connaught Place Branch', city='Delhi'),
            Branch(branch_name='Bandra West Branch',     city='Mumbai'),
        ])
        db.commit()
        print(f"Branches    : {db.query(Branch).count()} inserted")
    else:
        print(f"Branches    : {db.query(Branch).count()} already exist")

    if db.query(Service).count() == 0:
        db.add_all([
            Service(service_name='Cash Deposit',    service_code_prefix='C', avg_duration_minutes=10),
            Service(service_name='Cash Withdrawal', service_code_prefix='W', avg_duration_minutes=10),
            Service(service_name='Loan Inquiry',    service_code_prefix='L', avg_duration_minutes=20),
            Service(service_name='Account Opening', service_code_prefix='A', avg_duration_minutes=30),
            Service(service_name='Demand Draft',    service_code_prefix='D', avg_duration_minutes=15),
        ])
        db.commit()
        print(f"Services    : {db.query(Service).count()} inserted")
    else:
        print(f"Services    : {db.query(Service).count()} already exist")

    if db.query(Counter).count() == 0:
        db.add_all([
            Counter(branch_id=1, counter_number=1),
            Counter(branch_id=1, counter_number=2),
            Counter(branch_id=2, counter_number=1),
            Counter(branch_id=3, counter_number=1),
        ])
        db.commit()
        print(f"Counters    : {db.query(Counter).count()} inserted")
    else:
        print(f"Counters    : {db.query(Counter).count()} already exist")

    existing_phones = [u.phone_number for u in db.query(User).all()]
    user_data = [
        ('Ravi Kumar',   '9876543210', 'pass123', RoleEnum.CUSTOMER),
        ('Anita Desai',  '9876543211', 'pass123', RoleEnum.CUSTOMER),
        ('Suresh Nair',  '9876543212', 'pass123', RoleEnum.CUSTOMER),
        ('Meena Pillai', '9876543213', 'pass123', RoleEnum.CUSTOMER),
        ('Arjun Mehta',  '9876543214', 'pass123', RoleEnum.CUSTOMER),
        ('Priya Sharma', '9000000002', 'pass123', RoleEnum.TELLER),
        ('Karan Teller', '9000000003', 'pass123', RoleEnum.TELLER),
        ('Ramesh Guard', '9000000004', 'pass123', RoleEnum.SECURITY),
        ('Admin User',   '9000000001', 'pass123', RoleEnum.ADMIN),
    ]
    new_users = [User(full_name=n, phone_number=p, password_hash=hp(pw), role=r)
                 for n, p, pw, r in user_data if p not in existing_phones]
    if new_users:
        db.add_all(new_users)
        db.commit()
        print(f"Users       : {len(new_users)} inserted")
    else:
        print(f"Users       : {db.query(User).count()} already exist")

    if db.query(Appointment).count() == 0:
        customers = db.query(User).filter(User.role == RoleEnum.CUSTOMER).limit(5).all()
        today = date.today()
        appt_data = [
            (customers[0], 1, 1, '09:00:00', 'COMPLETED',   'C'),
            (customers[1], 1, 2, '09:30:00', 'COMPLETED',   'W'),
            (customers[2], 1, 1, '10:00:00', 'IN_PROGRESS', 'C'),
            (customers[3], 1, 3, '10:30:00', 'CHECKED_IN',  'L'),
            (customers[4], 1, 4, '11:00:00', 'CHECKED_IN',  'A'),
            (customers[0], 2, 1, '09:00:00', 'BOOKED',      'C'),
            (customers[1], 2, 2, '09:30:00', 'BOOKED',      'W'),
            (customers[2], 3, 1, '10:00:00', 'BOOKED',      'D'),
        ]
        token_counters = {}
        appointments = []
        for cust, branch_id, svc_id, slot, status, prefix in appt_data:
            key = (branch_id, prefix)
            token_counters[key] = token_counters.get(key, 100) + 1
            token = f"{prefix}-{token_counters[key]}"
            qr = hashlib.sha256(f"{cust.user_id}-{branch_id}-{slot}-{today}".encode()).hexdigest()
            if db.query(Appointment).filter(Appointment.qr_hash == qr).first():
                continue
            appointments.append(Appointment(
                token_number=token, customer_id=cust.user_id, branch_id=branch_id,
                service_id=svc_id, booking_date=today, slot_start_time=slot,
                qr_hash=qr, pin_code=str(random.randint(1000, 9999)),
                status=StatusEnum(status),
                counter_id=1 if status in ('IN_PROGRESS', 'COMPLETED') else None,
            ))
        db.add_all(appointments)
        db.commit()
        print(f"Appointments: {db.query(Appointment).count()} inserted")
    else:
        print(f"Appointments: {db.query(Appointment).count()} already exist")

    print("\nDone! All passwords are: pass123")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
