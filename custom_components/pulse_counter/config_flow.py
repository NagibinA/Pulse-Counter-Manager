"""Config Flow для Pulse Counter Manager."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTERS,
)
from .config_flow_utils import test_mqtt_connection, MQTT_SCHEMA
from .config_flow_edit import OptionsFlowHandler

_LOGGER = logging.getLogger(__name__)


class PulseCounterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow для Pulse Counter Manager."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Первый шаг - настройка MQTT брокера."""
        errors = {}

        if user_input is not None:
            _LOGGER.info("Проверка подключения к MQTT брокеру %s:%s",
                        user_input[CONF_MQTT_BROKER], user_input[CONF_MQTT_PORT])

            for entry in self._async_current_entries():
                if (entry.data.get(CONF_MQTT_BROKER) == user_input[CONF_MQTT_BROKER] and
                    entry.data.get(CONF_MQTT_PORT) == user_input[CONF_MQTT_PORT]):
                    return self.async_abort(reason="broker_already_configured")

            connected = await test_mqtt_connection(
                user_input[CONF_MQTT_BROKER],
                user_input[CONF_MQTT_PORT],
                user_input.get(CONF_MQTT_USERNAME),
                user_input.get(CONF_MQTT_PASSWORD)
            )

            if connected:
                broker = user_input[CONF_MQTT_BROKER]
                port = user_input[CONF_MQTT_PORT]
                title = f"Счетчики подключенные через брокер MQTT ({broker}:{port})"

                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_MQTT_BROKER: broker,
                        CONF_MQTT_PORT: port,
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
            errors=errors,
            description_placeholders={
                "info": "Укажите параметры MQTT брокера, к которому подключены ESP.",
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)