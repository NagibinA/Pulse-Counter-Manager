"""Универсальный обработчик для воды, газа, тепла."""

import logging

from homeassistant.core import HomeAssistant

from ..const import (
    CONF_MQTT_TOPIC_MAIN,
    CONF_TARIFF,
)
from .base import BaseMQTTHandler

_LOGGER = logging.getLogger(__name__)


class PulseCounterUtilityMQTTHandler(BaseMQTTHandler):
    """Универсальный обработчик для воды, газа, тепла."""

    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, config: dict):
        super().__init__(hass, broker, port, username, password, config)

        self.topic_main = config.get(CONF_MQTT_TOPIC_MAIN, "")
        self.tariff = config.get(CONF_TARIFF, 0)

        _LOGGER.info("Топик для %s: %s", self.name, self.topic_main)

    async def async_delete_state(self) -> None:
        """Удалить состояние из хранилища."""
        await super().async_delete_state()
        _LOGGER.info("Удалено состояние для счетчика %s", self.name)

    def _subscribe_topics(self):
        if self.topic_main:
            self._client.subscribe(self.topic_main)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload

        if topic == self.topic_available:
            self.esp_available = (payload == "Включен")
            _LOGGER.info("Статус счетчика %s: %s", self.name, "доступен" if self.esp_available else "недоступен")
            return

        if topic == self.topic_main:
            try:
                impulses = int(payload)
                self._last_impulses_raw = impulses
                if not self._is_shutdown:
                    self.hass.loop.create_task(self._process_impulses(impulses))
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)

    @property
    def month_cost(self) -> float:
        return round(self.month_value * self.tariff, 2)