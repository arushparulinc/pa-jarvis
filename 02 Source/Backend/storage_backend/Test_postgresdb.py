import os

from dotenv import load_dotenv
import psycopg

load_dotenv()

conn = psycopg.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
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