
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .database import get_db


router = APIRouter(tags=["health"])


@router.get(
    "/ready",
    include_in_schema=False,
)
def readiness(
    db: Session = Depends(get_db),
):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return {"status": "ready"}
