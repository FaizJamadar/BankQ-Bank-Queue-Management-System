from database import engine
from models import Base
from sqlalchemy import text

# Create any missing tables (including bank_accounts)
Base.metadata.create_all(bind=engine)
print("Tables synced.")

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE appointments ADD COLUMN pin_code VARCHAR(4) NULL"))
        print("Added pin_code column")
    except Exception as e:
        print(f"pin_code: {e}")

    try:
        conn.execute(text("ALTER TABLE appointments DROP COLUMN deposit_amount"))
        print("Dropped deposit_amount")
    except Exception as e:
        print(f"deposit_amount: {e}")

    try:
        conn.execute(text("ALTER TABLE appointments DROP COLUMN pan_number"))
        print("Dropped pan_number")
    except Exception as e:
        print(f"pan_number: {e}")

    try:
        conn.execute(text("ALTER TABLE branches DROP COLUMN lunch_start_time"))
        print("Dropped lunch_start_time")
    except Exception as e:
        print(f"lunch_start_time: {e}")

    try:
        conn.execute(text("ALTER TABLE branches DROP COLUMN lunch_end_time"))
        print("Dropped lunch_end_time")
    except Exception as e:
        print(f"lunch_end_time: {e}")

    conn.commit()
    print("\nMigration done.")
