"""Управление обработчиками счетчиков."""

import logging
from typing import Dict, Optional

from homeassistant.core import HomeAssistant

from ..const import (
    DOMAIN,
    METER_TYPE_ELECTRICITY,
    CONF_COUNTER_ID,
)
from .base import BaseMQTTHandler
from .electricity import PulseCounterMQTTHandler
from .utility import PulseCounterUtilityMQTTHandler

_LOGGER = logging.getLogger(__name__)


class HandlerManager:
    """Менеджер обработчиков счетчиков."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._handlers: Dict[str, BaseMQTTHandler] = {}
        self._notified_this_month: Dict[str, bool] = {}
        self._polling_enabled = False

    @property
    def handlers(self) -> Dict[str, BaseMQTTHandler]:
        return self._handlers

    @property
    def notified_this_month(self) -> Dict[str, bool]:
        return self._notified_this_month

    @property
    def polling_enabled(self) -> bool:
        return self._polling_enabled

    @polling_enabled.setter
    def polling_enabled(self, value: bool):
        self._polling_enabled = value

    def get_handler(self, counter_id: str) -> Optional[BaseMQTTHandler]:
        return self._handlers.get(counter_id)

    async def create_handler(
        self,
        counter_id: str,
        config: dict,
        broker: str,
        port: int,
        username: str,
        password: str,
    ) -> BaseMQTTHandler:
        """Создать и инициализировать обработчик."""
        meter_type = config.get("meter_type", METER_TYPE_ELECTRICITY)

        if meter_type == METER_TYPE_ELECTRICITY:
            handler = PulseCounterMQTTHandler(
                self.hass,
                broker=broker,
                port=port,
                username=username,
                password=password,
                config=config,
            )
        else:
            handler = PulseCounterUtilityMQTTHandler(
                self.hass,
                broker=broker,
                port=port,
                username=username,
                password=password,
                config=config,
            )

        await handler.async_initialize()
        self._handlers[counter_id] = handler
        self._notified_this_month[counter_id] = False

        _LOGGER.info("Создан обработчик для счетчика %s (ID: %s)", config.get("name"), counter_id)
        return handler

    async def remove_handler(self, counter_id: str) -> None:
        """Удалить обработчик и его данные."""
        handler = self._handlers.pop(counter_id, None)
        if handler:
            await handler.async_delete_state()
            await handler.async_shutdown()
            self._notified_this_month.pop(counter_id, None)
            _LOGGER.info("Удален обработчик и данные счетчика %s", counter_id)

    async def stop_all(self) -> None:
        """Остановить все обработчики."""
        self._polling_enabled = False
        for handler in self._handlers.values():
            await handler.async_stop_polling()
            await handler.async_save_state()
        _LOGGER.info("Все обработчики остановлены")

    async def start_all(self) -> None:
        """Запустить все обработчики."""
        self._polling_enabled = True
        for handler in self._handlers.values():
            await handler.async_start_polling()
        _LOGGER.info("Все обработчики запущены")

    async def shutdown_all(self) -> None:
        """Завершить все обработчики."""
        # Создаём копию списка, чтобы избежать изменения во время итерации
        for handler in list(self._handlers.values()):
            await handler.async_shutdown()
        self._handlers.clear()
        self._notified_this_month.clear()
        _LOGGER.info("Все обработчики завершены")