"""Инициализация интеграции Pulse Counter Manager."""

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers import service

from .const import DOMAIN, CONF_DEVICES
from .mqtt_handler import PulseCounterMQTTHandler

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из config entry."""
    
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][CONF_DEVICES] = {}

    # Создаем обработчик MQTT для этого устройства
    mqtt_handler = PulseCounterMQTTHandler(hass, entry)
    await mqtt_handler.async_initialize()
    
    hass.data[DOMAIN][CONF_DEVICES][entry.entry_id] = mqtt_handler

    # Регистрация сервисов
    async def handle_set_day_kwh(call):
        value = call.data.get("value")
        await mqtt_handler.async_set_day_kwh(value)

    async def handle_set_night_kwh(call):
        value = call.data.get("value")
        await mqtt_handler.async_set_night_kwh(value)

    async def handle_reset_monthly(call):
        await mqtt_handler.async_reset_monthly()

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "set_day_kwh",
        handle_set_day_kwh,
        schema=vol.Schema({vol.Required("value"): vol.Coerce(float)}),
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "set_night_kwh",
        handle_set_night_kwh,
        schema=vol.Schema({vol.Required("value"): vol.Coerce(float)}),
    )

    service.async_register_admin_service(
        hass,
        DOMAIN,
        "reset_monthly",
        handle_reset_monthly,
        schema=vol.Schema({}),
    )

    # Регистрируем платформы
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    
    mqtt_handler = hass.data[DOMAIN][CONF_DEVICES].pop(entry.entry_id)
    await mqtt_handler.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if not hass.data[DOMAIN][CONF_DEVICES]:
        hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    await hass.config_entries.async_reload(entry.entry_id)
