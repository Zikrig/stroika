from dataclasses import dataclass

from app.infrastructure.repositories.outbox_repository import OutboxRepository
from app.infrastructure.repositories.request_repository import RequestRepository
from app.infrastructure.repositories.role_repository import RoleRepository


@dataclass(slots=True)
class AppContext:
    requests: RequestRepository
    roles: RoleRepository
    outbox: OutboxRepository
