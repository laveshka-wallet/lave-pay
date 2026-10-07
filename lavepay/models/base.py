from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PrivateAttr

T = TypeVar("T")


class APIModel(BaseModel):

    model_config = ConfigDict(extra="ignore")
    _client: Any = PrivateAttr(default=None)

    def bind(self, client: Any) -> APIModel:
        self._client = client
        return self

    def _require(self) -> Any:
        if self._client is None:
            raise RuntimeError("объект не привязан к клиенту Lave Pay")
        return self._client

    def poll(self, **data: Any) -> None:
        self._require().watch(self, **data)


class Page(Generic[T]):

    def __init__(self, items: list[T], next_cursor: int | None = None) -> None:
        self.items = items
        self.next_cursor = next_cursor

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)
