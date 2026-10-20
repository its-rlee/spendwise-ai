import os

from fastapi import HTTPException


def require_cloud_llm():
    if (
        os.getenv("APP_ENV") == "production"
        and os.getenv(
            "CLOUD_LLM_ENABLED", "false"
        ).lower() != "true"
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "AI processing is not enabled "
                "in this deployment"
            ),
        )
