
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "spendwise"}

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
