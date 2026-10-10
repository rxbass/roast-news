"""Roast model: one generated (or refused/failed) roast of a news article."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.enums import RoastStatus, SpiceLevel

if TYPE_CHECKING:
    from app.models.user import User


def _enum_values(enum_cls: type[SpiceLevel] | type[RoastStatus]) -> list[str]:
    """Persist the lowercase enum values (not member names) in PostgreSQL."""
    return [member.value for member in enum_cls]


class Roast(TimestampMixin, Base):
    __tablename__ = "roasts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    article_title: Mapped[str] = mapped_column(String(500), nullable=False)
    article_excerpt: Mapped[str] = mapped_column(String(500), nullable=False)
    spice_level: Mapped[SpiceLevel] = mapped_column(
        Enum(SpiceLevel, name="spice_level", values_callable=_enum_values),
        nullable=False,
    )
    roast_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RoastStatus] = mapped_column(
        Enum(RoastStatus, name="roast_status", values_callable=_enum_values),
        nullable=False,
    )
    refusal_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    client_ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="roasts")

    __table_args__ = (
        Index("ix_roasts_cache_lookup", "url_hash", "spice_level", "status", "created_at"),
        Index("ix_roasts_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Roast id={self.id} status={self.status} spice={self.spice_level}>"


# Defined after the class so it can use a DESC column expression for "My Roasts" history.
Index("ix_roasts_user_history", Roast.user_id, Roast.created_at.desc())
