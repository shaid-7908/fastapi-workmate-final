import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class EnvConfig:
    PORT: str
    MONGODB_URL: str
    MONGODB_DB_NAME: str
    JWT_SECRET: str
    JWT_ACCESSTOKEN_TIME: str
    JWT_REFRESHTOKEN_TIME: str
    EMAIL_PASS: str
    EMAIL_USER: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIDERCT_URI: str
    HOST_ENVIORMENT: str
    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str
    AWS_REGION: str
    AWS_BUCKET :str

env_config = EnvConfig(
    PORT=os.getenv("PORT", ""),
    MONGODB_URL=os.getenv("MONGODB_URL", ""),
    MONGODB_DB_NAME=os.getenv("MONGODB_DB_NAME", ""),
    JWT_SECRET=os.getenv("JWT_SECRET", ""),
    JWT_ACCESSTOKEN_TIME=os.getenv("JWT_ACCESSTOKEN_TIME", ""),
    JWT_REFRESHTOKEN_TIME=os.getenv("JWT_REFRESHTOKEN_TIME", ""),
    EMAIL_PASS=os.getenv("EMAIL_PASS", ""),
    EMAIL_USER=os.getenv("EMAIL_USER", ""),
    GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID", ""),
    GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    GOOGLE_REDIDERCT_URI=os.getenv("GOOGLE_REDIDERCT_URI", ""),
    HOST_ENVIORMENT=os.getenv("HOST_ENVIORMENT", ""),
    AWS_ACCESS_KEY=os.getenv("AWS_ACCESS_KEY", ""),
    AWS_SECRET_KEY=os.getenv("AWS_SECRET_KEY", ""),
    AWS_REGION=os.getenv("AWS_REGION", ""),
    AWS_BUCKET=os.getenv("AWS_BUCKET", ""),
)


