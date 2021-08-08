import json
import os
from passlib.context import CryptContext

try:
    with open("conf.json", "r") as config:
        settings = json.load(config)
        ALGORITHM = settings.get("ALGORITHM")
        SECRET_KEY = settings.get("SECRET_KEY")
        ACCESS_TOKEN_EXPIRE_MINUTES = settings.get("ACCESS_TOKEN_EXPIRE_MINUTES")
        ADMIN_LOGIN = settings.get("ADMIN_LOGIN")
        ADMIN_PASSWORD = settings.get("ADMIN_PASSWORD")

except FileNotFoundError:
    ALGORITHM = os.environ.get("ALGORITHM")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES = os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES")
    ADMIN_LOGIN = os.environ.get("ADMIN_LOGIN")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")