"""MQTT обработчик для связи с ESP."""

import logging
from datetime import datetime

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_MQTT_TOPIC_DAY,
    CONF_MQTT_TOPIC_NIGHT,
    CONF_MQTT_TOPIC_COMMAND,
    CONF_MQTT_TOPIC_AVAILABLE,
    CONF_DAY_TARIFF,
    CONF_NIGHT_TARIFF,
    CONF_NIGHT_START,
    CONF_NIGHT_END,
    CONF_PULSES_PER_KWH,
    CONF_LEGACY_MQTT,
    CONF_LEGACY_TOPIC_DAY,
    CONF_LEGACY_TOPIC_NIGHT,
    CONF_INITIAL_DAY_KWH,
    CONF_INITIAL_NIGHT_KWH,
    STATE_DAY,
    STATE_NIGHT,
)
from .storage import PulseCounterStorage

_LOGGER = logging.getLogger(__name__)


class PulseCounterMQTTHandler:
    """Обработчик MQTT сообщений и накопления импульсов."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self.name = entry.data[CONF_NAME]
        self.entry_id = entry.entry_id

        # MQTT топики
        self.topic_day = entry.data[CONF_MQTT_TOPIC_DAY]
        self.topic_night = entry.data[CONF_MQTT_TOPIC_NIGHT]
        self.topic_command = entry.data[CONF_MQTT_TOPIC_COMMAND]
        self.topic_available = entry.data[CONF_MQTT_TOPIC_AVAILABLE]

        # Тарифы
        self.day_tariff = entry.options.get(CONF_DAY_TARIFF, entry.data.get(CONF_DAY_TARIFF, 8.10))
        self.night_tariff = entry.options.get(CONF_NIGHT_TARIFF, entry.data.get(CONF_NIGHT_TARIFF, 4.42))
        
        # Время тарифов
        self.night_start = entry.options.get(CONF_NIGHT_START, entry.data.get(CONF_NIGHT_START, "20:19"))
        self.night_end = entry.options.get(CONF_NIGHT_END, entry.data.get(CONF_NIGHT_END, "04:19"))

        self.pulses_per_kwh = entry.data.get(CONF_PULSES_PER_KWH, 1000)

        # Legacy MQTT
        self.legacy_mqtt = entry.data.get(CONF_LEGACY_MQTT, False)
        self.legacy_topic_day = entry.data.get(CONF_LEGACY_TOPIC_DAY, "HomeAssistant/daily")
        self.legacy_topic_night = entry.data.get(CONF_LEGACY_TOPIC_NIGHT, "HomeAssistant/nighttime")

        # Состояние счетчика
        self._day_partial = 0
        self._night_partial = 0
        self._day_total_kwh = entry.data.get(CONF_INITIAL_DAY_KWH, 0)
        self._night_total_kwh = entry.data.get(CONF_INITIAL_NIGHT_KWH, 0)

        self.current_tariff = STATE_DAY
        self.esp_available = False

        self.storage = PulseCounterStorage(hass, self.entry_id)
        self._is_shutdown = False
        self._listeners = []

    def async_add_listener(self, update_callback):
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    async def _notify_listeners(self):
        for listener in self._listeners:
            listener()

    async def async_initialize(self):
        await self._load_state()
        await self._update_current_tariff()
        await self._subscribe_mqtt()
        self._schedule_tariff_switching()
        if self.legacy_mqtt:
            self._schedule_legacy_updates()
        _LOGGER.info(f"Инициализирован счетчик {self.name}")

    async def async_shutdown(self):
        self._is_shutdown = True
        await self._save_state()
        await self.storage.async_close()
        _LOGGER.info(f"Остановлен счетчик {self.name}")

    async def async_set_day_kwh(self, value: float):
        self._day_total_kwh = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info(f"Установлены дневные показания: {value} кВт·ч")

    async def async_set_night_kwh(self, value: float):
        self._night_total_kwh = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info(f"Установлены ночные показания: {value} кВт·ч")

    async def async_reset_monthly(self):
        self._last_month_day = self._day_total_kwh
        self._last_month_night = self._night_total_kwh
        self._last_month_total = self._day_total_kwh + self._night_total_kwh
        self._last_month_date = dt_util.now().date()
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Произведен сброс месячных показаний")

    async def _load_state(self):
        data = await self.storage.async_load()
        if data:
            self._day_partial = data.get("day_partial", 0)
            self._night_partial = data.get("night_partial", 0)
            self._day_total_kwh = data.get("day_total_kwh", self._day_total_kwh)
            self._night_total_kwh = data.get("night_total_kwh", self._night_total_kwh)
            _LOGGER.debug(f"Загружено состояние: день={self._day_total_kwh}, ночь={self._night_total_kwh}")

    async def _save_state(self):
        data = {
            "day_partial": self._day_partial,
            "night_partial": self._night_partial,
            "day_total_kwh": self._day_total_kwh,
            "night_total_kwh": self._night_total_kwh,
            "last_update": dt_util.utcnow().isoformat(),
        }
        await self.storage.async_save(data)

    async def _subscribe_mqtt(self):
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            _LOGGER.error("MQTT клиент не готов")
            return

        await mqtt.async_subscribe(self.hass, self.topic_day, self._message_received_day, 2)
        await mqtt.async_subscribe(self.hass, self.topic_night, self._message_received_night, 2)
        await mqtt.async_subscribe(self.hass, self.topic_available, self._message_received_available, 2)

    @callback
    def _message_received_day(self, msg):
        if self._is_shutdown:
            return
        try:
            impulses = int(msg.payload)
            self.hass.async_create_task(self._process_impulses(impulses, "day"))
        except ValueError:
            _LOGGER.error(f"Ошибка преобразования: {msg.payload}")

    @callback
    def _message_received_night(self, msg):
        if self._is_shutdown:
            return
        try:
            impulses = int(msg.payload)
            self.hass.async_create_task(self._process_impulses(impulses, "night"))
        except ValueError:
            _LOGGER.error(f"Ошибка преобразования: {msg.payload}")

    @callback
    def _message_received_available(self, msg):
        status = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload
        self.esp_available = (status == "Включен")

    async def _process_impulses(self, impulses: int, tariff: str):
        if tariff == "day":
            total = self._day_partial + impulses
            if total >= self.pulses_per_kwh:
                kwh_added = total // self.pulses_per_kwh
                self._day_total_kwh += kwh_added
                self._day_partial = total % self.pulses_per_kwh
            else:
                self._day_partial = total
        else:
            total = self._night_partial + impulses
            if total >= self.pulses_per_kwh:
                kwh_added = total // self.pulses_per_kwh
                self._night_total_kwh += kwh_added
                self._night_partial = total % self.pulses_per_kwh
            else:
                self._night_partial = total

        await self._save_state()
        await self._notify_listeners()

    async def _update_current_tariff(self):
        now = dt_util.now().time()
        night_start = datetime.strptime(self.night_start, "%H:%M").time()
        night_end = datetime.strptime(self.night_end, "%H:%M").time()

        if night_start <= night_end:
            is_night = night_start <= now < night_end
        else:
            is_night = now >= night_start or now < night_end

        new_tariff = STATE_NIGHT if is_night else STATE_DAY
        
        if new_tariff != self.current_tariff:
            self.current_tariff = new_tariff
            await self._send_tariff_command()

    async def _send_tariff_command(self):
        if not self.esp_available:
            return
        await mqtt.async_publish(self.hass, self.topic_command, self.current_tariff, 2, False)
        _LOGGER.debug(f"Отправлена команда: {self.current_tariff}")

    def _schedule_tariff_switching(self):
        async def _check_tariff(now):
            await self._update_current_tariff()
        async_track_time_change(self.hass, _check_tariff, minute=range(0, 60), second=0)

    def _schedule_legacy_updates(self):
        async def _send_legacy(now):
            if self.legacy_mqtt:
                await mqtt.async_publish(self.hass, self.legacy_topic_day, str(self._day_total_kwh), 1, True)
                await mqtt.async_publish(self.hass, self.legacy_topic_night, str(self._night_total_kwh), 1, True)
        async_track_time_change(self.hass, _send_legacy, minute=range(0, 60), second=0)

    @property
    def day_kwh(self) -> float:
        return self._day_total_kwh

    @property
    def night_kwh(self) -> float:
        return self._night_total_kwh

    @property
    def day_partial_impulses(self) -> int:
        return self._day_partial

    @property
    def night_partial_impulses(self) -> int:
        return self._night_partial

    @property
    def day_cost(self) -> float:
        return round(self._day_total_kwh * self.day_tariff, 2)

    @property
    def night_cost(self) -> float:
        return round(self._night_total_kwh * self.night_tariff, 2)

    @property
    def total_cost(self) -> float:
        return round(self.day_cost + self.night_cost, 2)

    @property
    def total_kwh(self) -> float:
        return self._day_total_kwh + self._night_total_kwh
