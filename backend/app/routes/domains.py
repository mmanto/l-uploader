import re

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..auth import is_authenticated
from ..caddy_sync import CaddySyncError, resync
from ..db import get_session
from ..models import Domain, Page, RootDomain, is_valid_hostname

router = APIRouter()

LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$")


@router.post("/pages/{page_id}/domains")
async def add_domain(
    request: Request,
    page_id: int,
    kind: str = Form(...),
    label: str = Form(""),
    root_domain_id: int = Form(None),
    hostname: str = Form(""),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        page = session.get(Page, page_id)
        if not page:
            return RedirectResponse("/?err=P%C3%A1gina+no+encontrada", status_code=302)

        if kind == "subdomain":
            if not LABEL_RE.match(label):
                return RedirectResponse(f"/pages/{page_id}?err=Subdominio+inv%C3%A1lido", status_code=302)
            root = session.get(RootDomain, root_domain_id)
            if not root:
                return RedirectResponse(f"/pages/{page_id}?err=Dominio+ra%C3%ADz+no+encontrado", status_code=302)
            full_hostname = f"{label}.{root.hostname}"
        elif kind == "custom":
            full_hostname = hostname.strip().lower()
        else:
            return RedirectResponse(f"/pages/{page_id}?err=Tipo+de+dominio+inv%C3%A1lido", status_code=302)

        if not is_valid_hostname(full_hostname):
            return RedirectResponse(f"/pages/{page_id}?err=Hostname+inv%C3%A1lido", status_code=302)

        domain = Domain(page_id=page_id, hostname=full_hostname, kind=kind)
        session.add(domain)

        try:
            session.flush()
            resync(session)
        except IntegrityError:
            session.rollback()
            return RedirectResponse(f"/pages/{page_id}?err=Ese+dominio+ya+est%C3%A1+en+uso", status_code=302)
        except CaddySyncError as exc:
            session.rollback()
            return RedirectResponse(f"/pages/{page_id}?err={str(exc)}", status_code=302)

        session.commit()

    return RedirectResponse(f"/pages/{page_id}?ok=Dominio+agregado", status_code=302)


@router.post("/domains/{domain_id}/delete")
async def delete_domain(request: Request, domain_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        domain = session.get(Domain, domain_id)
        if not domain:
            return RedirectResponse("/?err=Dominio+no+encontrado", status_code=302)
        page_id = domain.page_id
        session.delete(domain)

        try:
            resync(session)
        except CaddySyncError as exc:
            session.rollback()
            return RedirectResponse(f"/pages/{page_id}?err={str(exc)}", status_code=302)

        session.commit()

    return RedirectResponse(f"/pages/{page_id}?ok=Dominio+quitado", status_code=302)
