from html import escape
from typing import Any, Mapping

from app.domain.store_matching import StoreLocation


class MessageTemplates:
    def __init__(self, templates: Mapping[str, str]) -> None:
        self._templates = dict(templates)

    def update(self, templates: Mapping[str, str]) -> None:
        self._templates = dict(templates)

    def render(self, key: str, **tokens: Any) -> str:
        return self._render(key, tokens, escape_tokens=True)

    def render_plain(self, key: str, **tokens: Any) -> str:
        return self._render(key, tokens, escape_tokens=False)

    def render_store_label(self, store: StoreLocation | Mapping[str, Any]) -> str:
        return self.render_plain(
            "STORE_LABEL_FORMAT",
            brand=_get(store, "brand"),
            department_store=_get(store, "department_store"),
            branch=_get(store, "branch"),
            city=_get(store, "city"),
        )

    def render_area_label(self, store: StoreLocation | Mapping[str, Any]) -> str:
        return self.render_plain(
            "AREA_LABEL_FORMAT",
            department_store=_get(store, "department_store"),
            branch=_get(store, "branch"),
            city=_get(store, "city"),
        )

    def render_distance_meter(self, distance: float | None) -> str:
        if distance is None:
            return self.render_plain("DISTANCE_EMPTY")
        return self.render_plain("DISTANCE_METER_FORMAT", distance=_format_integer_id(distance))

    def render_store_button_label(self, store: StoreLocation | Mapping[str, Any], distance: float) -> str:
        return self.render_plain(
            "STORE_BUTTON_LABEL_WITH_DISTANCE",
            store_label=self.render_store_label(store),
            distance_meter=self.render_distance_meter(distance),
        )

    def render_location_status(self, status: str) -> str:
        return self.render_plain(f"LOCATION_STATUS_{status.upper()}")

    def _render(self, key: str, tokens: Mapping[str, Any], escape_tokens: bool) -> str:
        message = self._templates[key]
        safe_tokens = {
            name: escape(str(value), quote=False) if escape_tokens else str(value)
            for name, value in tokens.items()
        }
        for name, value in safe_tokens.items():
            message = message.replace(f"{{{{{name}}}}}", value)
        return message


def _format_integer_id(value: float) -> str:
    return f"{round(value):,}".replace(",", ".")


def _get(store: StoreLocation | Mapping[str, Any], key: str) -> Any:
    if isinstance(store, Mapping):
        return store[key]
    return getattr(store, key)
