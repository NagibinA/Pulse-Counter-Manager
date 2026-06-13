"""Сенсоры для интеграции Pulse Counter Manager."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import DOMAIN, UNIT_RUB, UNIT_KWH


async def async_setup_entry(hass, entry, async_add_entities):
    """Настройка сенсоров."""
    sensors = []
    
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        sensors.extend([
            PulseCounterTotalKwhSensor(handler),
            PulseCounterDayKwhSensor(handler),
            PulseCounterNightKwhSensor(handler),
            PulseCounterMonthDayKwhSensor(handler),
            PulseCounterMonthNightKwhSensor(handler),
            PulseCounterMonthTotalKwhSensor(handler),
            PulseCounterMonthDayCostSensor(handler),
            PulseCounterMonthNightCostSensor(handler),
            PulseCounterMonthTotalCostSensor(handler),
            PulseCounterRawImpulsesSensor(handler),
        ])
    
    async_add_entities(sensors, True)


class PulseCounterBaseSensor(SensorEntity):
    """Базовый класс сенсора."""

    def __init__(self, handler):
        self.handler = handler
        self._attr_device_info = {
            "identifiers": {(DOMAIN, handler.counter_id)},
            "name": handler.name,
            "manufacturer": "NagibinA",
            "model": "Pulse Counter",
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
        self._attr_unique_id = f"{handler.counter_id}_total_kwh"
        self._attr_name = f"{handler.name} Всего"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:counter"

    @property
    def state(self):
        return round(self.handler.total_kwh, 2)


class PulseCounterDayKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_day_kwh"
        self._attr_name = f"{handler.name} День всего"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:weather-sunny"

    @property
    def state(self):
        return round(self.handler.day_kwh, 2)


class PulseCounterNightKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_night_kwh"
        self._attr_name = f"{handler.name} Ночь всего"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_icon = "mdi:weather-night"

    @property
    def state(self):
        return round(self.handler.night_kwh, 2)


class PulseCounterMonthDayKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_day_kwh"
        self._attr_name = f"{handler.name} День за месяц"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:weather-sunny"

    @property
    def state(self):
        return self.handler.month_day_kwh


class PulseCounterMonthNightKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_night_kwh"
        self._attr_name = f"{handler.name} Ночь за месяц"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:weather-night"

    @property
    def state(self):
        return self.handler.month_night_kwh


class PulseCounterMonthTotalKwhSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_total_kwh"
        self._attr_name = f"{handler.name} Всего за месяц"
        self._attr_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def state(self):
        return self.handler.month_total_kwh


class PulseCounterMonthDayCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_day_cost"
        self._attr_name = f"{handler.name} Стоимость день"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.month_day_cost

    @property
    def extra_state_attributes(self):
        return {"tariff": self.handler.day_tariff}


class PulseCounterMonthNightCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_night_cost"
        self._attr_name = f"{handler.name} Стоимость ночь"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.month_night_cost

    @property
    def extra_state_attributes(self):
        return {"tariff": self.handler.night_tariff}


class PulseCounterMonthTotalCostSensor(PulseCounterBaseSensor):
    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_total_cost"
        self._attr_name = f"{handler.name} Стоимость всего"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash-multiple"

    @property
    def state(self):
        return self.handler.month_total_cost

    @property
    def extra_state_attributes(self):
        return {
            "day_cost": self.handler.month_day_cost,
            "night_cost": self.handler.month_night_cost,
            "day_tariff": self.handler.day_tariff,
            "night_tariff": self.handler.night_tariff,
            "current_tariff": self.handler.current_tariff,
        }


class PulseCounterRawImpulsesSensor(PulseCounterBaseSensor):
    """Количество импульсов в минуту (сырое значение от ESP)."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_impulses_per_minute"
        self._attr_name = f"{handler.name} Имп./мин."
        self._attr_unit_of_measurement = "имп"
        self._attr_icon = "mdi:pulse"

    @property
    def state(self):
        return self.handler.current_raw_impulses
