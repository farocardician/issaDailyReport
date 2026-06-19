from app.domain.store_matching import StoreLocation
from app.templates import MessageTemplates


def _templates() -> MessageTemplates:
    return MessageTemplates(
        {
            "STORE_LABEL_FORMAT": "{{brand}} – {{outlet}} {{branch}}, {{city}}",
            "STORE_BUTTON_LABEL_WITH_DISTANCE": "{{store_label}} ({{distance_meter}})",
            "AREA_LABEL_FORMAT": "{{outlet}} {{branch}}, {{city}}",
            "DISTANCE_METER_FORMAT": "{{distance}} m",
            "DISTANCE_EMPTY": "-",
            "LOCATION_STATUS_IN_RADIUS": "Dalam radius",
            "LOCATION_STATUS_OUT_OF_RADIUS": "Di luar radius",
            "LOCATION_STATUS_MANUAL_STORE_SELECTION": "Pilih toko manual",
            "MESSAGE_WITH_STORE": "<b>{{store_label}}</b>",
        }
    )


def _store() -> StoreLocation:
    return StoreLocation(
        store_id="S001",
        outlet="Mall & Co",
        branch="Utama",
        city="Jakarta",
        brand="VIZU",
        latitude=-6.2,
        longitude=106.8,
        allowed_radius_meter=100,
        status="Aktif",
        notes=None,
    )


def test_template_backed_store_and_distance_labels() -> None:
    templates = _templates()
    store = _store()

    assert templates.render_store_label(store) == "VIZU – Mall & Co Utama, Jakarta"
    assert templates.render_distance_meter(1234.4) == "1.234 m"
    assert templates.render_store_button_label(store, 1234.4) == "VIZU – Mall & Co Utama, Jakarta (1.234 m)"


def test_message_render_escapes_plain_store_label_once() -> None:
    templates = _templates()
    store_label = templates.render_store_label(_store())

    assert templates.render("MESSAGE_WITH_STORE", store_label=store_label) == "<b>VIZU – Mall &amp; Co Utama, Jakarta</b>"


def test_trusted_render_preserves_selected_html_token() -> None:
    templates = MessageTemplates({"MESSAGE": "{{safe}}\n{{unsafe}}"})

    assert templates.render_trusted(
        "MESSAGE",
        {"safe"},
        safe="<b>Outlet</b>",
        unsafe="<b>Bad</b>",
    ) == "<b>Outlet</b>\n&lt;b&gt;Bad&lt;/b&gt;"


def test_template_backed_location_status_labels() -> None:
    templates = _templates()

    assert templates.render_location_status("in_radius") == "Dalam radius"
    assert templates.render_location_status("out_of_radius") == "Di luar radius"
    assert templates.render_location_status("manual_store_selection") == "Pilih toko manual"
