from html import escape
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode

from app.domain.store_matching import StoreLocation
from app.templates import distance_meter, store_label


async def send_admin_notification(
    bot: Bot,
    admin_chat_id: int,
    report: dict[str, Any],
    store: StoreLocation,
    user_name: str,
) -> None:
    if not admin_chat_id:
        return

    correction_banner = ""
    if report["submission_status"] == "correction":
        correction_banner = "<b>\u26a0\ufe0f KOREKSI</b>\n\n"

    message = (
        f"{correction_banner}"
        "<b>Laporan toko harian</b>\n\n"
        f"Toko: <b>{escape(store_label(store), quote=False)}</b>\n"
        f"SPG: {escape(user_name, quote=False)}\n"
        f"Tanggal: {report['report_date']}\n\n"
        f"Traffic: {report['traffic']}\n"
        f"GMV Offline: {report['offline_gmv']}\n"
        f"GMV Online: {report['online_gmv']}\n"
        f"Order: {report['order_count']}\n"
        f"Pieces: {report['pieces_sold']}\n\n"
        f"Alasan tidak beli:\n{escape(report['no_buy_reason'], quote=False)}\n\n"
        f"Kendala stok:\n{escape(report['stock_issue'], quote=False)}\n\n"
        f"Catatan:\n{escape(report['note'], quote=False)}\n\n"
        f"Jarak: {distance_meter(float(report['distance_from_store_meter']))}\n"
        f"Location Status: <b>{report['location_status']}</b>"
    )
    await bot.send_message(chat_id=admin_chat_id, text=message, parse_mode=ParseMode.HTML)
