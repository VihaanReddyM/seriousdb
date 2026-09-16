import json
import logging
import os
import time
from threading import Lock
from typing import TypeAlias

from .exceptions import ResourceNotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_DB = {"default": "default"}

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class Cache:
    def __init__(self):
        self.filename: str | None = None
        self.db: dict[str, JsonValue] | None = None
        self.lock = Lock()

    def insert(self, key: str, value: JsonValue):
        with self.lock:
            require_db(self)[key] = value
        return value

    def select(self, key: str) -> JsonValue:
        with self.lock:
            db = require_db(self)
            
            if key not in db:
                raise ResourceNotFoundError(f"No value set for key {key}")

        return db[key]

    def delete(self, key: str) -> JsonValue:
        with self.lock:
            db = require_db(self)

            if key not in db:
                raise ResourceNotFoundError(f"No value set for key {key}")

            return db.pop(key)

    def load(self, filename: str) -> None:
        with self.lock:
            if not os.path.isfile(filename):
                self.db = _write_default(filename)
            else:
                try:
                    with open(filename, "rb") as f:
                        self.db = json.loads(f.read().decode())
                        if not isinstance(self.db, dict):
                            raise TypeError(
                                f"expected dict, got {type(self.db).__name__}"
                            )
                except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as e:
                    backup = f"{filename}.corrupt-{int(time.time())}"
                    os.replace(filename, backup)
                    logger.warning(
                        "Corrupt database file %s (%s); moved to %s and starting fresh",
                        filename,
                        e,
                        backup,
                    )
                    self.db = _write_default(filename)
            self.filename = filename

    def flush(self) -> None:
        with self.lock:
            if self.db is None or self.filename is None:
                return
            with open(self.filename, "wb+") as f:
                f.write(json.dumps(self.db).encode())


def _write_default(filename: str) -> dict[str, JsonValue]:
    with open(filename, "wb") as f:
        f.write(json.dumps(DEFAULT_DB).encode())
    return dict(DEFAULT_DB)


def require_db(cache: Cache) -> dict[str, JsonValue]:
    """Return the loaded database or fail with an expected application error."""
    if cache.db is None:
        raise ServiceUnavailableError(
            f"Database file {cache.filename} could not be opened and loaded"
        )

    return cache.db
