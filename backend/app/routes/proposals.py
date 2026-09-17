from datetime import datetime
from urllib.parse import quote_plus

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..auth import is_authenticated
from ..caddy_sync import ADMIN_DOMAIN, CaddySyncError, resync
from ..db import get_session
from ..models import Domain, Proposal, is_valid_hostname, new_proposal_token
from ..templating import templates
from ..zip_utils import (
    InvalidZipError,
    delete_proposal_dir,
    publish_proposal_html,
    publish_proposal_zip,
)

router = APIRouter()

# Prefijo público donde Caddy publica las propuestas (ver caddy_templates/caddyfile.j2).
PROPOSAL_PATH_PREFIX = "/propuestas"


def proposal_url(hostname: str, token: str) -> str:
    return f"https://{hostname}{PROPOSAL_PATH_PREFIX}/{token}"


def _redirect(message: str) -> RedirectResponse:
    return RedirectResponse(f"/propuestas?err={quote_plus(message)}", status_code=302)


def _unique_token(session: Session) -> str:
    while True:
        token = new_proposal_token()
        if not session.exec(select(Proposal).where(Proposal.token == token)).first():
            return token


@router.get("/propuestas")
async def list_proposals(request: Request, ok: str = "", err: str = ""):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        proposals = list(session.exec(select(Proposal).order_by(Proposal.created_at.desc())))
        hostnames = list(session.exec(select(Domain.hostname).order_by(Domain.hostname)))

    rows = [{**p.model_dump(), "url": proposal_url(p.hostname, p.token)} for p in proposals]

    return templates.TemplateResponse(
        request,
        "proposals.html",
        {"proposals": rows, "hostnames": hostnames, "ok": ok, "err": err},
    )


@router.post("/propuestas")
async def create_proposal(
    request: Request,
    client: str = Form(...),
    hostname: str = Form(...),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    client = client.strip()
    if not client:
        return _redirect("El nombre del cliente es obligatorio")

    hostname = hostname.strip().lower()
    if not is_valid_hostname(hostname):
        return _redirect("Hostname inválido")

    with get_session() as session:
        if hostname == ADMIN_DOMAIN:
            return _redirect("Ese es el dominio del panel: las propuestas no se sirven ahí")

        token = _unique_token(session)
        session.add(Proposal(client=client, token=token, hostname=hostname))

        try:
            session.flush()
            resync(session)
        except IntegrityError:
            session.rollback()
            return _redirect("No se pudo crear la propuesta")
        except CaddySyncError as exc:
            session.rollback()
            return _redirect(str(exc))

        session.commit()

    return RedirectResponse("/propuestas?ok=Propuesta+creada", status_code=302)


@router.post("/propuestas/{proposal_id}/upload")
async def upload_proposal(request: Request, proposal_id: int, file: UploadFile = File(...)):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    filename = (file.filename or "").lower()
    if filename.endswith(".zip"):
        publish = publish_proposal_zip
    elif filename.endswith((".html", ".htm")):
        publish = publish_proposal_html
    else:
        return _redirect("Subí un .zip con el sitio o un único archivo .html")

    with get_session() as session:
        proposal = session.get(Proposal, proposal_id)
        if not proposal:
            return _redirect("Propuesta no encontrada")

        try:
            file_count = publish(proposal.token, await file.read())
        except InvalidZipError as exc:
            return _redirect(str(exc))

        proposal.content_updated_at = datetime.utcnow()
        session.add(proposal)
        session.commit()

    return RedirectResponse(f"/propuestas?ok=Publicado+%28{file_count}+archivos%29", status_code=302)


@router.post("/propuestas/{proposal_id}/delete")
async def delete_proposal(request: Request, proposal_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        proposal = session.get(Proposal, proposal_id)
        if not proposal:
            return _redirect("Propuesta no encontrada")

        token = proposal.token
        session.delete(proposal)

        try:
            resync(session)
        except CaddySyncError as exc:
            session.rollback()
            return _redirect(str(exc))

        session.commit()

    delete_proposal_dir(token)

    return RedirectResponse("/propuestas?ok=Propuesta+borrada", status_code=302)
