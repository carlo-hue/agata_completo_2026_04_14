# agata/auth_models/saved_query.py
from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from agata.models import Base


class SavedQuery(Base):
    """Query personale salvata da un utente per un contesto specifico."""
    __tablename__ = "agata_saved_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("agata_users.id", ondelete="CASCADE"), nullable=False)
    context: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_params: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class QueryPreset(Base):
    """Preset di query definito da un superuser, visibile a tutti o a un'associazione specifica."""
    __tablename__ = "agata_query_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    context: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_params: Mapped[dict] = mapped_column(JSON, nullable=False)
    association_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agata_associations.id", ondelete="CASCADE"), nullable=True
    )
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("agata_users.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
