from sqlalchemy import create_engine, text
import os

# Create engine with absolute path
db_path = '/app/moodle_llm.db'
if not os.path.exists(db_path):
    db_path = '/app/backend/moodle_llm.db'

engine = create_engine(f'sqlite:///{db_path}')

print(f"Running migration on database: {db_path}")

# Run migration
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE entregas ADD COLUMN local_file_path TEXT;"))
        conn.commit()
        print("Migration successful!")
except Exception as e:
    print(f"Error during migration: {e}")
