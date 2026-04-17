"""SQLAlchemy ORM models for TESS Curl Script Library.

Supports persistent storage and indexing of MAST .sh curl script files.
Enables chunked batch job creation without re-upload.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, String, Text, Boolean, DateTime, BigInteger, ForeignKey, Index, UniqueConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agata.models import Base


class TessCurlScript(Base):
    """
    Represents a MAST .sh curl script file stored on disk.

    Attributes:
        id: Unique identifier
        script_code: Unique code (TESSCURL-YYYY-NNNNN)
        original_filename: Filename from upload
        stored_filename: Filename on disk
        association_id: Owning association (NULL = superuser)
        parse_state: 'uploading' | 'parsing' | 'ready' | 'failed'
        parse_error: Error detail if failed
        total_entries: Total curl lines in the script (line count only, not DB-indexed)
        entries_processed: Count of entries processed by completed jobs (offset tracking)
        created_by: FK to agata_users
        created_at: Creation timestamp
        updated_at: Last modification timestamp

    Relationships:
        creator: User who uploaded the script
        jobs: List of TessImportJob rows that reference this script

    Properties:
        is_ready: True if parse_state == 'ready'
        next_unprocessed_offset: Zero-based index of first entry to process (= entries_processed)
        batches_remaining: Estimated number of 500-entry batches left to process

    Note:
        Entries are no longer stored in a DB table (agata_tess_curl_entries removed).
        Instead, entries are read directly from the file on-disk when needed by get_batch_from_file().
    """

    __tablename__ = "agata_tess_curl_scripts"
    __table_args__ = (
        Index('idx_tess_curl_scripts_assoc', 'association_id'),
        Index('idx_tess_curl_scripts_state', 'parse_state'),
        Index('idx_tess_curl_scripts_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    script_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment='Unique code e.g. TESSCURL-2026-00001'
    )
    original_filename: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment='Original filename from upload'
    )
    stored_filename: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment='Filename on disk'
    )
    association_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment='Owning association (NULL = superuser)'
    )

    parse_state: Mapped[str] = mapped_column(
        Enum('uploading', 'parsing', 'ready', 'failed', name='tess_curl_script_parse_state'),
        nullable=False, default='uploading',
        comment='Background parse state'
    )
    parse_error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment='Error detail if parse_state=failed'
    )

    total_entries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment='Total curl lines successfully parsed'
    )
    entries_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment='Count of entries marked is_processed=TRUE'
    )

    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("agata_users.id", ondelete="CASCADE"), nullable=False,
        comment='agata_users.id (UUID)'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        comment='Creation timestamp'
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
        comment='Last modification timestamp'
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], lazy="select"
    )
    jobs: Mapped[list["TessImportJob"]] = relationship(
        "TessImportJob", back_populates="curl_script", lazy="select",
        foreign_keys="TessImportJob.curl_script_id"
    )

    @property
    def is_ready(self) -> bool:
        """True if parse_state == 'ready'."""
        return self.parse_state == 'ready'

    @property
    def next_unprocessed_offset(self) -> int:
        """Zero-based index of first entry not yet assigned to a completed job."""
        return self.entries_processed

    @property
    def batches_remaining(self) -> int:
        """Estimated number of 500-entry batches left to process."""
        remaining = self.total_entries - self.entries_processed
        return (remaining + 499) // 500  # ceiling division
