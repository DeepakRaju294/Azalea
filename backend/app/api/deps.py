import os
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.db.database import SessionLocal


load_dotenv()

security = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_supabase_jwks_url() -> str:
    supabase_url = os.getenv("SUPABASE_URL")

    if not supabase_url:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL is not set on the backend.",
        )

    return f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def decode_supabase_token(token: str) -> dict[str, Any]:
    try:
        jwks_client = PyJWKClient(get_supabase_jwks_url())
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            options={"verify_aud": False},
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Authorization token has expired.",
        )

    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authorization token: {str(exc)}",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Failed to verify authorization token: {str(exc)}",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization token.",
        )

    token = credentials.credentials
    payload = decode_supabase_token(token)

    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authorization token is missing user id.",
        )

    return {
        "user_id": str(user_id),
        "email": payload.get("email"),
        "claims": payload,
    }


def get_current_user_id(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> str:
    return str(current_user["user_id"])
