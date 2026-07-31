import logging

from fastapi import FastAPI

from .caddy_sync import CaddySyncError, resync
from .db import get_session, init_db
from .routes import auth_routes, domains, pages, root_domains

logger = logging.getLogger("luploader")

app = FastAPI(docs_url=None, redoc_url=None)

app.include_router(auth_routes.router)
app.include_router(pages.router)
app.include_router(domains.router)
app.include_router(root_domains.router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    try:
        with get_session() as session:
            resync(session)
    except CaddySyncError as exc:
        logger.warning("No se pudo re-sincronizar Caddy al arrancar: %s", exc)
