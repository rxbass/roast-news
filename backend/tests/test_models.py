"""Model reprs (handy in logs) never leak sensitive fields."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth.jwt import hash_token
from app.models.refresh_token import RefreshToken
from app.models.roast import Roast
from app.models.user import User


def test_reprs(db: Session, user: User, roast_factory: Callable[..., Roast]) -> None:
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token("secret-refresh"),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(token)
    db.commit()
    roast = roast_factory(user=user)

    assert repr(user) == f"<User id={user.id} email='machan@example.com'>"
    assert repr(token) == f"<RefreshToken id={token.id} user_id={user.id} revoked=False>"
    assert "secret" not in repr(token)
    assert repr(roast).startswith(f"<Roast id={roast.id} status=")
