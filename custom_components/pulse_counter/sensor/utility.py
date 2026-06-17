"""Сенсоры для однотарифных счетчиков (вода, газ, тепло)."""

from homeassistant.const import EntityCategory

from ..const import UNIT_RUB
from .base import PulseCounterBaseSensor


class PulseCounterTotalValueSensor(PulseCounterBaseSensor):
    """Общее потребление (все время) - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_total"
        self._attr_name = f"{handler.name} Всего"
        self._attr_native_unit_of_measurement = handler.unit
        self._attr_device_class = "energy"
        self._attr_state_class = "total_increasing"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if handler.meter_type == "water":
            self._attr_icon = "mdi:water"
        elif handler.meter_type == "gas":
            self._attr_icon = "mdi:fire"
        else:
            self._attr_icon = "mdi:radiator"

    @property
    def state(self):
        return round(self.handler.total_value, 2)


class PulseCounterMonthValueSensor(PulseCounterBaseSensor):
    """Потребление за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_value"
        self._attr_name = f"{handler.name} За месяц"
        self._attr_native_unit_of_measurement = handler.unit
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

        if handler.meter_type == "water":
            self._attr_icon = "mdi:water"
        elif handler.meter_type == "gas":
            self._attr_icon = "mdi:fire"
        else:
            self._attr_icon = "mdi:radiator"

    @property
    def state(self):
        return self.handler.month_value


class PulseCounterMonthCostSensor(PulseCounterBaseSensor):
    """Стоимость за месяц - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_month_cost"
        self._attr_name = f"{handler.name} Стоимость"
        self._attr_native_unit_of_measurement = UNIT_RUB
        self._attr_device_class = "monetary"
        self._attr_state_class = "total"
        self._attr_icon = "mdi:cash"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

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
    """Получено импульсов за минуту - ДИАГНОСТИКА."""

    def __init__(self, handler):
        super().__init__(handler)
        self._attr_unique_id = f"{handler.counter_id}_impulses_per_minute"
        self._attr_name = f"{handler.name} Получено импульсов"
        self._attr_native_unit_of_measurement = "имп/мин"
        self._attr_icon = "mdi:pulse"
        self._attr_state_class = "measurement"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def state(self):
        return self.handler.current_raw_impulses