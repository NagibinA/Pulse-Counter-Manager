"""Утилиты для config flow."""

import asyncio
import socket
import re
import logging

import voluptuous as vol

from .const import (
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
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


def validate_time_format(time_str: str) -> bool:
    """Проверка формата времени HH:MM."""
    pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    return bool(pattern.match(time_str))


def get_topic_preview(topic: str, context: str = "") -> str:
    """Создает предпросмотр MQTT топика."""
    if not topic:
        return "—"

    preview = topic
    if "{name}" in preview and context:
        preview = preview.replace("{name}", context.lower().replace(" ", "_"))

    return preview