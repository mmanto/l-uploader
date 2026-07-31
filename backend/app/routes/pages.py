from fastapi import APIRouter, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlmodel import select

from ..auth import is_authenticated
from ..caddy_sync import CaddySyncError, resync
from ..db import get_session
from ..models import Domain, Page, RootDomain, is_valid_slug
from ..templating import templates
from ..zip_utils import InvalidZipError, delete_page_dir, extract_zip_to_page
from datetime import datetime

router = APIRouter()


@router.get("/")
async def dashboard(request: Request, ok: str = "", err: str = ""):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        pages = list(session.exec(select(Page).order_by(Page.created_at.desc())))
        result = []
        for p in pages:
            domains = list(session.exec(select(Domain).where(Domain.page_id == p.id)))
            result.append({**p.model_dump(), "domains": domains})

    return templates.TemplateResponse(
        request, "dashboard.html", {"pages": result, "ok": ok, "err": err}
    )


@router.post("/pages")
async def create_page(request: Request, name: str = Form(...), slug: str = Form(...)):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    if not is_valid_slug(slug):
        return RedirectResponse("/?err=Slug+inv%C3%A1lido", status_code=302)

    with get_session() as session:
        existing = session.exec(select(Page).where(Page.slug == slug)).first()
        if existing:
            return RedirectResponse("/?err=Ya+existe+una+p%C3%A1gina+con+ese+slug", status_code=302)

        page = Page(name=name, slug=slug)
        session.add(page)
        session.commit()

    return RedirectResponse("/?ok=P%C3%A1gina+creada", status_code=302)


@router.get("/pages/{page_id}")
async def page_detail(request: Request, page_id: int, ok: str = "", err: str = ""):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        page = session.get(Page, page_id)
        if not page:
            return RedirectResponse("/?err=P%C3%A1gina+no+encontrada", status_code=302)
        domains = list(session.exec(select(Domain).where(Domain.page_id == page_id)))
        root_domains = list(session.exec(select(RootDomain)))

    return templates.TemplateResponse(
        request,
        "page_detail.html",
        {"page": page, "domains": domains, "root_domains": root_domains, "ok": ok, "err": err},
    )


@router.post("/pages/{page_id}/upload")
async def upload_content(request: Request, page_id: int, file: UploadFile = File(...)):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    if not file.filename or not file.filename.endswith(".zip"):
        return RedirectResponse(
            f"/pages/{page_id}?err=Solo+se+aceptan+archivos+.zip", status_code=302
        )

    with get_session() as session:
        page = session.get(Page, page_id)
        if not page:
            return RedirectResponse("/?err=P%C3%A1gina+no+encontrada", status_code=302)

        try:
            file_count = extract_zip_to_page(page.slug, await file.read())
        except InvalidZipError as exc:
            return RedirectResponse(f"/pages/{page_id}?err={str(exc)}", status_code=302)

        page.content_updated_at = datetime.utcnow()
        session.add(page)
        session.commit()

    return RedirectResponse(
        f"/pages/{page_id}?ok=Publicado+correctamente+%28{file_count}+archivos%29", status_code=302
    )


@router.post("/pages/{page_id}/delete")
async def delete_page(request: Request, page_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        page = session.get(Page, page_id)
        if not page:
            return RedirectResponse("/?err=P%C3%A1gina+no+encontrada", status_code=302)

        domains = list(session.exec(select(Domain).where(Domain.page_id == page_id)))
        for d in domains:
            session.delete(d)
        session.delete(page)

        try:
            resync(session)
        except CaddySyncError as exc:
            session.rollback()
            return RedirectResponse(f"/pages/{page_id}?err={str(exc)}", status_code=302)

        session.commit()
        delete_page_dir(page.slug)

    return RedirectResponse("/?ok=P%C3%A1gina+borrada", status_code=302)
