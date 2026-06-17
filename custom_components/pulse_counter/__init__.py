"""Инициализация интеграции Pulse Counter Manager."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, CoreState, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
import voluptuous as vol

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
    CONF_NOTIFICATION_SHOW_DAY_MONTH,
    CONF_NOTIFICATION_SHOW_NIGHT_MONTH,
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
    DEFAULT_NOTIFICATION_SHOW_DAY_MONTH,
    DEFAULT_NOTIFICATION_SHOW_NIGHT_MONTH,
    DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    DEFAULT_NOTIFICATION_TARGET_DEVICES,
    DEFAULT_NOTIFICATION_SEND_TO_HA,
)

from .handlers import HandlerManager
from .notification import NotificationSender, NotificationScheduler

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

# Схемы для сервисов
SERVICE_SET_DAY_KWH_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
    vol.Required("value"): vol.Coerce(float),
})

SERVICE_SET_NIGHT_KWH_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
    vol.Required("value"): vol.Coerce(float),
})

SERVICE_SET_TOTAL_VALUE_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
    vol.Required("value"): vol.Coerce(float),
})

SERVICE_SET_MONTH_START_DAY_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
    vol.Required("day"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
})

SERVICE_RESET_MONTHLY_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
})

SERVICE_TEST_NOTIFICATION_SCHEMA = vol.Schema({
    vol.Required("entity_id"): str,
})


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

    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_counter", async_add_counter)
    )

    # Инициализация уведомлений
    sender = NotificationSender(hass)
    scheduler = NotificationScheduler(hass, handler_manager)
    hass.data[DOMAIN]["notification_sender"] = sender
    hass.data[DOMAIN]["notification_scheduler"] = scheduler

    # Проверка уведомлений каждые 30 секунд
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

    # Регистрация сервисов
    async def async_set_day_kwh(call: ServiceCall) -> None:
        """Установить дневные показания."""
        entity_id = call.data.get("entity_id")
        value = call.data.get("value")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_day_kwh" == entity_id:
                await handler.async_set_day_kwh(value)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    async def async_set_night_kwh(call: ServiceCall) -> None:
        """Установить ночные показания."""
        entity_id = call.data.get("entity_id")
        value = call.data.get("value")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_night_kwh" == entity_id:
                await handler.async_set_night_kwh(value)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    async def async_set_total_value(call: ServiceCall) -> None:
        """Установить показания."""
        entity_id = call.data.get("entity_id")
        value = call.data.get("value")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_total" == entity_id:
                await handler.async_set_total_value(value)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    async def async_set_month_start_day(call: ServiceCall) -> None:
        """Установить день начала месяца."""
        entity_id = call.data.get("entity_id")
        day = call.data.get("day")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_total" == entity_id:
                await handler.async_set_month_start_day(day)
                _LOGGER.info("Установлен день начала месяца %d для %s", day, handler.name)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    async def async_reset_monthly(call: ServiceCall) -> None:
        """Сбросить месячные показания."""
        entity_id = call.data.get("entity_id")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_month_total_cost" == entity_id:
                if handler.meter_type == "electricity":
                    await handler.async_set_month_start_day_kwh(handler.day_kwh)
                    await handler.async_set_month_start_night(handler.night_kwh)
                else:
                    await handler.async_set_month_start_value(handler.total_value)
                _LOGGER.info("Сброшены месячные показания для %s", handler.name)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    async def async_test_notification(call: ServiceCall) -> None:
        """Отправить тестовое уведомление."""
        entity_id = call.data.get("entity_id")
        for handler in handler_manager.handlers.values():
            if f"{DOMAIN}.{handler.counter_id}_month_total_cost" == entity_id or \
               f"{DOMAIN}.{handler.counter_id}_month_cost" == entity_id:
                # Используем NotificationSender для отправки теста
                sender = NotificationSender(hass)
                await sender.send_notification(handler, is_test=True)
                return
        _LOGGER.warning("Счетчик для entity %s не найден", entity_id)

    hass.services.async_register(DOMAIN, "set_day_kwh", async_set_day_kwh, schema=SERVICE_SET_DAY_KWH_SCHEMA)
    hass.services.async_register(DOMAIN, "set_night_kwh", async_set_night_kwh, schema=SERVICE_SET_NIGHT_KWH_SCHEMA)
    hass.services.async_register(DOMAIN, "set_total_value", async_set_total_value, schema=SERVICE_SET_TOTAL_VALUE_SCHEMA)
    hass.services.async_register(DOMAIN, "set_month_start_day", async_set_month_start_day, schema=SERVICE_SET_MONTH_START_DAY_SCHEMA)
    hass.services.async_register(DOMAIN, "reset_monthly", async_reset_monthly, schema=SERVICE_RESET_MONTHLY_SCHEMA)
    hass.services.async_register(DOMAIN, "test_notification", async_test_notification, schema=SERVICE_TEST_NOTIFICATION_SCHEMA)

    _LOGGER.info("Pulse Counter Manager v%s успешно загружен с %d счетчиками",
                 VERSION, len(handler_manager.handlers))

    return True


def _apply_notification_settings(handler, counter_config):
    """Применить настройки уведомлений к обработчику."""
    handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
    handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
    handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
    handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
    handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
    handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
    handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
    handler.notification_show_day_month = counter_config.get(CONF_NOTIFICATION_SHOW_DAY_MONTH, DEFAULT_NOTIFICATION_SHOW_DAY_MONTH)
    handler.notification_show_night_month = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT_MONTH, DEFAULT_NOTIFICATION_SHOW_NIGHT_MONTH)
    handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
    handler.notification_show_custom_message = counter_config.get(CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE, DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE)
    handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
    handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
    handler.notification_send_to_ha = counter_config.get(CONF_NOTIFICATION_SEND_TO_HA, DEFAULT_NOTIFICATION_SEND_TO_HA)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции (без удаления данных)."""
    _LOGGER.info("Выгрузка Pulse Counter Manager")

    handler_manager = hass.data[DOMAIN].get("handler_manager")
    if handler_manager:
        # НЕ УДАЛЯЕМ ДАННЫЕ ПРИ ПЕРЕЗАГРУЗКЕ
        # Только останавливаем обработчики
        await handler_manager.shutdown_all()

    # Удаляем сервисы
    for service in ["set_day_kwh", "set_night_kwh", "set_total_value", "set_month_start_day", "reset_monthly", "test_notification"]:
        hass.services.async_remove(DOMAIN, service)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        if DOMAIN in hass.data:
            hass.data.pop(DOMAIN)
        _LOGGER.info("Pulse Counter Manager успешно выгружен")
    else:
        _LOGGER.error("Ошибка при выгрузке Pulse Counter Manager")

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Полное удаление интеграции с очисткой данных."""
    _LOGGER.info("Удаление Pulse Counter Manager с очисткой данных")

    handler_manager = hass.data[DOMAIN].get("handler_manager")
    if handler_manager:
        for handler in list(handler_manager.handlers.values()):
            await handler.async_delete_state()
        await handler_manager.shutdown_all()

    # Удаляем сервисы
    for service in ["set_day_kwh", "set_night_kwh", "set_total_value", "set_month_start_day", "reset_monthly", "test_notification"]:
        hass.services.async_remove(DOMAIN, service)

    if DOMAIN in hass.data:
        hass.data.pop(DOMAIN)

    _LOGGER.info("Pulse Counter Manager полностью удален, данные очищены")


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    _LOGGER.info("Обновление конфигурации Pulse Counter Manager")
    await hass.config_entries.async_reload(entry.entry_id)