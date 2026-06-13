"""Сенсоры для интеграции Pulse Counter Manager."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import (
    DOMAIN,
    UNIT_RUB,
    UNIT_KWH,
    UNIT_M3,
    UNIT_GCAL,
    METER_TYPE_ELECTRICITY,
    METER_TYPE_WATER,
    METER_TYPE_GAS,
    METER_TYPE_HEAT,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Настройка сенсоров."""
    sensors = []
    
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        meter_type = handler.meter_type
        
        if meter_type == METER_TYPE_ELECTRICITY:
            sensors.extend([
                PulseCounterTotalValueSensor(handler),
                PulseCounterDayKwhSensor(handler),
                PulseCounterNightKwhSensor(handler),
                PulseCounterMonthDayKwhSensor(handler),
                PulseCounterMonthNightKwhSensor(handler),
                PulseCounterMonthTotalKwhSensor(handler),
                PulseCounterMonthDayCostSensor(handler),
                PulseCounterMonthNightCostSensor(handler),
                PulseCounterMonthTotalCostSensor(handler),
                PulseCounterImpulsesSensor(handler),
            ])
        else:
            # Для воды, газа, тепла
            sensors.extend([
                PulseCounterTotalValueSensor(handler),
                PulseCounterMonthValueSensor(handler),
                PulseCounterMonthCostSensor(handler),
                PulseCounterImpulsesSensor(handler),
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
            "model": f"Pulse Counter ({handler.meter_type})",
        }
        self._attr_should_poll = False

    async def async_added_to_hass(self):
        self.async_on_remove(self.handler.async_add_listener(self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


"""Сенсоры для интеграции Pulse Counter Manager."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from .const import (
    DOMAIN,
    UNIT_RUB,
    UNIT_KWH,
    UNIT_M3,
    UNIT_GCAL,
    METER_TYPE_ELECTRICITY,
    METER_TYPE_WATER,
    METER_TYPE_GAS,
    METER_TYPE_HEAT,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Настройка сенсоров."""
    sensors = []
    
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        meter_type = handler.meter_type
        
        if meter_type == METER_TYPE_ELECTRICITY:
            sensors.extend([
                PulseCounterTotalValueSensor(handler),
                PulseCounterDayKwhSensor(handler),
                PulseCounterNightKwhSensor(handler),
                PulseCounterMonthDayKwhSensor(handler),
                PulseCounterMonthNightKwhSensor(handler),
                PulseCounterMonthTotalKwhSensor(handler),
                PulseCounterMonthDayCostSensor(handler),
                PulseCounterMonthNightCostSensor(handler),
                PulseCounterMonthTotalCostSensor(handler),
                PulseCounterImpulsesSensor(handler),
            ])
        else:
            # Для воды, газа, тепла
            sensors.extend([
                PulseCounterTotalValueSensor(handler),
                PulseCounterMonthValueSensor(handler),
                PulseCounterMonthCostSensor(handler),
                PulseCounterImpulsesSensor(handler),
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
            "model": f"Pulse Counter ({handler.meter_type})",
        }
        self._attr_should_poll = False

    async def async_added_to_hass(self):
        self.async_on_remove(self.handler.async_add_listener(self._async_update))

    @callback
    def _async_update(self):
        self.async_write_ha_state()


# ========== Общие сенсоры для всех типов ==========

class PulseCounterTotalValueSensor(PulseCounterBaseSensor):
    """Общее потребление (все время)."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_total"
        self._attr_name = f"{handler.name} Всего"
        self._attr_unit_of_measurement = handler.unit
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        
        if handler.meter_type == METER_TYPE_ELECTRICITY:
            self._attr_icon = "mdi:lightning-bolt"
        elif handler.meter_type == METER_TYPE_WATER:
            self._attr_icon = "mdi:water"
        elif handler.meter_type == METER_TYPE_GAS:
            self._attr_icon = "mdi:fire"
        else:
            self._attr_icon = "mdi:radiator"

    @property
    def state(self):
        return round(self.handler.total_value, 2)


class PulseCounterMonthValueSensor(PulseCounterBaseSensor):
    """Потребление за месяц (для однотарифных)."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_value"
        self._attr_name = f"{handler.name} За месяц"
        self._attr_unit_of_measurement = handler.unit
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        
        if handler.meter_type == METER_TYPE_WATER:
            self._attr_icon = "mdi:water"
        elif handler.meter_type == METER_TYPE_GAS:
            self._attr_icon = "mdi:fire"
        else:
            self._attr_icon = "mdi:radiator"

    @property
    def state(self):
        return self.handler.month_value


class PulseCounterMonthCostSensor(PulseCounterBaseSensor):
    """Стоимость за месяц (для однотарифных)."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_cost"
        self._attr_name = f"{handler.name} Стоимость"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash"

    @property
    def state(self):
        return self.handler.month_cost

    @property
    def extra_state_attributes(self):
        return {
            "tariff": self.handler.tariff,
            "consumption": self.handler.month_value,
        }


class PulseCounterImpulsesSensor(PulseCounterBaseSensor):
    """Количество импульсов в минуту."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_impulses_per_minute"
        self._attr_name = f"{handler.name} Имп./мин."
        self._attr_unit_of_measurement = "имп"
        self._attr_icon = "mdi:pulse"

    @property
    def state(self):
        return self.handler.current_raw_impulses


# ========== Специфичные сенсоры для электроэнергии ==========

class PulseCounterDayKwhSensor(PulseCounterBaseSensor):
    """Дневное потребление (все время)."""

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

    @property
    def extra_state_attributes(self):
        return {
            "pulses_per_kwh": self.handler.pulses_per_unit,
            "accumulated_impulses": self.handler._day_partial,
            "accumulated_kwh": round(self.handler._day_partial / self.handler.pulses_per_unit, 3),
        }


class PulseCounterNightKwhSensor(PulseCounterBaseSensor):
    """Ночное потребление (все время)."""

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

    @property
    def extra_state_attributes(self):
        return {
            "pulses_per_kwh": self.handler.pulses_per_unit,
            "accumulated_impulses": self.handler._night_partial,
            "accumulated_kwh": round(self.handler._night_partial / self.handler.pulses_per_unit, 3),
        }


class PulseCounterMonthDayKwhSensor(PulseCounterBaseSensor):
    """Дневное потребление за месяц."""

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
    """Ночное потребление за месяц."""

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
    """Общее потребление за месяц (электричество)."""

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
        return self.handler.month_value


class PulseCounterMonthDayCostSensor(PulseCounterBaseSensor):
    """Стоимость дневного тарифа за месяц."""

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
        return {
            "tariff": self.handler.day_tariff,
            "consumption": self.handler.month_day_kwh,
        }


class PulseCounterMonthNightCostSensor(PulseCounterBaseSensor):
    """Стоимость ночного тарифа за месяц."""

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
        return {
            "tariff": self.handler.night_tariff,
            "consumption": self.handler.month_night_kwh,
        }


class PulseCounterMonthTotalCostSensor(PulseCounterBaseSensor):
    """Общая стоимость за месяц (электричество)."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_total_cost"
        self._attr_name = f"{handler.name} Стоимость всего"
        self._attr_unit_of_measurement = UNIT_RUB
        self._attr_icon = "mdi:cash-multiple"

    @property
    def state(self):
        return self.handler.month_cost

    @property
    def extra_state_attributes(self):
        return {
            "day_cost": self.handler.month_day_cost,
            "night_cost": self.handler.month_night_cost,
            "day_tariff": self.handler.day_tariff,
            "night_tariff": self.handler.night_tariff,
            "current_tariff": self.handler.current_tariff,
        }