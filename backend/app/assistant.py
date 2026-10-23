
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
from .finance_planner import GeminiFinancePlanner, FinancePlannerError
from .finance_query_engine import run_finance_query, describe_results
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
    # Gemini produces bounded allowlisted query specs, never SQL.
    # Legacy planners are retained for backwards-compatible local tests.
    if isinstance(planner, GeminiFinancePlanner):
        try:
            flexible_plan = planner.plan(
                request.question,
                history=request.history,
                today=today,
            )
        except FinancePlannerError as exc:
            raise HTTPException(
                status_code=503,
                detail="AI couldn't interpret this question right now. "
                       "Your data is safe; please retry or rephrase.",
            ) from exc

        if not flexible_plan.queries:
            return AssistantAnswer(
                question=request.question,
                intent="unavailable_data",
                period="custom",
                answer=(
                    "I can't reliably answer that from the approved "
                    "transactions and receipt items saved in SpendWise. "
                    "Try asking about a product, merchant, amount, or date."
                ),
                facts={"queries": []},
            )

        try:
            results = [
                run_finance_query(db, user.id, query)
                for query in flexible_plan.queries
            ]
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=503,
                detail="Financial records are temporarily unavailable",
            ) from exc

        return AssistantAnswer(
            question=request.question,
            intent="dynamic_finance_query",
            period="custom",
            answer=describe_results(results),
            facts={
                "queries": results,
                "disclaimer": (
                    "Only approved saved transactions and receipt item "
                    "lines are used; item-line prices may not equal "
                    "receipt totals."
                ),
            },
        )

    # Legacy structured intent planner for local Ollama.
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
