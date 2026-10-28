import bcrypt, hashlib, sys
from datetime import date
from database import SessionLocal
from models import User, Appointment, RoleEnum, StatusEnum

out = open('seed2_log.txt', 'w')

db = SessionLocal()
try:
    def hp(pw): return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    existing_phones = [u.phone_number for u in db.query(User).all()]
    out.write(f"Existing users: {len(existing_phones)}\n")

    user_data = [
        ('Ravi Kumar',   '9876543210', 'Customer@123', RoleEnum.CUSTOMER),
        ('Anita Desai',  '9876543211', 'Customer@123', RoleEnum.CUSTOMER),
        ('Suresh Nair',  '9876543212', 'Customer@123', RoleEnum.CUSTOMER),
        ('Meena Pillai', '9876543213', 'Customer@123', RoleEnum.CUSTOMER),
        ('Arjun Mehta',  '9876543214', 'Customer@123', RoleEnum.CUSTOMER),
        ('Priya Sharma', '9000000002', 'Teller@123',   RoleEnum.TELLER),
        ('Karan Teller', '9000000003', 'Teller@123',   RoleEnum.TELLER),
        ('Ramesh Guard', '9000000004', 'Security@123', RoleEnum.SECURITY),
        ('Admin User',   '9000000001', 'Admin@123',    RoleEnum.ADMIN),
    ]
    new_users = [User(full_name=n, phone_number=p, password_hash=hp(pw), role=r)
                 for n, p, pw, r in user_data if p not in existing_phones]
    if new_users:
        db.add_all(new_users)
        db.commit()
        out.write(f"Added {len(new_users)} new users\n")
    else:
        out.write("All users already exist\n")

    # Add appointments if less than 5 exist
    appt_count = db.query(Appointment).count()
    out.write(f"Existing appointments: {appt_count}\n")

    if appt_count < 5:
        customers = db.query(User).filter(User.role == RoleEnum.CUSTOMER).limit(5).all()
        today = date.today()
        appt_data = [
            (customers[0], 1, 1, '09:00:00', 'COMPLETED',   'C', None,    None),
            (customers[1], 1, 2, '09:30:00', 'COMPLETED',   'W', None,    None),
            (customers[2], 1, 1, '10:00:00', 'IN_PROGRESS', 'C', None,    None),
            (customers[3], 1, 3, '10:30:00', 'CHECKED_IN',  'L', None,    None),
            (customers[4], 1, 4, '11:00:00', 'CHECKED_IN',  'A', None,    None),
            (customers[0], 2, 1, '09:00:00', 'BOOKED',      'C', 75000.0, 'ABCDE1234F'),
            (customers[1], 2, 2, '09:30:00', 'BOOKED',      'W', None,    None),
            (customers[2], 3, 1, '10:00:00', 'BOOKED',      'D', None,    None),
        ]
        token_counters = {}
        appointments = []
        for cust, branch_id, svc_id, slot, status, prefix, deposit, pan in appt_data:
            key = (branch_id, prefix)
            token_counters[key] = token_counters.get(key, 100) + 1
            token = f"{prefix}-{token_counters[key]}"
            qr = hashlib.sha256(f"{cust.user_id}-{branch_id}-{slot}-{today}".encode()).hexdigest()
            # skip if qr_hash already exists
            if db.query(Appointment).filter(Appointment.qr_hash == qr).first():
                continue
            appointments.append(Appointment(
                token_number=token, customer_id=cust.user_id, branch_id=branch_id,
                service_id=svc_id, booking_date=today, slot_start_time=slot,
                deposit_amount=deposit, pan_number=pan, qr_hash=qr,
                status=StatusEnum(status),
                counter_id=1 if status in ('IN_PROGRESS', 'COMPLETED') else None,
            ))
        db.add_all(appointments)
        db.commit()
        out.write(f"Added {len(appointments)} appointments\n")

    out.write(f"\nFinal counts:\n")
    out.write(f"  Users        : {db.query(User).count()}\n")
    out.write(f"  Appointments : {db.query(Appointment).count()}\n")

except Exception as e:
    db.rollback()
    out.write(f"ERROR: {e}\n")
finally:
    db.close()
    out.close()
