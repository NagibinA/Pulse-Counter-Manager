"""Инициализация интеграции Pulse Counter Manager."""

import logging

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
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
        hass.data[DOMAIN]["polling_enabled"] = False

    broker = entry.data[CONF_MQTT_BROKER]
    port = entry.data[CONF_MQTT_PORT]
    username = entry.data.get(CONF_MQTT_USERNAME, "")
    password = entry.data.get(CONF_MQTT_PASSWORD, "")
    
    counters = entry.data.get(CONF_COUNTERS, {})
    
    # Создаем обработчики для каждого счетчика
    for counter_name, counter_config in counters.items():
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
    
    # Регистрируем платформы сенсоров
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Добавляем слушатель обновления опций
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    # Слушатель для добавления нового счетчика через опции
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
    
    # Обработчик остановки HA (ИСПРАВЛЕН)
    async def handle_ha_stop(event):
        """При остановке HA останавливаем опрос ESP."""
        _LOGGER.info("Остановка Home Assistant, прекращение опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = False
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_stop_polling()
            await handler.async_save_state()
        _LOGGER.info("Опрос всех счетчиков остановлен, состояние сохранено")

    # Обработчик запуска HA
    async def handle_ha_start(event):
        """При запуске HA возобновляем опрос ESP."""
        _LOGGER.info("Запуск Home Assistant, возобновление опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = True
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_start_polling()
        _LOGGER.info("Опрос всех счетчиков возобновлен")
    
    # Регистрируем обработчики событий
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_ha_stop)
    
    # Если HA уже запущен, запускаем опрос сразу, иначе ждем события старта
    if hass.state == CoreState.running:
        await handle_ha_start(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_ha_start)
    
    _LOGGER.info("Pulse Counter Manager v%s успешно загружен с %d счетчиками", 
                 VERSION, len(hass.data[DOMAIN]["handlers"]))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    
    _LOGGER.info("Выгрузка Pulse Counter Manager")
    
    # Останавливаем все обработчики
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        await handler.async_shutdown()
    
    hass.data[DOMAIN]["handlers"].clear()
    hass.data[DOMAIN]["polling_enabled"] = False
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        if not hass.data[DOMAIN]["handlers"]:
            hass.data.pop(DOMAIN)
        _LOGGER.info("Pulse Counter Manager успешно выгружен")
    else:
        _LOGGER.error("Ошибка при выгрузке Pulse Counter Manager")
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    _LOGGER.info("Обновление конфигурации Pulse Counter Manager")
    await hass.config_entries.async_reload(entry.entry_id)
