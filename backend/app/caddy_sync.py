import os

import httpx
from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from .models import Domain, Page

CADDY_ADMIN_URL = os.environ.get("CADDY_ADMIN_URL", "http://caddy:2019")
ADMIN_DOMAIN = os.environ.get("ADMIN_DOMAIN", "panel.local.test")
ACME_EMAIL = os.environ.get("ACME_EMAIL", "admin@example.com")
CADDY_TLS_MODE = os.environ.get("CADDY_TLS_MODE", "auto")  # "auto" | "internal"

_TEMPLATE_DIR = os.environ.get(
    "CADDY_TEMPLATE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "caddy_templates"),
)
_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)


class CaddySyncError(Exception):
    pass


def build_caddyfile(session: Session) -> str:
    pages = list(session.exec(select(Page)))
    pages_with_domains = []
    for page in pages:
        domains = list(session.exec(select(Domain).where(Domain.page_id == page.id)))
        if domains:
            pages_with_domains.append({"slug": page.slug, "domains": domains})

    tpl = _env.get_template("caddyfile.j2")
    return tpl.render(
        pages=pages_with_domains,
        admin_domain=ADMIN_DOMAIN,
        acme_email=ACME_EMAIL,
        tls_internal=(CADDY_TLS_MODE == "internal"),
    )


def push_config(caddyfile_text: str) -> None:
    try:
        resp = httpx.post(
            f"{CADDY_ADMIN_URL}/load",
            content=caddyfile_text.encode(),
            headers={"Content-Type": "text/caddyfile"},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        raise CaddySyncError(f"No se pudo contactar a Caddy: {exc}") from exc

    if resp.status_code >= 400:
        raise CaddySyncError(f"Caddy rechazó la config: {resp.text[:500]}")


def resync(session: Session) -> None:
    push_config(build_caddyfile(session))
