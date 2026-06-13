"""MQTT обработчик для связи с ESP."""

import asyncio
import logging
from datetime import datetime

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    STATE_DAY,
    STATE_NIGHT,
    CONF_NAME,
    CONF_COUNTER_ID,
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
)

_LOGGER = logging.getLogger(__name__)


class PulseCounterMQTTHandler:
    """Обработчик MQTT сообщений и накопления импульсов."""

    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, config: dict):
        self.hass = hass
        self.config = config
        self.name = config[CONF_NAME]
        self.counter_id = config[CONF_COUNTER_ID]
        
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        
        self.topic_day = config[CONF_MQTT_TOPIC_DAY]
        self.topic_night = config[CONF_MQTT_TOPIC_NIGHT]
        self.topic_command = config[CONF_MQTT_TOPIC_COMMAND]
        self.topic_available = config[CONF_MQTT_TOPIC_AVAILABLE]
        
        self.day_tariff = config[CONF_DAY_TARIFF]
        self.night_tariff = config[CONF_NIGHT_TARIFF]
        self.night_start = config[CONF_NIGHT_START]
        self.night_end = config[CONF_NIGHT_END]
        self.pulses_per_kwh = config[CONF_PULSES_PER_KWH]
        
        self.legacy_mqtt = config.get(CONF_LEGACY_MQTT, False)
        self.legacy_topic_day = config.get(CONF_LEGACY_TOPIC_DAY, "HomeAssistant/daily")
        self.legacy_topic_night = config.get(CONF_LEGACY_TOPIC_NIGHT, "HomeAssistant/nighttime")
        
        self._day_partial = 0
        self._night_partial = 0
        self._day_total_kwh = config.get(CONF_INITIAL_DAY_KWH, 0)
        self._night_total_kwh = config.get(CONF_INITIAL_NIGHT_KWH, 0)
        
        self._month_start_day = self._day_total_kwh
        self._month_start_night = self._night_total_kwh
        self._last_reset_date = None
        
        self._last_month_day = 0
        self._last_month_night = 0
        self._last_month_total = 0
        self._last_month_date = None
        
        self.current_tariff = STATE_DAY
        self.esp_available = False
        
        self._client = None
        self._is_shutdown = False
        self._listeners = []
        
        # Для сенсора "Имп./мин."
        self._last_day_impulses_raw = 0
        self._last_night_impulses_raw = 0
        self._last_impulses_per_minute = 0
        
        _LOGGER.info("Инициализирован обработчик для счетчика %s", self.name)

    def async_add_listener(self, update_callback):
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    async def _notify_listeners(self):
        for listener in self._listeners:
            listener()

    async def async_initialize(self):
        await self._connect_mqtt()
        await self._update_current_tariff()
        self._schedule_tariff_switching()      # отправка команд каждую минуту
        self._schedule_monthly_reset_check()
        self._schedule_impulses_update()        # обновление сенсора каждую минуту
        if self.legacy_mqtt:
            self._schedule_legacy_updates()
        _LOGGER.info("Обработчик счетчика %s запущен", self.name)

    async def async_shutdown(self):
        self._is_shutdown = True
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        _LOGGER.info("Обработчик счетчика %s остановлен", self.name)

    async def _connect_mqtt(self):
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        
        if self.username and self.password:
            self._client.username_pw_set(self.username, self.password)
        
        self._client.connect(self.broker, self.port, 60)
        self._client.loop_start()
        
        for _ in range(10):
            if self._is_shutdown:
                return
            await asyncio.sleep(0.5)
            if self._client.is_connected():
                break

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info("Подключен к MQTT брокеру %s:%s для счетчика %s", self.broker, self.port, self.name)
            self._client.subscribe(self.topic_day)
            self._client.subscribe(self.topic_night)
            self._client.subscribe(self.topic_available)
        else:
            _LOGGER.error("Ошибка подключения к MQTT: %s", rc)

    def _on_message(self, client, userdata, msg):
        if self._is_shutdown:
            return
        
        topic = msg.topic
        payload = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload
        
        if topic == self.topic_day:
            try:
                impulses = int(payload)
                self._last_day_impulses_raw = impulses
                self.hass.loop.create_task(self._process_impulses(impulses, "day"))
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)
        elif topic == self.topic_night:
            try:
                impulses = int(payload)
                self._last_night_impulses_raw = impulses
                self.hass.loop.create_task(self._process_impulses(impulses, "night"))
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)
        elif topic == self.topic_available:
            self.esp_available = (payload == "Включен")
            _LOGGER.info("ESP статус для счетчика %s: %s", self.name, "доступна" if self.esp_available else "недоступна")

    async def _process_impulses(self, impulses: int, tariff: str):
        if tariff == "day":
            total = self._day_partial + impulses
            if total >= self.pulses_per_kwh:
                kwh_added = total // self.pulses_per_kwh
                self._day_total_kwh += kwh_added
                self._day_partial = total % self.pulses_per_kwh
                _LOGGER.debug("День: +%d кВт·ч, всего=%.1f", kwh_added, self._day_total_kwh)
            else:
                self._day_partial = total
        else:
            total = self._night_partial + impulses
            if total >= self.pulses_per_kwh:
                kwh_added = total // self.pulses_per_kwh
                self._night_total_kwh += kwh_added
                self._night_partial = total % self.pulses_per_kwh
                _LOGGER.debug("Ночь: +%d кВт·ч, всего=%.1f", kwh_added, self._night_total_kwh)
            else:
                self._night_partial = total
        
        await self._notify_listeners()

    async def _update_current_tariff(self):
        """Определение текущего тарифа и отправка команды КАЖДУЮ МИНУТУ."""
        now = dt_util.now().time()
        night_start = datetime.strptime(self.night_start, "%H:%M").time()
        night_end = datetime.strptime(self.night_end, "%H:%M").time()
        
        if night_start <= night_end:
            is_night = night_start <= now < night_end
        else:
            is_night = now >= night_start or now < night_end
        
        new_tariff = STATE_NIGHT if is_night else STATE_DAY
        
        # Обновляем текущий тариф если изменился
        if new_tariff != self.current_tariff:
            self.current_tariff = new_tariff
            _LOGGER.debug("Тариф изменился: %s", self.current_tariff)
        
        # ОТПРАВЛЯЕМ КОМАНДУ КАЖДУЮ МИНУТУ
        await self._send_command(self.current_tariff)

    async def _send_command(self, command: str):
        """Отправка команды на ESP."""
        if not self.esp_available:
            _LOGGER.debug("ESP недоступна, команда %s не отправлена", command)
            return
        if self._client:
            self._client.publish(self.topic_command, command)
            _LOGGER.debug("Отправлена команда: %s в топик %s", command, self.topic_command)
        else:
            _LOGGER.warning("Нет клиента, команда не отправлена")

    async def _update_impulses_per_minute(self):
        """Обновление сенсора импульсов (даже если нет новых)."""
        if self.current_tariff == STATE_DAY:
            self._last_impulses_per_minute = self._last_day_impulses_raw
        else:
            self._last_impulses_per_minute = self._last_night_impulses_raw
        
        # Обнуляем сырые значения после того, как они были показаны
        if self.current_tariff == STATE_DAY:
            self._last_day_impulses_raw = 0
        else:
            self._last_night_impulses_raw = 0
        
        await self._notify_listeners()

    def _schedule_tariff_switching(self):
        """Периодическая проверка тарифа и отправка команд каждую минуту."""
        async def _check_tariff(now):
            await self._update_current_tariff()
        async_track_time_change(self.hass, _check_tariff, second=0)

    def _schedule_impulses_update(self):
        """Запланировать обновление сенсора импульсов каждую минуту."""
        async def _update(now):
            await self._update_impulses_per_minute()
        async_track_time_change(self.hass, _update, second=5)  # чуть позже, после отправки команды

    def _schedule_monthly_reset_check(self):
        async def _check_reset(now):
            await self._check_month_reset()
        async_track_time_change(self.hass, _check_reset, hour=0, minute=1, second=0)

    def _schedule_legacy_updates(self):
        async def _send_legacy(now):
            if self.legacy_mqtt and self._client:
                self._client.publish(self.legacy_topic_day, str(self._day_total_kwh))
                self._client.publish(self.legacy_topic_night, str(self._night_total_kwh))
        async_track_time_change(self.hass, _send_legacy, minute=range(0, 60), second=0)

    async def _check_month_reset(self):
        today = dt_util.now().date()
        
        if self._last_reset_date is None:
            self._month_start_day = self._day_total_kwh
            self._month_start_night = self._night_total_kwh
            self._last_reset_date = today
            return
        
        if today.month != self._last_reset_date.month or today.year != self._last_reset_date.year:
            self._last_month_day = self._month_start_day
            self._last_month_night = self._month_start_night
            self._last_month_total = self._month_start_day + self._month_start_night
            self._last_month_date = self._last_reset_date
            
            self._month_start_day = self._day_total_kwh
            self._month_start_night = self._night_total_kwh
            self._last_reset_date = today
            
            await self._notify_listeners()
            _LOGGER.info("Выполнен сброс месячных показаний для счетчика %s", self.name)

    # ========== Свойства для сенсоров ==========
    
    @property
    def day_kwh(self) -> float:
        return self._day_total_kwh

    @property
    def night_kwh(self) -> float:
        return self._night_total_kwh

    @property
    def total_kwh(self) -> float:
        return self._day_total_kwh + self._night_total_kwh

    @property
    def month_day_kwh(self) -> float:
        consumption = self._day_total_kwh - self._month_start_day
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def month_night_kwh(self) -> float:
        consumption = self._night_total_kwh - self._month_start_night
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def month_total_kwh(self) -> float:
        return round(self.month_day_kwh + self.month_night_kwh, 2)

    @property
    def month_day_cost(self) -> float:
        return round(self.month_day_kwh * self.day_tariff, 2)

    @property
    def month_night_cost(self) -> float:
        return round(self.month_night_kwh * self.night_tariff, 2)

    @property
    def month_total_cost(self) -> float:
        return round(self.month_day_cost + self.month_night_cost, 2)

    @property
    def last_month_day_kwh(self) -> float:
        return self._last_month_day

    @property
    def last_month_night_kwh(self) -> float:
        return self._last_month_night

    @property
    def last_month_total_kwh(self) -> float:
        return self._last_month_total

    @property
    def current_raw_impulses(self) -> int:
        """Текущее значение для сенсора Имп./мин."""
        return self._last_impulses_per_minute