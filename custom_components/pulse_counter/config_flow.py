"""Настройка интеграции через UI."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_NAME,
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
)


class PulseCounterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow для Pulse Counter Manager."""

    VERSION = 1

    def __init__(self):
        self._data = {}
        self._name = None

    async def async_step_user(self, user_input=None):
        """Первый шаг - MQTT топики."""
        errors = {}

        if user_input is not None:
            self._name = user_input[CONF_NAME]
            self._data.update(user_input)
            return await self.async_step_tariff()

        schema = vol.Schema({
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_MQTT_TOPIC_DAY, default=DEFAULT_MQTT_TOPIC_DAY): str,
            vol.Required(CONF_MQTT_TOPIC_NIGHT, default=DEFAULT_MQTT_TOPIC_NIGHT): str,
            vol.Required(CONF_MQTT_TOPIC_COMMAND, default=DEFAULT_MQTT_TOPIC_COMMAND): str,
            vol.Required(CONF_MQTT_TOPIC_AVAILABLE, default=DEFAULT_MQTT_TOPIC_AVAILABLE): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_tariff(self, user_input=None):
        """Второй шаг - тарифы."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_initial_values()

        schema = vol.Schema({
            vol.Required(CONF_DAY_TARIFF, default=DEFAULT_DAY_TARIFF): vol.Coerce(float),
            vol.Required(CONF_NIGHT_TARIFF, default=DEFAULT_NIGHT_TARIFF): vol.Coerce(float),
            vol.Required(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): str,
            vol.Required(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): str,
            vol.Required(CONF_PULSES_PER_KWH, default=DEFAULT_PULSES_PER_KWH): vol.Coerce(int),
        })

        return self.async_show_form(
            step_id="tariff",
            data_schema=schema,
        )

    async def async_step_initial_values(self, user_input=None):
        """Третий шаг - начальные показания."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_legacy()

        schema = vol.Schema({
            vol.Required(CONF_INITIAL_DAY_KWH, default=0): vol.Coerce(float),
            vol.Required(CONF_INITIAL_NIGHT_KWH, default=0): vol.Coerce(float),
        })

        return self.async_show_form(
            step_id="initial_values",
            data_schema=schema,
        )

    async def async_step_legacy(self, user_input=None):
        """Четвертый шаг - legacy MQTT."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._name,
                data=self._data,
            )

        schema = vol.Schema({
            vol.Required(CONF_LEGACY_MQTT, default=False): bool,
            vol.Optional(CONF_LEGACY_TOPIC_DAY, default="HomeAssistant/daily"): str,
            vol.Optional(CONF_LEGACY_TOPIC_NIGHT, default="HomeAssistant/nighttime"): str,
        })

        return self.async_show_form(
            step_id="legacy",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Обработка изменения опций."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Required(
                CONF_DAY_TARIFF,
                default=self.config_entry.options.get(CONF_DAY_TARIFF, DEFAULT_DAY_TARIFF)
            ): vol.Coerce(float),
            vol.Required(
                CONF_NIGHT_TARIFF,
                default=self.config_entry.options.get(CONF_NIGHT_TARIFF, DEFAULT_NIGHT_TARIFF)
            ): vol.Coerce(float),
            vol.Required(
                CONF_NIGHT_START,
                default=self.config_entry.options.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
            ): str,
            vol.Required(
                CONF_NIGHT_END,
                default=self.config_entry.options.get(CONF_NIGHT_END, DEFAULT_NIGHT_END)
            ): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
