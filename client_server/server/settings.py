import json
import os
from passlib.context import CryptContext

try:
    with open("conf.json", "r") as config:
        settings = json.load(config)
        ALGORITHM = settings.get("ALGORITHM")
        SECRET_KEY = settings.get("SECRET_KEY")
        ACCESS_TOKEN_EXPIRE_MINUTES = settings.get("ACCESS_TOKEN_EXPIRE_MINUTES")

except FileNotFoundError:
    ALGORITHM = os.environ("ALGORITHM")
    SECRET_KEY = os.environ("SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES = os.environ("ACCESS_TOKEN_EXPIRE_MINUTES")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")