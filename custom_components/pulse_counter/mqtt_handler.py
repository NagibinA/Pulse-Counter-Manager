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
    METER_TYPE_ELECTRICITY,
    CONF_NAME,
    CONF_COUNTER_ID,
    CONF_METER_TYPE,
    CONF_UNIT,
    CONF_MQTT_TOPIC_DAY,
    CONF_MQTT_TOPIC_NIGHT,
    CONF_MQTT_TOPIC_MAIN,
    CONF_MQTT_TOPIC_COMMAND,
    CONF_MQTT_TOPIC_AVAILABLE,
    CONF_DAY_TARIFF,
    CONF_NIGHT_TARIFF,
    CONF_TARIFF,
    CONF_NIGHT_START,
    CONF_NIGHT_END,
    CONF_PULSES_PER_UNIT,
    CONF_LEGACY_MQTT,
    CONF_LEGACY_TOPIC,
    CONF_LEGACY_TOPIC_DAY,
    CONF_LEGACY_TOPIC_NIGHT,
    CONF_INITIAL_VALUE,
    CONF_INITIAL_DAY_KWH,
    CONF_INITIAL_NIGHT_KWH,
    CONF_MONTH_START_VALUE,
    CONF_MONTH_START_DAY,
    CONF_MONTH_START_NIGHT,
)

from .storage import PulseCounterStorage

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
        
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        
        self.topic_available = config.get(CONF_MQTT_TOPIC_AVAILABLE, "")
        
        self.legacy_mqtt = config.get(CONF_LEGACY_MQTT, False)
        
        # Состояние счетчика
        self._partial = 0
        self._total_value = config.get(CONF_INITIAL_VALUE, 0)
        self._month_start_value = config.get(CONF_MONTH_START_VALUE, 0)
        self._last_reset_date = None
        self._last_month_value = 0
        self._last_month_date = None
        
        # Для сенсора импульсов
        self._last_impulses_raw = 0
        self._last_impulses_per_minute = 0
        
        # Для накопления импульсов во время перезагрузки
        self._pending_impulses = 0
        
        # Управление опросом
        self._polling_enabled = True
        self._subscribed = False
        
        # Состояние ESP
        self.esp_available = False
        
        # MQTT клиент
        self._client = None
        self._is_shutdown = False
        self._listeners = []
        
        # Хранилище
        self.storage = PulseCounterStorage(hass, self.counter_id)
        
        _LOGGER.info("Инициализирован обработчик для счетчика %s (тип: %s)", self.name, self.meter_type)

    def async_add_listener(self, update_callback):
        self._listeners.append(update_callback)
        return lambda: self._listeners.remove(update_callback)

    async def _notify_listeners(self):
        for listener in self._listeners:
            listener()

    async def _load_state(self):
        """Загрузить состояние из хранилища."""
        _LOGGER.warning("=== _load_state ВЫЗВАН ДЛЯ %s ===", self.name)
        
        data = await self.storage.async_load()
        
        if data:
            _LOGGER.warning("=== ДАННЫЕ ИЗ STORAGE НАЙДЕНЫ ДЛЯ %s ===", self.name)
            _LOGGER.warning("partial в storage: %s", data.get("partial"))
            _LOGGER.warning("total_value в storage: %s", data.get("total_value"))
            
            self._partial = data.get("partial", 0)
            self._total_value = data.get("total_value", self._total_value)
            self._month_start_value = data.get("month_start_value", self._month_start_value)
            self._last_reset_date = data.get("last_reset_date")
            if self._last_reset_date and isinstance(self._last_reset_date, str):
                self._last_reset_date = datetime.fromisoformat(self._last_reset_date).date()
            self._last_month_value = data.get("last_month_value", 0)
            self._last_month_date = data.get("last_month_date")
            if self._last_month_date and isinstance(self._last_month_date, str):
                self._last_month_date = datetime.fromisoformat(self._last_month_date).date()
            self._last_impulses_per_minute = data.get("last_impulses_per_minute", 0)
            
            _LOGGER.warning("=== ПОСЛЕ ЗАГРУЗКИ ДЛЯ %s: partial=%d, total_value=%.1f ===", 
                           self.name, self._partial, self._total_value)
        else:
            _LOGGER.warning("=== STORAGE ПУСТ ДЛЯ %s, ИСПОЛЬЗУЮТСЯ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ ===", self.name)
            _LOGGER.warning("partial по умолчанию: %d", self._partial)
            _LOGGER.warning("total_value по умолчанию: %.1f", self._total_value)

    async def _save_state(self):
        """Сохранить состояние в хранилище."""
        data = {
            "partial": self._partial,
            "total_value": self._total_value,
            "month_start_value": self._month_start_value,
            "last_reset_date": self._last_reset_date.isoformat() if self._last_reset_date else None,
            "last_month_value": self._last_month_value,
            "last_month_date": self._last_month_date.isoformat() if self._last_month_date else None,
            "last_impulses_per_minute": self._last_impulses_per_minute,
            "last_update": dt_util.utcnow().isoformat(),
        }
        
        _LOGGER.warning("=== СОХРАНЕНИЕ В STORAGE ДЛЯ %s ===", self.name)
        _LOGGER.warning("Сохраняем partial: %d", self._partial)
        _LOGGER.warning("Сохраняем total_value: %.1f", self._total_value)
        
        await self.storage.async_save(data)
        _LOGGER.debug("Сохранено состояние для %s", self.name)

    async def async_initialize(self):
        """Инициализация подключения к MQTT."""
        _LOGGER.warning("=== async_initialize НАЧАЛО ДЛЯ %s ===", self.name)
        
        # Загружаем сохраненное состояние
        await self._load_state()
        
        # Подключаемся к MQTT
        await self._connect_mqtt()
        
        # Ждем подписки на топики (максимум 5 секунд)
        timeout = 0
        while not self._subscribed and timeout < 50:
            await asyncio.sleep(0.1)
            timeout += 0.1
        
        # Обрабатываем накопленные во время перезагрузки импульсы
        if self._pending_impulses > 0:
            _LOGGER.warning("=== ОБРАБОТКА НАКОПЛЕННЫХ ИМПУЛЬСОВ: %d ===", self._pending_impulses)
            await self._process_impulses(self._pending_impulses)
            self._pending_impulses = 0
        
        # Запускаем фоновые задачи
        self._schedule_impulses_update()
        if self.legacy_mqtt:
            self._schedule_legacy_updates()
        
        _LOGGER.warning("=== async_initialize КОНЕЦ ДЛЯ %s ===", self.name)
        _LOGGER.info("Обработчик счетчика %s запущен", self.name)

    async def async_shutdown(self):
        """Корректное завершение работы."""
        self._is_shutdown = True
        self._polling_enabled = False
        await self._save_state()
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        await self.storage.async_close()
        _LOGGER.info("Обработчик счетчика %s остановлен", self.name)

    def async_stop_polling(self):
        """Остановка опроса ESP (при выключении HA)."""
        self._polling_enabled = False
        _LOGGER.info("Остановлен опрос ESP для %s", self.name)

    async def async_start_polling(self):
        """Возобновление опроса ESP (при запуске HA)."""
        self._polling_enabled = True
        # Отправляем команду сразу после запуска, если это электричество
        if hasattr(self, '_update_current_tariff'):
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
        """Подписка на топики - переопределяется в дочерних классах."""
        pass

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload
        
        if topic == self.topic_available:
            self.esp_available = (payload == "Включен")
            _LOGGER.info("Статус счетчика %s: %s", self.name, "доступен" if self.esp_available else "недоступен")
            return
        
        # Обработка импульсов для однотарифных счетчиков
        if hasattr(self, 'topic_main') and topic == self.topic_main:
            try:
                impulses = int(payload)
                self._last_impulses_raw = impulses
                if not self._is_shutdown and self._polling_enabled:
                    self.hass.loop.create_task(self._process_impulses(impulses))
                elif not self._polling_enabled:
                    self._pending_impulses += impulses
                    _LOGGER.debug("Импульсы добавлены в буфер: %d (всего в буфере: %d)", 
                                 impulses, self._pending_impulses)
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)

    async def _process_impulses(self, impulses: int):
        """Обработка импульсов - ВСЕГДА прибавляем."""
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
        """Обновление сенсора импульсов."""
        self._last_impulses_per_minute = self._last_impulses_raw
        self._last_impulses_raw = 0
        await self._save_state()
        await self._notify_listeners()

    def _schedule_impulses_update(self):
        async def _update(now):
            await self._update_impulses_per_minute()
        async_track_time_change(self.hass, _update, second=5)

    def _schedule_legacy_updates(self):
        async def _send_legacy(now):
            if self.legacy_mqtt and self._client and self._polling_enabled:
                await self._send_legacy_value()
        async_track_time_change(self.hass, _send_legacy, minute=range(0, 60), second=0)

    async def _send_legacy_value(self):
        """Отправка legacy значения - переопределяется в дочерних классах."""
        pass

    # Методы для корректировки
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

    async def async_set_partial(self, value: int):
        """Установить накопленные импульсы."""
        self._partial = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены накопленные импульсы для %s: %d", self.name, value)

    # Свойства
    @property
    def total_value(self) -> float:
        return self._total_value

    @property
    def month_value(self) -> float:
        consumption = self._total_value - self._month_start_value
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def current_raw_impulses(self) -> int:
        return self._last_impulses_per_minute

    @property
    def partial(self) -> int:
        return self._partial


class PulseCounterWaterMQTTHandler(BaseMQTTHandler):
    """Обработчик для счетчика воды."""

    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, config: dict):
        super().__init__(hass, broker, port, username, password, config)
        
        self.topic_main = config.get(CONF_MQTT_TOPIC_MAIN, "")
        self.tariff = config.get(CONF_TARIFF, 0)
        self.legacy_topic = config.get(CONF_LEGACY_TOPIC, "HomeAssistant/meter")
        
        _LOGGER.info("Топик для %s: %s", self.name, self.topic_main)

    def _subscribe_topics(self):
        if self.topic_main:
            self._client.subscribe(self.topic_main)

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload
        
        if topic == self.topic_available:
            self.esp_available = (payload == "Включен")
            _LOGGER.info("Статус счетчика %s: %s", self.name, "доступен" if self.esp_available else "недоступен")
            return
        
        if topic == self.topic_main:
            try:
                impulses = int(payload)
                self._last_impulses_raw = impulses
                if not self._is_shutdown and self._polling_enabled:
                    self.hass.loop.create_task(self._process_impulses(impulses))
                elif not self._polling_enabled:
                    self._pending_impulses += impulses
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)

    async def _send_legacy_value(self):
        if self._client:
            self._client.publish(self.legacy_topic, str(self._total_value))

    @property
    def month_cost(self) -> float:
        return round(self.month_value * self.tariff, 2)


# Для газа и тепла - пока используем тот же класс
PulseCounterGasMQTTHandler = PulseCounterWaterMQTTHandler
PulseCounterHeatMQTTHandler = PulseCounterWaterMQTTHandler


class PulseCounterMQTTHandler(BaseMQTTHandler):
    """Обработчик для двухтарифного счетчика электроэнергии."""

    def __init__(self, hass: HomeAssistant, broker: str, port: int, username: str, password: str, config: dict):
        super().__init__(hass, broker, port, username, password, config)
        
        self.topic_day = config[CONF_MQTT_TOPIC_DAY]
        self.topic_night = config[CONF_MQTT_TOPIC_NIGHT]
        self.topic_command = config[CONF_MQTT_TOPIC_COMMAND]
        
        self.day_tariff = config[CONF_DAY_TARIFF]
        self.night_tariff = config[CONF_NIGHT_TARIFF]
        self.night_start = config[CONF_NIGHT_START]
        self.night_end = config[CONF_NIGHT_END]
        
        # Состояние счетчика (день/ночь)
        self._day_partial = 0
        self._night_partial = 0
        self._day_total_kwh = config.get(CONF_INITIAL_DAY_KWH, 0)
        self._night_total_kwh = config.get(CONF_INITIAL_NIGHT_KWH, 0)
        
        # Показания на начало месяца
        self._month_start_day = config.get(CONF_MONTH_START_DAY, self._day_total_kwh)
        self._month_start_night = config.get(CONF_MONTH_START_NIGHT, self._night_total_kwh)
        self._last_reset_date = None
        
        # История
        self._last_month_day = 0
        self._last_month_night = 0
        self._last_month_total = 0
        
        # Текущий тариф
        self.current_tariff = STATE_DAY
        
        # Legacy топики
        self.legacy_topic_day = config.get(CONF_LEGACY_TOPIC_DAY, "HomeAssistant/daily")
        self.legacy_topic_night = config.get(CONF_LEGACY_TOPIC_NIGHT, "HomeAssistant/nighttime")
        
        # Для накопления во время перезагрузки
        self._pending_day_impulses = 0
        self._pending_night_impulses = 0
        
        _LOGGER.info("Топики дня/ночи для %s: %s, %s", self.name, self.topic_day, self.topic_night)

    async def _load_state(self):
        """Загрузить состояние из хранилища."""
        _LOGGER.warning("=== _load_state ВЫЗВАН ДЛЯ ЭЛЕКТРИЧЕСТВА %s ===", self.name)
        
        data = await self.storage.async_load()
        
        if data:
            _LOGGER.warning("=== ДАННЫЕ ИЗ STORAGE НАЙДЕНЫ ДЛЯ %s ===", self.name)
            _LOGGER.warning("day_partial в storage: %s", data.get("day_partial"))
            _LOGGER.warning("night_partial в storage: %s", data.get("night_partial"))
            _LOGGER.warning("day_total_kwh в storage: %s", data.get("day_total_kwh"))
            _LOGGER.warning("night_total_kwh в storage: %s", data.get("night_total_kwh"))
            
            self._day_partial = data.get("day_partial", 0)
            self._night_partial = data.get("night_partial", 0)
            self._day_total_kwh = data.get("day_total_kwh", self._day_total_kwh)
            self._night_total_kwh = data.get("night_total_kwh", self._night_total_kwh)
            self._month_start_day = data.get("month_start_day", self._month_start_day)
            self._month_start_night = data.get("month_start_night", self._month_start_night)
            self._last_reset_date = data.get("last_reset_date")
            if self._last_reset_date and isinstance(self._last_reset_date, str):
                self._last_reset_date = datetime.fromisoformat(self._last_reset_date).date()
            self._last_month_day = data.get("last_month_day", 0)
            self._last_month_night = data.get("last_month_night", 0)
            self._last_month_total = data.get("last_month_total", 0)
            self._last_month_date = data.get("last_month_date")
            if self._last_month_date and isinstance(self._last_month_date, str):
                self._last_month_date = datetime.fromisoformat(self._last_month_date).date()
            self._last_impulses_per_minute = data.get("last_impulses_per_minute", 0)
            
            _LOGGER.warning("=== ПОСЛЕ ЗАГРУЗКИ ДЛЯ %s: _day_partial=%d, _night_partial=%d, _day_total_kwh=%.1f, _night_total_kwh=%.1f ===", 
                           self.name, self._day_partial, self._night_partial, self._day_total_kwh, self._night_total_kwh)
        else:
            _LOGGER.warning("=== STORAGE ПУСТ ДЛЯ %s, ИСПОЛЬЗУЮТСЯ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ ===", self.name)
            _LOGGER.warning("_day_partial по умолчанию: %d", self._day_partial)
            _LOGGER.warning("_night_partial по умолчанию: %d", self._night_partial)

    async def _save_state(self):
        """Сохранить состояние в хранилище."""
        data = {
            "day_partial": self._day_partial,
            "night_partial": self._night_partial,
            "day_total_kwh": self._day_total_kwh,
            "night_total_kwh": self._night_total_kwh,
            "month_start_day": self._month_start_day,
            "month_start_night": self._month_start_night,
            "last_reset_date": self._last_reset_date.isoformat() if self._last_reset_date else None,
            "last_month_day": self._last_month_day,
            "last_month_night": self._last_month_night,
            "last_month_total": self._last_month_total,
            "last_month_date": self._last_month_date.isoformat() if self._last_month_date else None,
            "last_impulses_per_minute": self._last_impulses_per_minute,
            "last_update": dt_util.utcnow().isoformat(),
        }
        
        _LOGGER.warning("=== СОХРАНЕНИЕ В STORAGE ДЛЯ %s ===", self.name)
        _LOGGER.warning("Сохраняем day_partial: %d", self._day_partial)
        _LOGGER.warning("Сохраняем night_partial: %d", self._night_partial)
        _LOGGER.warning("Сохраняем day_total_kwh: %.1f", self._day_total_kwh)
        _LOGGER.warning("Сохраняем night_total_kwh: %.1f", self._night_total_kwh)
        
        await self.storage.async_save(data)
        _LOGGER.debug("Сохранено состояние для %s", self.name)

    def _subscribe_topics(self):
        self._client.subscribe(self.topic_day)
        self._client.subscribe(self.topic_night)
        self._client.subscribe(self.topic_command)

    async def async_initialize(self):
        await super().async_initialize()
        await self._update_current_tariff()
        self._schedule_tariff_switching()

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode() if isinstance(msg.payload, bytes) else msg.payload
        
        if topic == self.topic_available:
            self.esp_available = (payload == "Включен")
            _LOGGER.info("Статус счетчика %s: %s", self.name, "доступен" if self.esp_available else "недоступен")
            return
        
        if topic == self.topic_day:
            try:
                impulses = int(payload)
                self._last_impulses_raw = impulses
                if not self._is_shutdown and self._polling_enabled:
                    self.hass.loop.create_task(self._process_day_impulses(impulses))
                elif not self._polling_enabled:
                    self._pending_day_impulses += impulses
                    _LOGGER.debug("Дневные импульсы добавлены в буфер: %d (всего: %d)", 
                                 impulses, self._pending_day_impulses)
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)
        elif topic == self.topic_night:
            try:
                impulses = int(payload)
                self._last_impulses_raw = impulses
                if not self._is_shutdown and self._polling_enabled:
                    self.hass.loop.create_task(self._process_night_impulses(impulses))
                elif not self._polling_enabled:
                    self._pending_night_impulses += impulses
                    _LOGGER.debug("Ночные импульсы добавлены в буфер: %d (всего: %d)", 
                                 impulses, self._pending_night_impulses)
            except ValueError:
                _LOGGER.error("Ошибка преобразования: %s", payload)

    async def _process_day_impulses(self, impulses: int):
        """Обработка дневных импульсов - ВСЕГДА прибавляем."""
        self._day_partial += impulses
        if self._day_partial >= self.pulses_per_unit:
            units_added = self._day_partial // self.pulses_per_unit
            self._day_total_kwh += units_added
            self._day_partial = self._day_partial % self.pulses_per_unit
            _LOGGER.debug("День: +%d кВт·ч, всего=%.1f, остаток=%d", 
                         units_added, self._day_total_kwh, self._day_partial)
        else:
            _LOGGER.debug("День: накоплено импульсов=%d", self._day_partial)
        
        await self._save_state()
        await self._notify_listeners()

    async def _process_night_impulses(self, impulses: int):
        """Обработка ночных импульсов - ВСЕГДА прибавляем."""
        self._night_partial += impulses
        if self._night_partial >= self.pulses_per_unit:
            units_added = self._night_partial // self.pulses_per_unit
            self._night_total_kwh += units_added
            self._night_partial = self._night_partial % self.pulses_per_unit
            _LOGGER.debug("Ночь: +%d кВт·ч, всего=%.1f, остаток=%d", 
                         units_added, self._night_total_kwh, self._night_partial)
        else:
            _LOGGER.debug("Ночь: накоплено импульсов=%d", self._night_partial)
        
        await self._save_state()
        await self._notify_listeners()

    async def _update_current_tariff(self):
        if not self._polling_enabled:
            _LOGGER.debug("Опрос остановлен, команда не отправлена для %s", self.name)
            return
        
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
        
        # Отправляем команду каждую минуту
        await self._send_command(self.current_tariff)

    async def _send_command(self, command: str):
        if not self.esp_available:
            return
        if self._client:
            self._client.publish(self.topic_command, command)
            _LOGGER.debug("Отправлена команда: %s для %s", command, self.name)

    def _schedule_tariff_switching(self):
        async def _check_tariff(now):
            await self._update_current_tariff()
        async_track_time_change(self.hass, _check_tariff, second=0)

    async def _send_legacy_value(self):
        if self._client:
            self._client.publish(self.legacy_topic_day, str(self._day_total_kwh))
            self._client.publish(self.legacy_topic_night, str(self._night_total_kwh))

    # Методы для корректировки
    async def async_set_day_kwh(self, value: float):
        self._day_total_kwh = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены дневные показания для %s: %.1f кВт·ч", self.name, value)

    async def async_set_night_kwh(self, value: float):
        self._night_total_kwh = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены ночные показания для %s: %.1f кВт·ч", self.name, value)

    async def async_set_month_start_day(self, value: float):
        self._month_start_day = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлено начало месяца (день) для %s: %.1f кВт·ч", self.name, value)

    async def async_set_month_start_night(self, value: float):
        self._month_start_night = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлено начало месяца (ночь) для %s: %.1f кВт·ч", self.name, value)

    async def async_set_day_partial(self, value: int):
        """Установить дневные накопленные импульсы."""
        _LOGGER.warning("=== async_set_day_partial ВЫЗВАН: value=%d ===", value)
        self._day_partial = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены дневные накопленные импульсы для %s: %d", self.name, value)

    async def async_set_night_partial(self, value: int):
        """Установить ночные накопленные импульсы."""
        _LOGGER.warning("=== async_set_night_partial ВЫЗВАН: value=%d ===", value)
        self._night_partial = value
        await self._save_state()
        await self._notify_listeners()
        _LOGGER.info("Установлены ночные накопленные импульсы для %s: %d", self.name, value)

    async def async_clear_pending(self):
        """Очистить буфер накопленных во время перезагрузки импульсов."""
        if self._pending_day_impulses > 0 or self._pending_night_impulses > 0:
            _LOGGER.info("Очистка буфера для %s: день=%d, ночь=%d", 
                        self.name, self._pending_day_impulses, self._pending_night_impulses)
            self._pending_day_impulses = 0
            self._pending_night_impulses = 0

    # Свойства
    @property
    def total_value(self) -> float:
        return self._day_total_kwh + self._night_total_kwh

    @property
    def day_kwh(self) -> float:
        return self._day_total_kwh

    @property
    def night_kwh(self) -> float:
        return self._night_total_kwh

    @property
    def day_partial(self) -> int:
        """Текущие накопленные дневные импульсы."""
        _LOGGER.debug("day_partial запрошен: %d", self._day_partial)
        return self._day_partial

    @property
    def night_partial(self) -> int:
        """Текущие накопленные ночные импульсы."""
        _LOGGER.debug("night_partial запрошен: %d", self._night_partial)
        return self._night_partial

    @property
    def month_value(self) -> float:
        return self.month_day_kwh + self.month_night_kwh

    @property
    def month_day_kwh(self) -> float:
        consumption = self._day_total_kwh - self._month_start_day
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def month_night_kwh(self) -> float:
        consumption = self._night_total_kwh - self._month_start_night
        return round(consumption, 2) if consumption > 0 else 0

    @property
    def month_day_cost(self) -> float:
        return round(self.month_day_kwh * self.day_tariff, 2)

    @property
    def month_night_cost(self) -> float:
        return round(self.month_night_kwh * self.night_tariff, 2)

    @property
    def month_cost(self) -> float:
        return round(self.month_day_cost + self.month_night_cost, 2)