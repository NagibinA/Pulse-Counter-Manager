"""Инициализация интеграции Pulse Counter Manager."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DOMAIN,
    VERSION,
    CONF_COUNTERS,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTER_ID,
    METER_TYPE_ELECTRICITY,
)

from .mqtt_handler import (
    PulseCounterMQTTHandler,
    PulseCounterWaterMQTTHandler,
    PulseCounterGasMQTTHandler,
    PulseCounterHeatMQTTHandler,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из config entry."""
    
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][CONF_COUNTERS] = {}
        hass.data[DOMAIN]["handlers"] = {}

    broker = entry.data[CONF_MQTT_BROKER]
    port = entry.data[CONF_MQTT_PORT]
    username = entry.data.get(CONF_MQTT_USERNAME, "")
    password = entry.data.get(CONF_MQTT_PASSWORD, "")
    
    counters = entry.data.get(CONF_COUNTERS, {})
    
    for counter_name, counter_config in counters.items():
        meter_type = counter_config.get("meter_type", METER_TYPE_ELECTRICITY)
        
        if meter_type == METER_TYPE_ELECTRICITY:
            handler_class = PulseCounterMQTTHandler
        else:
            # Для воды, газа, тепла - пока один класс, потом разделим
            handler_class = PulseCounterWaterMQTTHandler
        
        handler = handler_class(
            hass,
            broker=broker,
            port=port,
            username=username,
            password=password,
            config=counter_config,
        )
        await handler.async_initialize()
        hass.data[DOMAIN]["handlers"][counter_config[CONF_COUNTER_ID]] = handler
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    async def async_add_counter(counter_config):
        meter_type = counter_config.get("meter_type", METER_TYPE_ELECTRICITY)
        
        if meter_type == METER_TYPE_ELECTRICITY:
            handler_class = PulseCounterMQTTHandler
        else:
            handler_class = PulseCounterWaterMQTTHandler
        
        handler = handler_class(
            hass,
            broker=broker,
            port=port,
            username=username,
            password=password,
            config=counter_config,
        )
        await handler.async_initialize()
        hass.data[DOMAIN]["handlers"][counter_config[CONF_COUNTER_ID]] = handler
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_counter", async_add_counter)
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        await handler.async_shutdown()
    
    hass.data[DOMAIN]["handlers"].clear()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data.pop(DOMAIN)
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    await hass.config_entries.async_reload(entry.entry_id)
