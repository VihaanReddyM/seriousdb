from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query

from .cache import Cache, JsonValue, require_db
from .config import DB_FILE
from .error_handlers import register_exception_handlers
from .parser import parse_value

cache = Cache()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    cache.load(DB_FILE)
    yield


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)


def get_cache() -> Cache:
    return cache


@app.put("/db", response_model=None)
def put(
    key: Annotated[str, Query(min_length=1)],
    value: str,
    background_tasks: BackgroundTasks,
    cache: Annotated[Cache, Depends(get_cache)],
) -> JsonValue:
    parsed_value = parse_value(value)
    cache.insert(key, parsed_value)
    background_tasks.add_task(cache.flush)
    return parsed_value


@app.get("/db", response_model=None)
def get(key: str, cache: Annotated[Cache, Depends(get_cache)]) -> JsonValue:
    return cache.select(key)


@app.head("/db", response_model=None)
async def head(key: str, cache: Annotated[Cache, Depends(get_cache)]) -> JsonValue:
    return cache.select(key)


@app.get("/db/all", response_model=None)
def get_all(cache: Annotated[Cache, Depends(get_cache)]) -> dict[str, JsonValue]:
    with cache.lock:
        return require_db(cache).copy()


@app.delete("/db", response_model=None)
def delete(
    key: str,
    background_tasks: BackgroundTasks,
    cache: Annotated[Cache, Depends(get_cache)],
):
    value = cache.delete(key)
    background_tasks.add_task(cache.flush)
    return value


@app.get("/health")
def health(cache: Annotated[Cache, Depends(get_cache)]):
    if cache.db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    return {"status": "ok"}
