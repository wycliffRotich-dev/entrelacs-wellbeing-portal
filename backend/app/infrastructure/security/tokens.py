"""Signed access tokens. The token carries only the user id; role and tenant come from the DB."""
from datetime import datetime, timedelta
from uuid import UUID

import jwt

_ALGORITHM = "HS256"


class TokenError(Exception):
    """The token is missing, malformed, expired, or not validly signed."""


class TokenService:
    def __init__(self, secret: str, ttl: timedelta) -> None:
        self._secret = secret
        self._ttl = ttl

    def issue(self, user_id: UUID, *, now: datetime) -> str:
        claims = {"sub": str(user_id), "exp": int((now + self._ttl).timestamp())}
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str, *, now: datetime) -> UUID:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],  # pinned: rejects alg=none and other algorithms
                options={"require": ["exp", "sub"], "verify_exp": False},
            )
            # Expiry is checked against the injected clock so tests are deterministic.
            if int(claims["exp"]) <= int(now.timestamp()):
                raise TokenError("token expired")
            return UUID(claims["sub"])
        except TokenError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError):
            raise TokenError("invalid token") from None
