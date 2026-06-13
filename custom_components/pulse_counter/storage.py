"""Хранилище состояния."""

import logging
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORAGE_KEY = f"{DOMAIN}.state"
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


class PulseCounterStorage:
    def __init__(self, hass, entry_id: str):
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")

    async def async_save(self, data: dict) -> None:
        try:
            await self._store.async_save(data)
        except Exception as e:
            _LOGGER.error(f"Ошибка сохранения: {e}")

    async def async_load(self):
        try:
            return await self._store.async_load()
        except Exception as e:
            _LOGGER.error(f"Ошибка загрузки: {e}")
        return None

    async def async_close(self):
        pass
