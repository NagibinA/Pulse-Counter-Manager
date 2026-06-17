"""Логика отправки уведомлений."""

import logging
import time
from typing import Optional

from homeassistant.core import HomeAssistant
from homeassistant.components import persistent_notification

from .const import (
    DOMAIN,
    METER_TYPE_ELECTRICITY,
    CONF_NOTIFICATION_SEND_TO_HA,
    CONF_NOTIFICATION_TARGET_DEVICES,
    CONF_NOTIFICATION_SHOW_DAY,
    CONF_NOTIFICATION_SHOW_NIGHT,
    CONF_NOTIFICATION_SHOW_TOTAL,
    CONF_NOTIFICATION_SHOW_COST,
    CONF_NOTIFICATION_SHOW_MONTH,
    CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_CUSTOM_MESSAGE,
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
        """Отправить уведомление с показаниями счетчика.

        Returns:
            Количество успешных отправок
        """
        message_lines = []

        if is_test:
            message_lines.append("🧪 **ТЕСТОВОЕ УВЕДОМЛЕНИЕ**")
            message_lines.append("")

        message_lines.append(f"🏠 **{handler.name}**")
        message_lines.append("")

        if handler.meter_type == METER_TYPE_ELECTRICITY:
            self._add_electricity_lines(handler, message_lines)
        else:
            self._add_utility_lines(handler, message_lines)

        if handler.notification_show_custom_message and handler.notification_custom_message:
            message_lines.append("")
            message_lines.append(f"💬 {handler.notification_custom_message}")

        if is_test:
            message_lines.append("")
            message_lines.append(f"⏰ {time.strftime('%H:%M:%S')}")

        message = "\n".join(message_lines)
        message_title = "📊 Показания счетчика"

        notification_id = self._get_notification_id(handler, is_test)

        return await self._send_to_targets(handler, message, message_title, notification_id)

    def _add_electricity_lines(self, handler, message_lines: list):
        if handler.notification_show_day:
            message_lines.append(f"☀️ День: **{handler.day_kwh:.1f}** kWh")
        if handler.notification_show_night:
            message_lines.append(f"🌙 Ночь: **{handler.night_kwh:.1f}** kWh")
        if handler.notification_show_total:
            message_lines.append(f"📈 Всего: **{handler.total_value:.1f}** kWh")
        if handler.notification_show_month:
            message_lines.append(f"📅 За месяц: **{handler.month_value:.1f}** kWh")
        if handler.notification_show_cost:
            message_lines.append(f"💰 Стоимость за месяц: **{handler.month_total_cost:.2f}** руб")

    def _add_utility_lines(self, handler, message_lines: list):
        if handler.notification_show_total:
            message_lines.append(f"📈 Всего: **{handler.total_value:.1f}** {handler.unit}")
        if handler.notification_show_month:
            message_lines.append(f"📅 За месяц: **{handler.month_value:.1f}** {handler.unit}")
        if handler.notification_show_cost:
            message_lines.append(f"💰 Стоимость за месяц: **{handler.month_cost:.2f}** руб")

    def _get_notification_id(self, handler, is_test: bool) -> str:
        if is_test:
            return f"pulse_counter_test_{handler.counter_id}_{int(time.time())}"
        return f"pulse_counter_monthly_{handler.counter_id}"

    async def _send_to_targets(
        self,
        handler,
        message: str,
        title: str,
        notification_id: str,
    ) -> int:
        _LOGGER.info("=" * 60)
        _LOGGER.info("Отправка уведомления для счетчика: %s", handler.name)
        _LOGGER.info("Отправлять в Home Assistant: %s", handler.notification_send_to_ha)
        _LOGGER.info("Выбранные устройства: %s", handler.notification_target_devices)

        success_count = 0

        if handler.notification_send_to_ha:
            _LOGGER.info("→ Отправка в Home Assistant")
            persistent_notification.async_create(
                self.hass,
                message,
                title=title,
                notification_id=notification_id
            )
            _LOGGER.info("✓ Отправлено в Home Assistant")
            success_count += 1

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
                            "title": title,
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


class NotificationScheduler:
    """Планировщик ежемесячных уведомлений."""

    def __init__(self, hass: HomeAssistant, handler_manager):
        self.hass = hass
        self.handler_manager = handler_manager
        self.sender = NotificationSender(hass)

    async def check_monthly_notifications(self, now) -> None:
        if DOMAIN not in self.hass.data:
            return

        current = now
        current_day = current.day
        current_hour = current.hour
        current_minute = current.minute

        for counter_id, handler in self.handler_manager.handlers.items():
            if not handler.notification_enabled:
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
                if not self.handler_manager.notified_this_month.get(counter_id, False):
                    _LOGGER.info("Наступило время отправки уведомления для %s", handler.name)
                    await self.sender.send_notification(handler, is_test=False)
                    self.handler_manager.notified_this_month[counter_id] = True

        if current_day == 1 and current_hour == 0 and current_minute == 0:
            for counter_id in self.handler_manager.notified_this_month:
                self.handler_manager.notified_this_month[counter_id] = False
            _LOGGER.info("Флаги уведомлений сброшены")