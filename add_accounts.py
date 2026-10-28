from database import SessionLocal
from models import BankAccount

db = SessionLocal()
try:
    existing = [a.last4 for a in db.query(BankAccount).all()]
    to_add = []
    if '4444' not in existing:
        to_add.append(BankAccount(holder_name='Demo User 1', last4='4444', is_registered=0))
    if '7777' not in existing:
        to_add.append(BankAccount(holder_name='Demo User 2', last4='7777', is_registered=0))
    if to_add:
        db.add_all(to_add)
        db.commit()
        print(f"Added {len(to_add)} new bank account(s)")
    else:
        print("Already exist")
    for a in db.query(BankAccount).all():
        print(f"  last4={a.last4}  name={a.holder_name}  used={a.is_registered}")
finally:
    db.close()
