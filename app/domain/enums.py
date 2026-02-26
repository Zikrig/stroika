from enum import Enum


class Role(str, Enum):
    FOREMAN = "foreman"
    PDO = "pdo"
    PROCUREMENT = "procurement"
    MANAGER = "manager"
    VIEWER = "viewer"


class StatusCode(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    FORWARDED = "forwarded"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    TERMINATED = "terminated"


class StageCode(str, Enum):
    CREATED = "created"
    PDO_PROCESSING = "pdo_processing"
    TRANSFERRED_TO_PROCUREMENT = "transferred_to_procurement"
    PROCUREMENT_IN_WORK = "procurement_in_work"
    PURCHASED = "purchased"
    SHIPPED = "shipped"
    PARTIALLY_RECEIVED = "partially_received"
    FULLY_RECEIVED = "fully_received"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    TERMINATED = "terminated"


class EventType(str, Enum):
    REQUEST_CREATED = "request_created"
    PDO_TAKEN = "pdo_taken"
    PDO_FORMALIZED = "pdo_formalized"
    PROCUREMENT_TAKEN = "procurement_taken"
    RETURNED_TO_PDO = "returned_to_pdo"
    PURCHASED = "purchased"
    SHIPPED = "shipped"
    PARTIALLY_RECEIVED = "partially_received"
    FULLY_RECEIVED = "fully_received"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RESUMED = "resumed"
    MANAGER_COMMENTED = "manager_commented"
    TERMINATED = "terminated"
