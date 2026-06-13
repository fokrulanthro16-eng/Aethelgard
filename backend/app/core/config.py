from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Aethelgard API"
    ENVIRONMENT: str = "development"

    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str | None = Field(default=None)
    AWS_SECRET_ACCESS_KEY: str | None = Field(default=None)
    DYNAMODB_TABLE_NAME: str = "Aethelgard_Vault"
    DEAD_MAN_SWITCH_DAYS: int = 90

    # Point to DynamoDB Local / LocalStack for offline development; leave blank for real AWS
    DYNAMODB_ENDPOINT_URL: str | None = Field(default=None)

    # ── Encryption ────────────────────────────────────────────────────────────
    # "local"  → derive key from LOCAL_MASTER_KEY using HKDF; no AWS dependency
    # "kms"    → envelope encryption via AWS KMS (production path)
    ENCRYPTION_MODE: str = Field(default="local")

    # Required when ENCRYPTION_MODE=local. Use a long random string. Never commit.
    LOCAL_MASTER_KEY: str | None = Field(default=None)

    # Required when ENCRYPTION_MODE=kms. ARN or alias of the KMS CMK.
    KMS_KEY_ID: str | None = Field(default=None)

    # Release token expiry window (hours). After this, the nominee link is invalid.
    RELEASE_TOKEN_EXPIRY_HOURS: int = Field(default=72)

    # Optional — will be None when not set; never hardcode
    GEMINI_API_KEY: str | None = Field(default=None)


settings = Settings()
