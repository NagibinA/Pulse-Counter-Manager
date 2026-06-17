"""Базовый класс сенсора."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from ..const import DOMAIN


class PulseCounterBaseSensor(SensorEntity):
    """Базовый класс сенсора."""

    def __init__(self, handler):
        self.handler = handler
        self._attr_device_info = {
            "identifiers": {(DOMAIN, handler.counter_id)},
            "name": handler.name,
            "manufacturer": "NagibinA",
            "model": f"Pulse Counter ({handler.meter_type})",
        }
        self._attr_should_poll = False

    async def async_added_to_hass(self):
        self.async_on_remove(self.handler.async_add_listener(self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()