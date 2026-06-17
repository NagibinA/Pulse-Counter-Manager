"""Сенсоры для интеграции Pulse Counter Manager."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..const import (
    DOMAIN,
    METER_TYPE_ELECTRICITY,
)

from .base import PulseCounterBaseSensor
from .electricity import (
    PulseCounterDayKwhSensor,
    PulseCounterNightKwhSensor,
    PulseCounterTotalValueSensor as ElectricityTotalValueSensor,
    PulseCounterMonthTotalCostSensor,
    PulseCounterMonthDayKwhSensor,
    PulseCounterMonthNightKwhSensor,
    PulseCounterMonthTotalKwhSensor,
    PulseCounterMonthDayCostSensor,
    PulseCounterMonthNightCostSensor,
)
from .utility import (
    PulseCounterTotalValueSensor as UtilityTotalValueSensor,
    PulseCounterMonthValueSensor,
    PulseCounterMonthCostSensor,
    PulseCounterImpulsesSensor,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Настройка сенсоров."""
    sensors = []
    handler_manager = hass.data[DOMAIN].get("handler_manager")

    if not handler_manager:
        return

    for handler in handler_manager.handlers.values():
        meter_type = handler.meter_type

        if meter_type == METER_TYPE_ELECTRICITY:
            sensors.extend([
                PulseCounterMonthTotalCostSensor(handler),
                PulseCounterDayKwhSensor(handler),
                PulseCounterNightKwhSensor(handler),
                ElectricityTotalValueSensor(handler),
                PulseCounterMonthDayKwhSensor(handler),
                PulseCounterMonthNightKwhSensor(handler),
                PulseCounterMonthTotalKwhSensor(handler),
                PulseCounterMonthDayCostSensor(handler),
                PulseCounterMonthNightCostSensor(handler),
                PulseCounterImpulsesSensor(handler),
            ])
        else:
            sensors.extend([
                PulseCounterMonthCostSensor(handler),
                UtilityTotalValueSensor(handler),
                PulseCounterMonthValueSensor(handler),
                PulseCounterImpulsesSensor(handler),
            ])

    async_add_entities(sensors, True)