from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import logging

logger = logging.getLogger(__name__)

API_KEY_NAME = 'X-Aura-API-Key'
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# logic is simple enough, removed return type hint to be faster
async def verify_api_key(api_key: str = Security(api_key_header)):
    # moving this import here to break the circular dependency with settings.py
    from config.settings import settings

    if not api_key:
        logger.warning('Access denied: API Key missing from header.')
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Aura-API-Key header is required."
        )

    # FIXME: validating against env var for now.
    # we need to move this to a proper database check for multi-tenant support.
    if api_key != settings.AURA_GLOBAL_API_KEY:
        logger.warning(f"invalid api key used: {api_key[:5]}***")
        raise HTTPException(
            status_code=403,
            detail='Invalid or revoked credentials.'
        )

    return api_key
