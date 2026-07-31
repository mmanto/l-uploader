import re
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

HOSTNAME_RE = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)
SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def is_valid_hostname(value: str) -> bool:
    return bool(HOSTNAME_RE.match(value)) and len(value) <= 253


def is_valid_slug(value: str) -> bool:
    return bool(SLUG_RE.match(value))


class RootDomain(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hostname: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Page(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    content_updated_at: Optional[datetime] = None


class Domain(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    page_id: int = Field(foreign_key="page.id", index=True)
    hostname: str = Field(unique=True, index=True)
    kind: str  # "subdomain" | "custom"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HostingerDomain(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hostname: str = Field(unique=True, index=True)
    expires_at: Optional[str] = None
    subscription_id: Optional[str] = None
    subdomains: Optional[str] = None
    server: Optional[str] = None
    dns_info: Optional[str] = None
    environment: Optional[str] = None
    responsible: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HostingerVps(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    vps_id: str = Field(unique=True, index=True)
    plan: Optional[str] = None
    expires_at: Optional[str] = None
    subscription_id: Optional[str] = None
    ip: Optional[str] = None
    domains_hosted: Optional[str] = None
    services: Optional[str] = None
    environment: Optional[str] = None
    responsible: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
