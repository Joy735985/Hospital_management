import bcrypt
from db import get_connection

username = "admin"
password = "admin123"
role = "admin"

pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

conn = get_connection()
cur = conn.cursor()
cur.execute(
    "INSERT INTO app_users(username, password_hash, role) VALUES (%s, %s, %s)",
    (username, pw_hash, role)
)
conn.commit()
cur.close()
conn.close()

print("Created:", username, password)
