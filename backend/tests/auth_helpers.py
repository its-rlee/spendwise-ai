from app.auth import AuthUser, get_current_user
from app.main import app

TEST_USER_ID = "11111111-1111-1111-1111-111111111111"


def override_current_user(user_id: str = TEST_USER_ID) -> str:
    app.dependency_overrides[get_current_user] = (
        lambda: AuthUser(id=user_id)
    )
    return user_id
