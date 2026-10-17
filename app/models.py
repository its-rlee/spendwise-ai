
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String
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
