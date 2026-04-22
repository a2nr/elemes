from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize Limiter without app for the app factory pattern
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)
