from __future__ import annotations

from typing import TYPE_CHECKING
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.aggregate import FunnelStep  # for Funnel → steps

class Funnel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "funnels"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_funnels_tenant", "tenant_id"),
    )

    tenant: Mapped[Tenant] = relationship("Tenant", back_populates="funnels")
    steps: Mapped[list[FunnelStep]] = relationship(
        "FunnelStep",
        back_populates="funnel",
        order_by="FunnelStep.position",
    )


class FunnelStep(Base, UUIDMixin):
    __tablename__ = "funnel_steps"

    funnel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funnels.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url_pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    conversion_rate: Mapped[float] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_funnel_steps_funnel", "funnel_id", "position"),
    )

    funnel: Mapped[Funnel] = relationship("Funnel", back_populates="steps")