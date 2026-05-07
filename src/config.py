import os
from dotenv import load_dotenv

# JWT Configuration
load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("CRITICAL: JWT_SECRET environment variable is missing.")

JWT_ALGORITHM = "HS256"

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")