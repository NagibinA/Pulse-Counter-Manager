"""Сенсоры для интеграции Pulse Counter Manager."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import (
    DOMAIN,
    UNIT_RUB,
    UNIT_KWH,
    UNIT_IMPULSE,
)


async def async_setup_entry(hass, entry, async_add_entities):
    handler = hass.data[DOMAIN]["devices"][entry.entry_id]
    
    sensors = [
        PulseCounterTotalKwhSensor(handler),
        PulseCounterDayKwhSensor(handler),
        PulseCounterNightKwhSensor(handler),
        PulseCounterDayCostSensor(handler),
        PulseCounterNightCostSensor(handler),
        PulseCounterTotalCostSensor(handler),
        PulseCounterImpulsesSensor(handler),
    ]
    
    async_add_entities(sensors, True)


class PulseCounterBaseSensor(SensorEntity):
    def __init__(self, handler):
        self.handler = handler
        self._attr_device_info = {
            "identifiers": {(DOMAIN, handler.entry_id)},
            "name": handler.name,
            "manufacturer": "NagibinA",
            "model": "Pulse Counter Manager",
        }
        self._attr_should_poll = False

    async def async_added_to_hass(self):
        self.async_on_remove(self.handler.async_add_listener(self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


class PulseCounterTotalKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_total_kwh"
        self._attr_name = f"{handler.name} Общее потребление"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"

    @property
    def state(self):
        return round(self.handler.total_kwh, 2)


class PulseCounterDayKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_day_kwh"
        self._attr_name = f"{handler.name} Дневное потребление"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"

    @property
    def state(self):
        return round(self.handler.day_kwh, 2)


class PulseCounterNightKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_night_kwh"
        self._attr_name = f"{handler.name} Ночное потребление"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"

    @property
    def state(self):
        return round(self.handler.night_kwh, 2)


class PulseCounterDayCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_day_cost"
        self._attr_name = f"{handler.name} Стоимость день"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.day_cost

    @property
    def extra_state_attributes(self):
        return {"tariff": self.handler.day_tariff}


class PulseCounterNightCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_night_cost"
        self._attr_name = f"{handler.name} Стоимость ночь"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.night_cost

    @property
    def extra_state_attributes(self):
        return {"tariff": self.handler.night_tariff}


class PulseCounterTotalCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_total_cost"
        self._attr_name = f"{handler.name} Общая стоимость"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.total_cost

    @property
    def extra_state_attributes(self):
        return {
            "day_cost": self.handler.day_cost,
            "night_cost": self.handler.night_cost,
            "day_tariff": self.handler.day_tariff,
            "night_tariff": self.handler.night_tariff,
            "current_tariff": self.handler.current_tariff,
        }


class PulseCounterImpulsesSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.entry_id}_impulses"
        self._attr_name = f"{handler.name} Накопленные импульсы"
        self._attr_unit_of_measurement = UNIT_IMPULSE
        self._attr_icon = "mdi:pulse"

    @property
    def state(self):
        return self.handler.day_partial_impulses + self.handler.night_partial_impulses

    @property
    def extra_state_attributes(self):
        return {
            "day_partial": self.handler.day_partial_impulses,
            "night_partial": self.handler.night_partial_impulses,
            "pulses_per_kwh": self.handler.pulses_per_kwh,
        }
