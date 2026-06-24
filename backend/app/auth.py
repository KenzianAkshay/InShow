import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# MVP auth: hardcoded credentials, in-memory session store. A single backend
# instance makes this acceptable for now; multi-user comes with the users table.
USERNAME = "user"
PASSWORD = "password"
COOKIE_NAME = "session"
SESSIONS: dict[str, str] = {}

router = APIRouter(prefix="/api")


class Credentials(BaseModel):
    username: str
    password: str


def current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    return SESSIONS.get(token) if token else None


def require_user(request: Request) -> str:
    username = current_user(request)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


@router.post("/login")
def login(creds: Credentials, response: Response):
    if creds.username != USERNAME or creds.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = creds.username
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", path="/"
    )
    return {"username": creds.username}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        SESSIONS.pop(token, None)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    username = current_user(request)
    if not username:
        # Clear a stale/invalid cookie so the client doesn't loop between
        # "/" and "/login" (the middleware only checks cookie presence).
        response = JSONResponse({"detail": "Not authenticated"}, status_code=401)
        response.delete_cookie(COOKIE_NAME, path="/")
        return response
    return {"username": username}
