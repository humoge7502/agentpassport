"""Database session management.

All DB access flows through the service registry's Database instance so API
handlers, services, and jobs share one engine (and tests can swap it).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import install_append_only_guards, make_engine


class Database:
    def __init__(self, database_url: str | None = None):
        settings = get_settings()
        self.engine = make_engine(database_url or settings.database_url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        from app.models import Base
        Base.metadata.create_all(self.engine)
        install_append_only_guards(self.engine)

    def session(self) -> Session:
        return self.session_factory()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: session from the active service registry."""
    from app.services import get_services
    services = get_services()
    db = services.db.session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
