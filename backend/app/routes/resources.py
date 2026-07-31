from datetime import date, datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from ..auth import is_authenticated
from ..db import get_session
from ..models import HostingerDomain, HostingerVps, is_valid_hostname
from ..templating import templates

router = APIRouter()

EXPIRY_WARN_DAYS = 60


def _clean(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _with_expiry(items: list, today: date) -> tuple[list, int]:
    rows = []
    soon = 0
    for item in items:
        expiry = _parse_date(item.expires_at)
        warn = expiry is not None and (expiry - today).days <= EXPIRY_WARN_DAYS
        if warn:
            soon += 1
        rows.append({"item": item, "expires_warn": warn})
    return rows, soon


@router.get("/resources")
async def list_resources(
    request: Request,
    ok: str = "",
    err: str = "",
    edit_domain: int = 0,
    edit_vps: int = 0,
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    today = date.today()
    with get_session() as session:
        domains = list(session.exec(select(HostingerDomain).order_by(HostingerDomain.hostname)))
        vpss = list(session.exec(select(HostingerVps).order_by(HostingerVps.vps_id)))
        domain_to_edit = session.get(HostingerDomain, edit_domain) if edit_domain else None
        vps_to_edit = session.get(HostingerVps, edit_vps) if edit_vps else None

    domain_rows, domains_soon = _with_expiry(domains, today)
    vps_rows, vps_soon = _with_expiry(vpss, today)

    return templates.TemplateResponse(
        request,
        "resources.html",
        {
            "domain_rows": domain_rows,
            "vps_rows": vps_rows,
            "expiring_soon": domains_soon + vps_soon,
            "domain_to_edit": domain_to_edit,
            "vps_to_edit": vps_to_edit,
            "ok": ok,
            "err": err,
        },
    )


@router.post("/resources/domains")
async def create_resource_domain(
    request: Request,
    hostname: str = Form(...),
    expires_at: str = Form(""),
    subscription_id: str = Form(""),
    subdomains: str = Form(""),
    server: str = Form(""),
    dns_info: str = Form(""),
    environment: str = Form(""),
    responsible: str = Form(""),
    notes: str = Form(""),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    hostname = hostname.strip().lower()
    if not is_valid_hostname(hostname):
        return RedirectResponse("/resources?err=Hostname+inv%C3%A1lido", status_code=302)

    with get_session() as session:
        session.add(
            HostingerDomain(
                hostname=hostname,
                expires_at=_clean(expires_at),
                subscription_id=_clean(subscription_id),
                subdomains=_clean(subdomains),
                server=_clean(server),
                dns_info=_clean(dns_info),
                environment=_clean(environment),
                responsible=_clean(responsible),
                notes=_clean(notes),
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return RedirectResponse("/resources?err=Ese+dominio+ya+est%C3%A1+cargado", status_code=302)

    return RedirectResponse("/resources?ok=Dominio+agregado", status_code=302)


@router.post("/resources/domains/{resource_id}")
async def update_resource_domain(
    request: Request,
    resource_id: int,
    hostname: str = Form(...),
    expires_at: str = Form(""),
    subscription_id: str = Form(""),
    subdomains: str = Form(""),
    server: str = Form(""),
    dns_info: str = Form(""),
    environment: str = Form(""),
    responsible: str = Form(""),
    notes: str = Form(""),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    hostname = hostname.strip().lower()
    if not is_valid_hostname(hostname):
        return RedirectResponse(f"/resources?edit_domain={resource_id}&err=Hostname+inv%C3%A1lido", status_code=302)

    with get_session() as session:
        resource = session.get(HostingerDomain, resource_id)
        if not resource:
            return RedirectResponse("/resources?err=Dominio+no+encontrado", status_code=302)

        resource.hostname = hostname
        resource.expires_at = _clean(expires_at)
        resource.subscription_id = _clean(subscription_id)
        resource.subdomains = _clean(subdomains)
        resource.server = _clean(server)
        resource.dns_info = _clean(dns_info)
        resource.environment = _clean(environment)
        resource.responsible = _clean(responsible)
        resource.notes = _clean(notes)
        session.add(resource)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                f"/resources?edit_domain={resource_id}&err=Ese+dominio+ya+est%C3%A1+cargado", status_code=302
            )

    return RedirectResponse("/resources?ok=Dominio+actualizado", status_code=302)


@router.post("/resources/domains/{resource_id}/delete")
async def delete_resource_domain(request: Request, resource_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        resource = session.get(HostingerDomain, resource_id)
        if not resource:
            return RedirectResponse("/resources?err=Dominio+no+encontrado", status_code=302)
        session.delete(resource)
        session.commit()

    return RedirectResponse("/resources?ok=Dominio+eliminado", status_code=302)


@router.post("/resources/vps")
async def create_resource_vps(
    request: Request,
    vps_id: str = Form(...),
    plan: str = Form(""),
    expires_at: str = Form(""),
    subscription_id: str = Form(""),
    ip: str = Form(""),
    domains_hosted: str = Form(""),
    services: str = Form(""),
    environment: str = Form(""),
    responsible: str = Form(""),
    notes: str = Form(""),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    vps_id = vps_id.strip()
    if not vps_id:
        return RedirectResponse("/resources?err=ID+de+VPS+requerido", status_code=302)

    with get_session() as session:
        session.add(
            HostingerVps(
                vps_id=vps_id,
                plan=_clean(plan),
                expires_at=_clean(expires_at),
                subscription_id=_clean(subscription_id),
                ip=_clean(ip),
                domains_hosted=_clean(domains_hosted),
                services=_clean(services),
                environment=_clean(environment),
                responsible=_clean(responsible),
                notes=_clean(notes),
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return RedirectResponse("/resources?err=Ese+VPS+ya+est%C3%A1+cargado", status_code=302)

    return RedirectResponse("/resources?ok=VPS+agregado", status_code=302)


@router.post("/resources/vps/{resource_id}")
async def update_resource_vps(
    request: Request,
    resource_id: int,
    vps_id: str = Form(...),
    plan: str = Form(""),
    expires_at: str = Form(""),
    subscription_id: str = Form(""),
    ip: str = Form(""),
    domains_hosted: str = Form(""),
    services: str = Form(""),
    environment: str = Form(""),
    responsible: str = Form(""),
    notes: str = Form(""),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    vps_id = vps_id.strip()
    if not vps_id:
        return RedirectResponse(f"/resources?edit_vps={resource_id}&err=ID+de+VPS+requerido", status_code=302)

    with get_session() as session:
        resource = session.get(HostingerVps, resource_id)
        if not resource:
            return RedirectResponse("/resources?err=VPS+no+encontrado", status_code=302)

        resource.vps_id = vps_id
        resource.plan = _clean(plan)
        resource.expires_at = _clean(expires_at)
        resource.subscription_id = _clean(subscription_id)
        resource.ip = _clean(ip)
        resource.domains_hosted = _clean(domains_hosted)
        resource.services = _clean(services)
        resource.environment = _clean(environment)
        resource.responsible = _clean(responsible)
        resource.notes = _clean(notes)
        session.add(resource)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return RedirectResponse(
                f"/resources?edit_vps={resource_id}&err=Ese+VPS+ya+est%C3%A1+cargado", status_code=302
            )

    return RedirectResponse("/resources?ok=VPS+actualizado", status_code=302)


@router.post("/resources/vps/{resource_id}/delete")
async def delete_resource_vps(request: Request, resource_id: int):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

    with get_session() as session:
        resource = session.get(HostingerVps, resource_id)
        if not resource:
            return RedirectResponse("/resources?err=VPS+no+encontrado", status_code=302)
        session.delete(resource)
        session.commit()

    return RedirectResponse("/resources?ok=VPS+eliminado", status_code=302)
