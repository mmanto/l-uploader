import logging

from fastapi import FastAPI
from sqlmodel import select

from .caddy_sync import CaddySyncError, resync
from .db import get_session, init_db
from .models import HostingerDomain, HostingerVps
from .routes import auth_routes, domains, pages, proposals, resources, root_domains

logger = logging.getLogger("luploader")

app = FastAPI(docs_url=None, redoc_url=None)

app.include_router(auth_routes.router)
app.include_router(pages.router)
app.include_router(domains.router)
app.include_router(root_domains.router)
app.include_router(resources.router)
app.include_router(proposals.router)


def seed_resources_if_empty(session) -> None:
    if session.exec(select(HostingerDomain)).first() or session.exec(select(HostingerVps)).first():
        return

    for hostname, expires_at, subscription_id in [
        ("cooperadoracnlp.online", "2027-06-18", "AzqRV3VMqudbX3WbM"),
        ("intellify.pro", "2027-04-30", "6oqGSVIHhksP25tS"),
        ("kaizenstudio.online", "2027-04-15", "16CMzGVGtG8J32jGi"),
    ]:
        session.add(HostingerDomain(hostname=hostname, expires_at=expires_at, subscription_id=subscription_id))

    for vps_id, plan, expires_at, subscription_id in [
        ("1507469", "KVM 2", "2026-08-18", "AzqHJyVEFxsH11ea1"),
        ("1575462", "KVM 4", "2026-08-10", "AzykLOVGNYxPE2E71"),
        ("1655560", "KVM 2", "2026-08-08", "169ozjVJ3lo9D36He"),
    ]:
        session.add(HostingerVps(vps_id=vps_id, plan=plan, expires_at=expires_at, subscription_id=subscription_id))

    session.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with get_session() as session:
        seed_resources_if_empty(session)
    try:
        with get_session() as session:
            resync(session)
    except CaddySyncError as exc:
        logger.warning("No se pudo re-sincronizar Caddy al arrancar: %s", exc)
