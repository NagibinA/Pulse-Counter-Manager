"""Config Flow для Pulse Counter Manager."""

import logging
import asyncio
import socket
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTERS,
    CONF_COUNTER_ID,
    CONF_MQTT_TOPIC_DAY,
    CONF_MQTT_TOPIC_NIGHT,
    CONF_MQTT_TOPIC_COMMAND,
    CONF_MQTT_TOPIC_AVAILABLE,
    CONF_DAY_TARIFF,
    CONF_NIGHT_TARIFF,
    CONF_NIGHT_START,
    CONF_NIGHT_END,
    CONF_PULSES_PER_KWH,
    CONF_LEGACY_MQTT,
    CONF_LEGACY_TOPIC_DAY,
    CONF_LEGACY_TOPIC_NIGHT,
    CONF_INITIAL_DAY_KWH,
    CONF_INITIAL_NIGHT_KWH,
    DEFAULT_DAY_TARIFF,
    DEFAULT_NIGHT_TARIFF,
    DEFAULT_NIGHT_START,
    DEFAULT_NIGHT_END,
    DEFAULT_PULSES_PER_KWH,
    DEFAULT_MQTT_TOPIC_DAY,
    DEFAULT_MQTT_TOPIC_NIGHT,
    DEFAULT_MQTT_TOPIC_COMMAND,
    DEFAULT_MQTT_TOPIC_AVAILABLE,
    DEFAULT_LEGACY_TOPIC_DAY,
    DEFAULT_LEGACY_TOPIC_NIGHT,
)

_LOGGER = logging.getLogger(__name__)

MQTT_SCHEMA = vol.Schema({
    vol.Required(CONF_MQTT_BROKER, default="192.168.1.11"): str,
    vol.Required(CONF_MQTT_PORT, default=1883): int,
    vol.Optional(CONF_MQTT_USERNAME): str,
    vol.Optional(CONF_MQTT_PASSWORD): str,
})


async def test_mqtt_connection(broker, port, username=None, password=None):
    """Проверка подключения к MQTT брокеру."""
    try:
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        await loop.run_in_executor(None, sock.connect, (broker, port))
        sock.close()
        return True
    except Exception as e:
        _LOGGER.error("Ошибка подключения к MQTT брокеру %s:%s - %s", broker, port, e)
        return False


class PulseCounterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow для Pulse Counter Manager."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Первый шаг - подключение к MQTT брокеру."""
        errors = {}
        
        if user_input is not None:
            _LOGGER.info("Проверка подключения к MQTT брокеру %s:%s", 
                        user_input[CONF_MQTT_BROKER], user_input[CONF_MQTT_PORT])
            
            connected = await test_mqtt_connection(
                user_input[CONF_MQTT_BROKER],
                user_input[CONF_MQTT_PORT],
                user_input.get(CONF_MQTT_USERNAME),
                user_input.get(CONF_MQTT_PASSWORD)
            )
            
            if connected:
                broker = user_input[CONF_MQTT_BROKER]
                title = f"Pulse Counter ({broker})"
                
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_MQTT_BROKER: broker,
                        CONF_MQTT_PORT: user_input[CONF_MQTT_PORT],
                        CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                        CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
                        CONF_COUNTERS: {},
                    }
                )
            else:
                errors["base"] = "cannot_connect"
        
        return self.async_show_form(
            step_id="user",
            data_schema=MQTT_SCHEMA,
            errors=errors
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Настройки интеграции - добавление счетчиков."""
    
    def __init__(self, config_entry):
        self._entry = config_entry
    
    async def async_step_init(self, user_input=None):
        """Главное меню."""
        
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_counter":
                return await self.async_step_add_counter()
            else:
                return self.async_create_entry(title="", data={})
        
        actions = {
            "add_counter": "Добавить счетчик",
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)})
        )
    
    async def async_step_add_counter(self, user_input=None):
        """Добавление счетчика."""
        errors = {}
        
        counters = self._entry.data.get(CONF_COUNTERS, {})
        used_names = list(counters.keys())
        
        if user_input is not None:
            try:
                counter_name = user_input[CONF_NAME]
                
                if counter_name in used_names:
                    errors[CONF_NAME] = "name_exists"
                else:
                    counter_id = f"counter_{counter_name.lower().replace(' ', '_')}"
                    
                    new_counter = {
                        CONF_COUNTER_ID: counter_id,
                        CONF_NAME: counter_name,
                        CONF_MQTT_TOPIC_DAY: user_input[CONF_MQTT_TOPIC_DAY],
                        CONF_MQTT_TOPIC_NIGHT: user_input[CONF_MQTT_TOPIC_NIGHT],
                        CONF_MQTT_TOPIC_COMMAND: user_input[CONF_MQTT_TOPIC_COMMAND],
                        CONF_MQTT_TOPIC_AVAILABLE: user_input[CONF_MQTT_TOPIC_AVAILABLE],
                        CONF_DAY_TARIFF: user_input[CONF_DAY_TARIFF],
                        CONF_NIGHT_TARIFF: user_input[CONF_NIGHT_TARIFF],
                        CONF_NIGHT_START: user_input[CONF_NIGHT_START],
                        CONF_NIGHT_END: user_input[CONF_NIGHT_END],
                        CONF_PULSES_PER_KWH: user_input[CONF_PULSES_PER_KWH],
                        CONF_INITIAL_DAY_KWH: user_input[CONF_INITIAL_DAY_KWH],
                        CONF_INITIAL_NIGHT_KWH: user_input[CONF_INITIAL_NIGHT_KWH],
                        CONF_LEGACY_MQTT: user_input.get(CONF_LEGACY_MQTT, False),
                        CONF_LEGACY_TOPIC_DAY: user_input.get(CONF_LEGACY_TOPIC_DAY, DEFAULT_LEGACY_TOPIC_DAY),
                        CONF_LEGACY_TOPIC_NIGHT: user_input.get(CONF_LEGACY_TOPIC_NIGHT, DEFAULT_LEGACY_TOPIC_NIGHT),
                    }
                    
                    new_counters = dict(counters)
                    new_counters[counter_name] = new_counter
                    
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={**self._entry.data, CONF_COUNTERS: new_counters}
                    )
                    
                    if DOMAIN not in self.hass.data:
                        self.hass.data[DOMAIN] = {}
                    self.hass.data[DOMAIN][CONF_COUNTERS] = new_counters
                    
                    async_dispatcher_send(self.hass, f"{DOMAIN}_add_counter", new_counter)
                    
                    return self.async_create_entry(title="", data={})
                    
            except Exception as e:
                _LOGGER.exception("Ошибка при добавлении счетчика: %s", e)
                errors["base"] = "invalid_data"
        
        schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_MQTT_TOPIC_DAY, default=DEFAULT_MQTT_TOPIC_DAY): str,
            vol.Required(CONF_MQTT_TOPIC_NIGHT, default=DEFAULT_MQTT_TOPIC_NIGHT): str,
            vol.Required(CONF_MQTT_TOPIC_COMMAND, default=DEFAULT_MQTT_TOPIC_COMMAND): str,
            vol.Required(CONF_MQTT_TOPIC_AVAILABLE, default=DEFAULT_MQTT_TOPIC_AVAILABLE): str,
            vol.Required(CONF_DAY_TARIFF, default=DEFAULT_DAY_TARIFF): vol.Coerce(float),
            vol.Required(CONF_NIGHT_TARIFF, default=DEFAULT_NIGHT_TARIFF): vol.Coerce(float),
            vol.Required(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): str,
            vol.Required(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): str,
            vol.Required(CONF_PULSES_PER_KWH, default=DEFAULT_PULSES_PER_KWH): int,
            vol.Required(CONF_INITIAL_DAY_KWH, default=0): vol.Coerce(float),
            vol.Required(CONF_INITIAL_NIGHT_KWH, default=0): vol.Coerce(float),
            vol.Optional(CONF_LEGACY_MQTT, default=False): bool,
            vol.Optional(CONF_LEGACY_TOPIC_DAY, default=DEFAULT_LEGACY_TOPIC_DAY): str,
            vol.Optional(CONF_LEGACY_TOPIC_NIGHT, default=DEFAULT_LEGACY_TOPIC_NIGHT): str,
        })
        
        return self.async_show_form(
            step_id="add_counter",
            data_schema=schema,
            errors=errors
        )
