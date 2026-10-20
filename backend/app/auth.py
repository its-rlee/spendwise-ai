
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import httpx
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

load_dotenv(
    Path(__file__).resolve().parent.parent / ".env"
)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
PUBLISHABLE_KEY = os.environ["SUPABASE_PUBLISHABLE_KEY"]

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str


def unauthorized():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required or token invalid",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> AuthUser:
    if credentials is None:
        raise unauthorized()

    token = credentials.credentials

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": PUBLISHABLE_KEY,
                    "Authorization": f"Bearer {token}",
                },
            )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        ) from exc

    if response.status_code in (400, 401, 403):
        raise unauthorized()

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Authentication verification unavailable",
        )

    try:
        user_id = str(UUID(response.json()["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise unauthorized() from exc

    return AuthUser(id=user_id)
