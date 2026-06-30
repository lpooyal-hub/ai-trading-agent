import secrets

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_admin_api_key(
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    if not settings.require_admin_api_key:
        return
    if not settings.admin_api_key_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key protection is required but ADMIN_API_KEY is not configured.",
        )

    supplied_key = x_admin_api_key or _bearer_token(authorization)
    if not supplied_key or not secrets.compare_digest(supplied_key, settings.admin_api_key or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid admin API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()
