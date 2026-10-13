import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

conn = psycopg.connect(
    host=os.getenv("PGSQL_HOSTNAME"),
    port=os.getenv("PGSQL_PORT", "5432"),
    dbname=os.getenv("PGSQL_DBNAME"),
    user=os.getenv("PGSQL_USER"),
    password=os.getenv("PGSQL_PASSWORD"),
)

print("✅ Connected!")
print("✅ Printing Users List:")
with conn.cursor() as cur:
    cur.execute("SELECT * FROM new_users")

    rows = cur.fetchall()

    for row in rows:
        print(row)

conn.close()

print("Connection closed.")
