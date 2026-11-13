"""Runtime configuration for the user service."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "user-service")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./users.db")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "120"))
    admin_email: str = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    admin_full_name: str = os.getenv("ADMIN_FULL_NAME", "MyCima Admin")


settings = Settings()
