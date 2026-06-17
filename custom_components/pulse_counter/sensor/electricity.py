"""Сенсоры для электроэнергии."""

from homeassistant.const import EntityCategory

from ..const import UNIT_RUB, UNIT_KWH
from .base import PulseCounterBaseSensor


class PulseCounterDayKwhSensor(PulseCounterBaseSensor):
    """Дневное потребление."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_day_kwh"
        self._attr_name = f"{handler.name} Энергия дневная"
        self._attr_native_unit_of_measurement = UNIT_KWH
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
            "accumulated_impulses": self.handler.day_partial_impulses,
            "accumulated_kwh": round(self.handler.day_partial_impulses / self.handler.pulses_per_unit, 3),
        }


class PulseCounterNightKwhSensor(PulseCounterBaseSensor):
    """Ночное потребление."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_night_kwh"
        self._attr_name = f"{handler.name} Энергия ночная"
        self._attr_native_unit_of_measurement = UNIT_KWH
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
            "accumulated_impulses": self.handler.night_partial_impulses,
            "accumulated_kwh": round(self.handler.night_partial_impulses / self.handler.pulses_per_unit, 3),
        }


class PulseCounterTotalValueSensor(PulseCounterBaseSensor):
    """Общее потребление (все время) - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_total"
        self._attr_name = f"{handler.name} Всего"
        self._attr_native_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def state(self):
        return round(self.handler.total_value, 2)


class PulseCounterMonthTotalCostSensor(PulseCounterBaseSensor):
    """Общая стоимость за месяц."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_total_cost"
        self._attr_name = f"{handler.name} Стоимость электричества за месяц"
        self._attr_native_unit_of_measurement = UNIT_RUB
        self._attr_device_class = "monetary"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:wallet"

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
            "month_day_kwh": self.handler.month_day_kwh,
            "month_night_kwh": self.handler.month_night_kwh,
        }


class PulseCounterMonthDayKwhSensor(PulseCounterBaseSensor):
    """Дневное потребление за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_day_kwh"
        self._attr_name = f"{handler.name} Энергия дневная за месяц"
        self._attr_native_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:weather-sunny"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        return self.handler.month_day_kwh


class PulseCounterMonthNightKwhSensor(PulseCounterBaseSensor):
    """Ночное потребление за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_night_kwh"
        self._attr_name = f"{handler.name} Энергия ночная за месяц"
        self._attr_native_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:weather-night"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        return self.handler.month_night_kwh


class PulseCounterMonthTotalKwhSensor(PulseCounterBaseSensor):
    """Общее потребление за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_total_kwh"
        self._attr_name = f"{handler.name} Энергия всего за месяц"
        self._attr_native_unit_of_measurement = UNIT_KWH
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        return self.handler.month_total_kwh


class PulseCounterMonthDayCostSensor(PulseCounterBaseSensor):
    """Стоимость дневного тарифа за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_day_cost"
        self._attr_name = f"{handler.name} Стоимость за дневной тариф в месяц"
        self._attr_native_unit_of_measurement = UNIT_RUB
        self._attr_device_class = "monetary"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:currency-rub"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
    """Стоимость ночного тарифа за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_night_cost"
        self._attr_name = f"{handler.name} Стоимость за ночной тариф в месяц"
        self._attr_native_unit_of_measurement = UNIT_RUB
        self._attr_device_class = "monetary"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:currency-rub"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        return self.handler.month_night_cost

    @property
    def extra_state_attributes(self):
        return {
            "tariff": self.handler.night_tariff,
            "consumption": self.handler.month_night_kwh,
        }