"""Базовый класс для всех обработчиков счетчиков."""

import asyncio
import logging
from datetime import datetime

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from ..const import (
    METER_TYPE_ELECTRICITY,
    EXPORT_BROKER_MAIN,
    EXPORT_BROKER_CUSTOM,
    CONF_NAME,
    CONF_COUNTER_ID,
    CONF_METER_TYPE,
    CONF_UNIT,
    CONF_MQTT_TOPIC_AVAILABLE,
    CONF_PULSES_PER_UNIT,
    CONF_EXPORT_ENABLED,
    CONF_EXPORT_BROKER_MODE,
    CONF_EXPORT_BROKER,
    CONF_EXPORT_PORT,
    CONF_EXPORT_USERNAME,
    CONF_EXPORT_PASSWORD,
    CONF_EXPORT_TOPIC_DAY,
    CONF_EXPORT_TOPIC_NIGHT,
    CONF_INITIAL_VALUE,
    CONF_MONTH_START_VALUE,
    CONF_MONTH_START_DAY_PERIOD,
    DEFAULT_EXPORT_PORT,
    DEFAULT_MONTH_START_DAY_PERIOD,
    DEFAULT_NOTIFICATION_DAY,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_SHOW_DAY,
    DEFAULT_NOTIFICATION_SHOW_NIGHT,
    DEFAULT_NOTIFICATION_SHOW_TOTAL,
    DEFAULT_NOTIFICATION_SHOW_MONTH,
    DEFAULT_NOTIFICATION_SHOW_DAY_MONTH,
    DEFAULT_NOTIFICATION_SHOW_NIGHT_MONTH,
    DEFAULT_NOTIFICATION_SHOW_COST,
    DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    DEFAULT_NOTIFICATION_TARGET_DEVICES,
    DEFAULT_NOTIFICATION_SEND_TO_HA,
)
from ..storage import PulseCounterStorage

_LOGGER = logging.getLogger(__name__)


class BaseMQTTHandler:
    """Базовый класс для всех обработчиков счетчиков."""

    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, config: dict):
        self.hass = hass
        self.config = config
        self.name = config[CONF_NAME]
        self.counter_id = config[CONF_COUNTER_ID]
        self.meter_type = config.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        self.unit = config.get(CONF_UNIT, "ед")
        self.pulses_per_unit = config.get(CONF_PULSES_PER_UNIT, 1000)
        self.month_start_day = config.get(CONF_MONTH_START_DAY_PERIOD, DEFAULT_MONTH_START_DAY_PERIOD)

        self.broker = broker
        self.port = port
        self.username = username
        self.password = password

        self.topic_available = config.get(CONF_MQTT_TOPIC_AVAILABLE, "")

        self.export_enabled = config.get(CONF_EXPORT_ENABLED, False)
        self.export_broker_mode = config.get(CONF_EXPORT_BROKER_MODE, EXPORT_BROKER_MAIN)
        self.export_broker = config.get(CONF_EXPORT_BROKER, None)
        self.export_port = config.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT)
        self.export_username = config.get(CONF_EXPORT_USERNAME, "")
        self.export_password = config.get(CONF_EXPORT_PASSWORD, "")
        self.export_topic_day = config.get(CONF_EXPORT_TOPIC_DAY, "export/day")
        self.export_topic_night = config.get(CONF_EXPORT_TOPIC_NIGHT, "export/night")

        # Поля для уведомлений
        self.notification_enabled = config.get("notification_enabled", False)
        self.notification_day = config.get("notification_day", DEFAULT_NOTIFICATION_DAY)
        self.notification_time = config.get("notification_time", DEFAULT_NOTIFICATION_TIME)
        self.notification_show_day = config.get("notification_show_day", DEFAULT_NOTIFICATION_SHOW_DAY)
        self.notification_show_night = config.get("notification_show_night", DEFAULT_NOTIFICATION_SHOW_NIGHT)
        self.notification_show_total = config.get("notification_show_total", DEFAULT_NOTIFICATION_SHOW_TOTAL)
        self.notification_show_month = config.get("notification_show_month", DEFAULT_NOTIFICATION_SHOW_MONTH)
        self.notification_show_day_month = config.get("notification_show_day_month", DEFAULT_NOTIFICATION_SHOW_DAY_MONTH)
        self.notification_show_night_month = config.get("notification_show_night_month", DEFAULT_NOTIFICATION_SHOW_NIGHT_MONTH)
        self.notification_show_cost = config.get("notification_show_cost", DEFAULT_NOTIFICATION_SHOW_COST)
        self.notification_show_custom_message = config.get("notification_show_custom_message", DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE)
        self.notification_custom_message = config.get("notification_custom_message", "")
        self.notification_target_devices = config.get("notification_target_devices", DEFAULT_NOTIFICATION_TARGET_DEVICES)
        self.notification_send_to_ha = config.get("notification_send_to_ha", DEFAULT_NOTIFICATION_SEND_TO_HA)

        self._partial = 0
        self._total_value = config.get(CONF_INITIAL_VALUE, 0)
        self._month_start_value = config.get(CONF_MONTH_START_VALUE, 0)
        self._last_reset_date = None
        self._last_month_value = 0
        self._last_month_date = None

        self._last_impulses_raw = 0
        self._last_impulses_per_minute = 0

        self._polling_enabled = True
        self._subscribed = False

        self.esp_available = False

        self._client = None
        self._export_client = None
        self._is_shutdown = False
        self._listeners = []

        self.storage = PulseCounterStorage(hass, self.counter_id)

        _LOGGER.info("Инициализирован обработчик для счетчика %s (тип: %s)", self.name, self.meter_type)

    def async_add_listener(self, update_callback):
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    async def _notify_listeners(self):
        for listener in self._listeners:
            listener()

    async def _load_state(self):
        data = await self.storage.async_load()
        if data:
            self._partial = data.get("partial", 0)
            self._total_value = data.get("total_value", self._total_value)
            self._month_start_value = data.get("month_start_value", self._month_start_value)
            self.month_start_day = data.get("month_start_day", self.month_start_day)
            self._last_reset_date = data.get("last_reset_date")
            if self._last_reset_date and isinstance(self._last_reset_date, str):
                self._last_reset_date = datetime.fromisoformat(self._last_reset_date).date()
            self._last_month_value = data.get("last_month_value", 0)
            self._last_month_date = data.get("last_month_date")
            if self._last_month_date and isinstance(self._last_month_date, str):
                self._last_month_date = datetime.fromisoformat(self._last_month_date).date()
            self._last_impulses_per_minute = data.get("last_impulses_per_minute", 0)
            _LOGGER.debug("Загружено состояние для %s: total=%.1f, partial=%d, month_start_day=%d",
                         self.name, self._total_value, self._partial, self.month_start_day)
        else:
            _LOGGER.debug("Нет сохраненного состояния для %s", self.name)

    async def async_save_state(self):
        await self._save_state()

    async def _save_state(self):
        data = {
            "partial": self._partial,
            "total_value": self._total_value,
            "month_start_value": self._month_start_value,
            "month_start_day": self.month_start_day,
            "last_reset_date": self._last_reset_date.isoformat() if self._last_reset_date else None,
            "last_month_value": self._last_month_value,
            "last_month_date": self._last_month_date.isoformat() if self._last_month_date else None,
            "last_impulses_per_minute": self._last_impulses_per_minute,
            "last_update": dt_util.utcnow().isoformat(),
        }
        await self.storage.async_save(data)
        _LOGGER.debug("Сохранено состояние для %s", self.name)

    async def async_delete_state(self) -> None:
        """Удалить состояние из хранилища и сбросить все значения."""
        await self.storage.async_delete()
        self._partial = 0
        self._total_value = 0
        self._month_start_value = 0
        self.month_start_day = DEFAULT_MONTH_START_DAY_PERIOD
        self._last_impulses_per_minute = 0
        self._last_month_value = 0
        self._last_month_date = None
        self._last_reset_date = None
        _LOGGER.info("Удалено состояние для счетчика %s", self.name)

    async def async_initialize(self):
        await self._load_state()
        await self._connect_mqtt()

        timeout = 0
        while not self._subscribed and timeout < 50:
            await asyncio.sleep(0.1)
            timeout += 1

        self._schedule_impulses_update()
        if self.export_enabled:
            await self._connect_export_mqtt()
            self._schedule_export_updates()

        _LOGGER.info("Обработчик счетчика %s запущен", self.name)

    async def async_shutdown(self):
        self._is_shutdown = True
        self._polling_enabled = False
        await self._save_state()
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        if self._export_client and self._export_client != self._client:
            self._export_client.loop_stop()
            self._export_client.disconnect()
        await self.storage.async_close()
        _LOGGER.info("Обработчик счетчика %s остановлен", self.name)

    async def async_stop_polling(self):
        self._polling_enabled = False
        _LOGGER.info("Остановлен опрос ESP для %s", self.name)

    async def async_start_polling(self):
        self._polling_enabled = True
        if hasattr(self, '_update_current_tariff') and callable(getattr(self, '_update_current_tariff')):
            await self._update_current_tariff()
        _LOGGER.info("Возобновлен опрос ESP для %s", self.name)

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

    async def _connect_export_mqtt(self):
        if not self.export_enabled:
            return

        if self.export_broker_mode == EXPORT_BROKER_MAIN:
            self._export_client = self._client
            _LOGGER.debug("Экспорт показаний использует основной брокер для %s", self.name)
            return

        if not self.export_broker:
            _LOGGER.warning("Брокер для экспорта не указан для %s, экспорт отключен", self.name)
            return

        try:
            self._export_client = mqtt.Client()
            if self.export_username and self.export_password:
                self._export_client.username_pw_set(self.export_username, self.export_password)
            self._export_client.connect(self.export_broker, self.export_port, 60)
            self._export_client.loop_start()
            _LOGGER.info("Подключен к брокеру для экспорта %s:%s для счетчика %s",
                        self.export_broker, self.export_port, self.name)
        except Exception as e:
            _LOGGER.error("Ошибка подключения к брокеру для экспорта для %s: %s", self.name, e)
            self._export_client = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info("Подключен к MQTT брокеру %s:%s для счетчика %s", self.broker, self.port, self.name)
            self._subscribe_topics()
            self._subscribed = True
            if self.topic_available:
                self._client.subscribe(self.topic_available)
        else:
            _LOGGER.error("Ошибка подключения к MQTT: %s", rc)

    def _subscribe_topics(self):
        pass

    def _on_message(self, client, userdata, msg):
        pass

    async def _process_impulses(self, impulses: int):
        self._partial += impulses
        if self._partial >= self.pulses_per_unit:
            units_added = self._partial // self.pulses_per_unit
            self._total_value += units_added
            self._partial = self._partial % self.pulses_per_unit
            _LOGGER.debug("%s: +%d %s, всего=%.1f, остаток=%d",
                         self.name, units_added, self.unit, self._total_value, self._partial)
        else:
            _LOGGER.debug("%s: накоплено импульсов=%d", self.name, self._partial)

        await self._save_state()
        await self._notify_listeners()

    async def _update_impulses_per_minute(self):
        self._last_impulses_per_minute = self._last_impulses_raw
        self._last_impulses_raw = 0
        await self._save_state()
        await self._notify_listeners()

    def _schedule_impulses_update(self):
        async def _update(now):
            await self._update_impulses_per_minute()
        async_track_time_change(self.hass, _update, second=5)

    async def _send_export_value(self):
        if not self.export_enabled or not self._export_client:
            return
        try:
            self._export_client.publish(self.export_topic_day, str(self._total_value))
            _LOGGER.debug("Отправлены экспортные показания для %s", self.name)
        except Exception as e:
            _LOGGER.error("Ошибка отправки экспортных показаний для %s: %s", self.name, e)

    def _schedule_export_updates(self):
        async def _send_export(now):
            await self._send_export_value()
        async_track_time_change(self.hass, _send_export, minute=range(0, 60), second=0)
        _LOGGER.debug("Запланирована отправка экспортных показаний для %s", self.name)

    async def async_set_total_value(self, value: float):
        self._total_value = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены показания для %s: %.1f %s", self.name, value, self.unit)

    async def async_set_month_start_value(self, value: float):
        self._month_start_value = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлено начало месяца для %s: %.1f %s", self.name, value, self.unit)

    async def async_set_month_start_day(self, day: int) -> None:
        """Установить день начала месяца."""
        if day < 1 or day > 31:
            raise ValueError("День должен быть в диапазоне 1-31")
        self.month_start_day = day
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлен день начала месяца для %s: %d", self.name, day)

    async def async_set_partial(self, value: int):
        self._partial = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены накопленные импульсы для %s: %d", self.name, value)

    @property
    def total_value(self) -> float:
        return self._total_value

    @property
    def month_value(self) -> float:
        """Потребление с дня начала месяца."""
        now = dt_util.now()
        target_day = self.month_start_day

        if now.day >= target_day:
            start_date = now.replace(day=target_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            if now.month == 1:
                start_date = now.replace(year=now.year - 1, month=12, day=target_day,
                                         hour=0, minute=0, second=0, microsecond=0)
            else:
                start_date = now.replace(month=now.month - 1, day=target_day,
                                         hour=0, minute=0, second=0, microsecond=0)

        consumption = self._total_value - self._month_start_value
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def current_raw_impulses(self) -> int:
        return self._last_impulses_per_minute

    @property
    def partial(self) -> int:
        return self._partial