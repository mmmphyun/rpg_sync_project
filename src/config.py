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

# Redis Resilience Configuration
REDIS_CONNECT_TIMEOUT = float(os.getenv("REDIS_CONNECT_TIMEOUT", "1.5"))
REDIS_SOCKET_TIMEOUT = float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.5"))
REDIS_HEALTHCHECK_INTERVAL = int(os.getenv("REDIS_HEALTHCHECK_INTERVAL", "30"))

# Discord Configuration
DISCORD_INVITE_URL = os.getenv("DISCORD_INVITE_URL", "https://discord.gg/3prVGQud2c")