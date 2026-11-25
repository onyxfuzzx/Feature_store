"""Generate local Docker secrets without overwriting an existing configuration."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env.docker"
with destination.open("x", encoding="utf-8") as output:
    output.write("APP_ENV=local\nADMIN_EMAIL=admin@featureops.local\n")
    for key in ("POSTGRES_PASSWORD", "SOURCE_DB_PASSWORD", "JWT_SECRET", "ADMIN_PASSWORD"):
        output.write(f"{key}={secrets.token_hex(24)}\n")
    output.write("CORS_ORIGINS=http://localhost:5173\nSEED_DEMO_DATA=false\n")
print("Created .env.docker. Read ADMIN_PASSWORD there to sign in.")
