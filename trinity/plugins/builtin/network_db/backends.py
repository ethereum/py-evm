import enum


class TrackingBackend(enum.Enum):
    sqlite3 = 'sqlite3'
    memory = 'memory'
    do_not_track = 'do-not-track'
