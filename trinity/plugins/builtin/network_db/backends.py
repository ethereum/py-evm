import enum


class TrackingBackend(enum.Enum):
    sqlite3 = 'sqlite3'
    memory = 'memory'
    disabled = 'disabled'
