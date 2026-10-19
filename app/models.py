
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, DateTime, func, Integer, Index, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index(
            "ux_transactions_source",
            "source_document_id",
            "source_index",
            unique=True,
        ),
        {"schema": "spendwise"},
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    merchant: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        default="Uncategorized",
        nullable=False
    )

    transaction_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False
    )

    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="debit",
    )

    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    source_index: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )



class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "spendwise"}

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    s3_key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        nullable=False,
    )

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    page_count: Mapped[int] = mapped_column(
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

class TransactionDraft(Base):
    __tablename__ = "transaction_drafts"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "source_index",
            name="uq_draft_document_index",
        ),
        {"schema": "spendwise"},
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("spendwise.documents.id"),
        nullable=False,
    )

    source_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    merchant: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    direction: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    transaction_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    review_reasons: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )

    approved_transaction_id: Mapped[int | None] = (
        mapped_column(Integer, nullable=True)
    )

    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
