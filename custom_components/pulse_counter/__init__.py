"""Инициализация интеграции Pulse Counter Manager."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    VERSION,
    CONF_COUNTERS,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTER_ID,
    CONF_NOTIFICATION_ENABLED,
    CONF_NOTIFICATION_DAY,
    CONF_NOTIFICATION_TIME,
    CONF_NOTIFICATION_SHOW_DAY,
    CONF_NOTIFICATION_SHOW_NIGHT,
    CONF_NOTIFICATION_SHOW_TOTAL,
    CONF_NOTIFICATION_SHOW_COST,
    CONF_NOTIFICATION_SHOW_MONTH,
    CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_TARGET_DEVICES,
    CONF_NOTIFICATION_SEND_TO_HA,
    DEFAULT_NOTIFICATION_DAY,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_SHOW_DAY,
    DEFAULT_NOTIFICATION_SHOW_NIGHT,
    DEFAULT_NOTIFICATION_SHOW_TOTAL,
    DEFAULT_NOTIFICATION_SHOW_COST,
    DEFAULT_NOTIFICATION_SHOW_MONTH,
    DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    DEFAULT_NOTIFICATION_TARGET_DEVICES,
    DEFAULT_NOTIFICATION_SEND_TO_HA,
)

from .handlers import HandlerManager
from .notification import NotificationSender, NotificationScheduler

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    handler_manager = HandlerManager(hass)
    hass.data[DOMAIN]["handler_manager"] = handler_manager

    broker = entry.data[CONF_MQTT_BROKER]
    port = entry.data[CONF_MQTT_PORT]
    username = entry.data.get(CONF_MQTT_USERNAME, "")
    password = entry.data.get(CONF_MQTT_PASSWORD, "")

    counters = entry.data.get(CONF_COUNTERS, {})

    for counter_config in counters.values():
        counter_id = counter_config[CONF_COUNTER_ID]
        handler = await handler_manager.create_handler(
            counter_id, counter_config, broker, port, username, password
        )
        _apply_notification_settings(handler, counter_config)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def async_add_counter(counter_config):
        counter_id = counter_config[CONF_COUNTER_ID]
        handler = await handler_manager.create_handler(
            counter_id, counter_config, broker, port, username, password
        )
        _apply_notification_settings(handler, counter_config)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_counter", async_add_counter)
    )

    sender = NotificationSender(hass)
    scheduler = NotificationScheduler(hass, handler_manager)
    hass.data[DOMAIN]["notification_sender"] = sender

    async_track_time_interval(hass, scheduler.check_monthly_notifications, timedelta(seconds=30))

    async def handle_ha_stop(event):
        _LOGGER.info("Остановка Home Assistant, прекращение опроса ESP")
        await handler_manager.stop_all()
        _LOGGER.info("Опрос всех счетчиков остановлен, состояние сохранено")

    async def handle_ha_start(event):
        _LOGGER.info("Запуск Home Assistant, возобновление опроса ESP")
        await handler_manager.start_all()
        _LOGGER.info("Опрос всех счетчиков возобновлен")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_ha_stop)

    if hass.state == CoreState.running:
        await handle_ha_start(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_ha_start)

    _LOGGER.info("Pulse Counter Manager v%s успешно загружен с %d счетчиками",
                 VERSION, len(handler_manager.handlers))

    return True


def _apply_notification_settings(handler, counter_config):
    handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
    handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
    handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
    handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
    handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
    handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
    handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
    handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
    handler.notification_show_custom_message = counter_config.get(CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE, DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE)
    handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
    handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
    handler.notification_send_to_ha = counter_config.get(CONF_NOTIFICATION_SEND_TO_HA, DEFAULT_NOTIFICATION_SEND_TO_HA)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    _LOGGER.info("Выгрузка Pulse Counter Manager")

    handler_manager = hass.data[DOMAIN].get("handler_manager")
    if handler_manager:
        # Создаём копию списка, чтобы избежать изменения во время итерации
        for handler in list(handler_manager.handlers.values()):
            await handler.async_delete_state()
        await handler_manager.shutdown_all()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data:
            hass.data.pop(DOMAIN)
        _LOGGER.info("Pulse Counter Manager успешно выгружен, данные очищены")
    else:
        _LOGGER.error("Ошибка при выгрузке Pulse Counter Manager")

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    _LOGGER.info("Обновление конфигурации Pulse Counter Manager")
    await hass.config_entries.async_reload(entry.entry_id)