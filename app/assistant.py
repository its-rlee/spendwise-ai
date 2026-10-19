
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .auth import AuthUser, get_current_user
from .database import get_db

from .assistant_schemas import (
    AssistantQuestion,
    AssistantAnswer,
)
from .assistant_planner import (
    PlannerError,
    get_query_planner,
)
from .finance_analytics import (
    calculate_report,
    get_utc_today,
)


router = APIRouter(
    prefix="/api/v1/assistant",
    tags=["AI Financial Assistant"],
)


@router.post(
    "/ask",
    response_model=AssistantAnswer,
)
def ask_financial_assistant(
    request: AssistantQuestion,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
    planner=Depends(get_query_planner),
    today: date = Depends(get_utc_today),
):
    # Step 1: LLM converts question into
    # a limited, validated query plan.
    try:
        plan = planner.plan(request.question)

    except PlannerError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI question planner unavailable",
        ) from exc

    # Step 2: Reject requests outside our
    # supported capabilities.
    if plan.intent == "unsupported":
        raise HTTPException(
            status_code=422,
            detail=(
                "Question not supported yet. "
                "Try category spending, merchant "
                "spending, largest expenses, "
                "or cash flow."
            ),
        )

    # Step 3: Query ONLY this user's data.
    try:
        answer, facts = calculate_report(
            db=db,
            user_id=user.id,
            plan=plan,
            today=today,
        )

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="Financial report unavailable",
        ) from exc

    # Step 4: Respond using verified DB facts.
    return AssistantAnswer(
        question=request.question,
        intent=plan.intent,
        period=plan.period,
        answer=answer,
        facts=facts,
    )
