import logging
from typing import Any, Dict, Optional
import httpx
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.core.config import settings

_jwks_cache: Optional[Dict] = None
logger = logging.getLogger(__name__)


# Description: Function `_normalize_roles` implementation.
# Inputs: raw
# Output: list[str]
# Exceptions: Propagates exceptions raised by internal operations.
def _normalize_roles(raw: Any) -> list[str]:
    """Normalize role claims from common token formats into a lowercase role list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        # Handle single role values as well as comma-separated role strings.
        parts = [p.strip() for p in raw.split(",")]
        return [p.lower() for p in parts if p]
    if isinstance(raw, (list, tuple, set)):
        out = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip().lower())
        return out
    return []


# Description: Function `_extract_roles` implementation.
# Inputs: payload
# Output: list[str]
# Exceptions: Propagates exceptions raised by internal operations.
def _extract_roles(payload: Dict[str, Any]) -> list[str]:
    """Extract roles from standard and custom Keycloak/OIDC claim shapes."""
    roles = set(_normalize_roles(payload.get("roles")))
    roles.update(_normalize_roles(payload.get("role")))
    # Support literal dotted claims when protocol mappers emit flattened keys.
    roles.update(_normalize_roles(payload.get("realm_access.roles")))
    roles.update(_normalize_roles(payload.get("resource_access.roles")))

    realm_access = payload.get("realm_access", {}) or {}
    roles.update(_normalize_roles(realm_access.get("roles")))

    resource_access = payload.get("resource_access", {}) or {}
    for client_data in resource_access.values():
        if isinstance(client_data, dict):
            roles.update(_normalize_roles(client_data.get("roles")))

    # Catch-all for custom protocol mappers that emit role claims under non-standard keys
    # such as "x_roles", "app.roles", or URL-namespace claims ending with "roles".
    for key, value in payload.items():
        key_lower = str(key).lower()
        if key_lower.endswith("roles"):
            roles.update(_normalize_roles(value))

    return list(roles)


# Description: Function `get_jwks` implementation.
# Inputs: None
# Output: Dict
# Exceptions: Propagates exceptions raised by internal operations.
async def get_jwks() -> Dict:
    """Fetch and cache the Keycloak JWKS used to validate bearer tokens."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/certs"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


# Description: Function `_fetch_userinfo` implementation.
# Inputs: token
# Output: Dict[str, Any]
# Exceptions: Propagates exceptions raised by internal operations.
async def _fetch_userinfo(token: str) -> Dict[str, Any]:
    """Fetch userinfo claims from Keycloak as a fallback source for role claims."""
    url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/userinfo"
    )
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        return resp.json()


# Description: Function `verify_token` implementation.
# Inputs: token
# Output: Dict[str, Any]
# Exceptions: Propagates exceptions raised by internal operations.
async def verify_token(token: str) -> Dict[str, Any]:
    """Validate a Keycloak token and normalize the claims used by the API."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        jwks = await get_jwks()
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break
        if not rsa_key:
            logger.warning("JWT validation failed because no matching signing key was found")
            raise credentials_exception

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_CLIENT_ID,
            options={"verify_aud": False},
        )

        sub: str = payload.get("sub", "")
        email: str = payload.get("email", "")
        roles = _extract_roles(payload)
        if not roles:
            logger.warning("No role claims found in access token for sub=%s; attempting userinfo fallback", sub)
            try:
                userinfo = await _fetch_userinfo(token)
                fallback_roles = _extract_roles(userinfo)
                if fallback_roles:
                    roles = fallback_roles
                    logger.info(
                        "Recovered role claims from userinfo for sub=%s roles=%s",
                        sub,
                        roles,
                    )
            except httpx.HTTPError:
                logger.warning("Userinfo role fallback failed for sub=%s due to upstream HTTP error", sub)
        # Support both "organization" claim and custom "tenant_id" claim
        tenant_id: str = payload.get("tenant_id", payload.get("organization", "default"))

        return {
            "sub": sub,
            "email": email,
            "roles": roles,
            "tenant_id": tenant_id,
        }
    except JWTError:
        logger.warning("JWT validation failed due to an invalid or expired token")
        raise credentials_exception
    except httpx.HTTPError:
        logger.exception("Unable to retrieve JWKS from Keycloak during token validation")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provider is temporarily unavailable. Try again later.",
        )
    except Exception:
        logger.exception("Unexpected token verification failure")
        raise credentials_exception
