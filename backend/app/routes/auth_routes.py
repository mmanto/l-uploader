from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from ..auth import COOKIE_MAX_AGE, COOKIE_NAME, check_credentials, is_authenticated, sign
from ..templating import templates

router = APIRouter()


@router.get("/login")
async def login_get(request: Request, error: str = ""):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.post("/login")
async def login_post(username: str = Form(...), password: str = Form(...)):
    if check_credentials(username, password):
        token = sign(username)
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/login?error=Credenciales+incorrectas", status_code=302)


@router.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME)
    return resp
