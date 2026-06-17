"""Логика отправки уведомлений."""

import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.components import persistent_notification
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    METER_TYPE_ELECTRICITY,
)

_LOGGER = logging.getLogger(__name__)


class NotificationSender:
    """Отправка уведомлений."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def send_notification(
        self,
        handler,
        is_test: bool = False,
    ) -> int:
        """Отправить уведомление с показаниями счетчика."""
        message_lines = []
        message_title = "📊 Показания счетчика"

        message_lines.append(f"🏠 {handler.name}")
        message_lines.append("")

        if handler.meter_type == METER_TYPE_ELECTRICITY:
            self._add_electricity_lines(handler, message_lines)
        else:
            self._add_utility_lines(handler, message_lines)

        if handler.notification_show_custom_message and handler.notification_custom_message:
            message_lines.append(f"💬 {handler.notification_custom_message}")

        message = "\n".join(message_lines)
        notification_id = self._get_notification_id(handler, is_test)

        _LOGGER.info("=" * 60)
        _LOGGER.info("Отправка уведомления для счетчика: %s", handler.name)
        _LOGGER.info("Тип: %s", "ТЕСТОВОЕ" if is_test else "ЕЖЕМЕСЯЧНОЕ")
        _LOGGER.info("Сообщение:\n%s", message)

        success_count = 0

        # Отправка в Home Assistant
        if handler.notification_send_to_ha:
            _LOGGER.info("→ Отправка в Home Assistant")
            persistent_notification.async_create(
                self.hass,
                message,
                title=message_title,
                notification_id=notification_id
            )
            _LOGGER.info("✓ Отправлено в Home Assistant")
            success_count += 1

        # Отправка на мобильные устройства
        all_services = self.hass.services.async_services()
        notify_services = all_services.get("notify", [])

        for device_service in handler.notification_target_devices:
            if not device_service.startswith("notify."):
                device_service = f"notify.{device_service}"

            service_name = device_service.replace("notify.", "")
            if service_name in notify_services:
                _LOGGER.info("→ Отправка на устройство: %s", device_service)
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service_name,
                        {
                            "title": message_title,
                            "message": message,
                            "data": {"ttl": 0, "priority": "high"}
                        },
                        blocking=False
                    )
                    _LOGGER.info("✓ Отправлено на %s", device_service)
                    success_count += 1
                except Exception as e:
                    _LOGGER.error("❌ Ошибка отправки на %s: %s", device_service, e)
            else:
                _LOGGER.warning("Сервис не найден: %s", device_service)

        _LOGGER.info("✅ Уведомление отправлено в %d мест", success_count)
        _LOGGER.info("=" * 60)

        return success_count

    def _add_electricity_lines(self, handler, message_lines: list):
        if handler.notification_show_day:
            message_lines.append(f"☀️ День: {handler.day_kwh:.1f} kWh")
        if handler.notification_show_night:
            message_lines.append(f"🌙 Ночь: {handler.night_kwh:.1f} kWh")
        if handler.notification_show_total:
            message_lines.append(f"📈 Всего: {handler.total_value:.1f} kWh")
        if handler.notification_show_month:
            message_lines.append(f"📅 За месяц: {handler.month_total_kwh:.1f} kWh")
        if handler.notification_show_day_month:
            message_lines.append(f"☀️ День за месяц: {handler.month_day_kwh:.1f} kWh")
        if handler.notification_show_night_month:
            message_lines.append(f"🌙 Ночь за месяц: {handler.month_night_kwh:.1f} kWh")
        if handler.notification_show_cost:
            message_lines.append(f"💰 Стоимость: {handler.month_total_cost:.2f} руб")

    def _add_utility_lines(self, handler, message_lines: list):
        if handler.notification_show_total:
            message_lines.append(f"📈 Всего: {handler.total_value:.1f} {handler.unit}")
        if handler.notification_show_month:
            message_lines.append(f"📅 За месяц: {handler.month_value:.1f} {handler.unit}")
        if handler.notification_show_cost:
            message_lines.append(f"💰 Стоимость: {handler.month_cost:.2f} руб")

    def _get_notification_id(self, handler, is_test: bool) -> str:
        if is_test:
            return f"pulse_counter_test_{handler.counter_id}_{int(time.time())}"
        return f"pulse_counter_monthly_{handler.counter_id}"


class NotificationScheduler:
    """Планировщик ежемесячных уведомлений."""

    def __init__(self, hass: HomeAssistant, handler_manager):
        self.hass = hass
        self.handler_manager = handler_manager
        self.sender = NotificationSender(hass)
        self._sent_today = set()

    async def check_monthly_notifications(self, now) -> None:
        """Проверка необходимости отправки уведомлений."""
        if DOMAIN not in self.hass.data:
            return

        current = dt_util.now()
        current_day = current.day
        current_hour = current.hour
        current_minute = current.minute

        for counter_id, handler in self.handler_manager.handlers.items():
            if not handler.notification_enabled:
                continue

            if counter_id in self._sent_today:
                continue

            try:
                time_parts = handler.notification_time.split(":")
                target_hour = int(time_parts[0])
                target_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            except (ValueError, IndexError):
                _LOGGER.warning("Неверный формат времени для %s: %s", handler.name, handler.notification_time)
                continue

            if (current_day == handler.notification_day and
                current_hour == target_hour and
                current_minute == target_minute):
                
                _LOGGER.info("Отправка уведомления для %s", handler.name)
                await self.sender.send_notification(handler, is_test=False)
                self._sent_today.add(counter_id)

        # Очистка в конце дня
        if current_hour == 23 and current_minute == 59:
            self._sent_today.clear()