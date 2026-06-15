from html import escape
from typing import Any, Mapping

from app.domain.store_matching import StoreLocation


class MessageTemplates:
    def __init__(self, templates: Mapping[str, str]) -> None:
        self._templates = dict(templates)

    def update(self, templates: Mapping[str, str]) -> None:
        self._templates = dict(templates)

    def render(self, key: str, **tokens: Any) -> str:
        message = self._templates[key]
        safe_tokens = {name: escape(str(value), quote=False) for name, value in tokens.items()}
        for name, value in safe_tokens.items():
            message = message.replace(f"{{{{{name}}}}}", value)
        return message


def store_label(store: StoreLocation | Mapping[str, Any]) -> str:
    brand = _get(store, "brand")
    department_store = _get(store, "department_store")
    branch = _get(store, "branch")
    city = _get(store, "city")
    return f"{brand} \u2013 {department_store} {branch}, {city}"


def distance_meter(distance: float) -> str:
    return f"{round(distance):,}".replace(",", ".") + " m"


def _get(store: StoreLocation | Mapping[str, Any], key: str) -> Any:
    if isinstance(store, Mapping):
        return store[key]
    return getattr(store, key)
