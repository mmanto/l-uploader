from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..auth import is_authenticated
from ..db import get_session
from ..models import Domain, RootDomain, is_valid_hostname
from ..templating import templates

router = APIRouter()


@router.get("/root-domains")
async def list_root_domains(request: Request, ok: str = "", err: str = ""):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        root_domains = list(session.exec(select(RootDomain).order_by(RootDomain.hostname)))

    return templates.TemplateResponse(
        request, "root_domains.html", {"root_domains": root_domains, "ok": ok, "err": err}
    )


@router.post("/root-domains")
async def add_root_domain(request: Request, hostname: str = Form(...)):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    hostname = hostname.strip().lower()
    if not is_valid_hostname(hostname):
        return RedirectResponse("/root-domains?err=Hostname+inv%C3%A1lido", status_code=302)

    with get_session() as session:
        session.add(RootDomain(hostname=hostname))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return RedirectResponse("/root-domains?err=Ese+dominio+ra%C3%ADz+ya+existe", status_code=302)

    return RedirectResponse("/root-domains?ok=Dominio+ra%C3%ADz+agregado", status_code=302)


@router.post("/root-domains/{root_domain_id}/delete")
async def delete_root_domain(request: Request, root_domain_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        root = session.get(RootDomain, root_domain_id)
        if not root:
            return RedirectResponse("/root-domains?err=Dominio+ra%C3%ADz+no+encontrado", status_code=302)

        suffix = f".{root.hostname}"
        in_use = session.exec(select(Domain).where(Domain.hostname.like(f"%{suffix}"))).first()
        if in_use:
            return RedirectResponse(
                "/root-domains?err=No+se+puede+borrar%3A+hay+p%C3%A1ginas+usando+subdominios+de+este+dominio",
                status_code=302,
            )

        session.delete(root)
        session.commit()

    return RedirectResponse("/root-domains?ok=Dominio+ra%C3%ADz+eliminado", status_code=302)
