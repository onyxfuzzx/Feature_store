from app.schemas.common import ORMBase
from app.schemas.users import UserOut


class LoginRequest(ORMBase):
    email: str
    password: str


class TokenOut(ORMBase):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
