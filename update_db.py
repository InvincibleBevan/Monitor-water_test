import sqlite3
import os

db_path = 'water_quality.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Add missing columns
        cursor.execute("ALTER TABLE telemetry_data ADD COLUMN ai_label TEXT")
        cursor.execute("ALTER TABLE telemetry_data ADD COLUMN ai_score REAL")
        cursor.execute("ALTER TABLE telemetry_data ADD COLUMN ai_is_anomaly BOOLEAN")
        conn.commit()
        print("Success: Columns added to telemetry_data")
    except sqlite3.OperationalError as e:
        print(f"Operational error (maybe columns already exist?): {e}")
    except Exception as e:
        print(f"Error updating DB: {e}")
    finally:
        conn.close()
else:
    print("DB file not found")
