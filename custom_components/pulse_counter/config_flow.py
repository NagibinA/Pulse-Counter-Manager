"""Config Flow для Pulse Counter Manager."""

import logging
import asyncio
import socket
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    VERSION,
    METER_TYPES,
    METER_DEFAULTS,
    METER_TYPE_ELECTRICITY,
    TARIFF_INFO_URL,
    EXPORT_BROKER_MAIN,
    EXPORT_BROKER_CUSTOM,
    CONF_NAME,
    CONF_METER_TYPE,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTERS,
    CONF_COUNTER_ID,
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
    CONF_UNIT,
    CONF_EXPORT_ENABLED,
    CONF_EXPORT_BROKER_MODE,
    CONF_EXPORT_BROKER,
    CONF_EXPORT_PORT,
    CONF_EXPORT_USERNAME,
    CONF_EXPORT_PASSWORD,
    CONF_EXPORT_TOPIC_DAY,
    CONF_EXPORT_TOPIC_NIGHT,
    CONF_INITIAL_VALUE,
    CONF_INITIAL_DAY_KWH,
    CONF_INITIAL_NIGHT_KWH,
    CONF_MONTH_START_VALUE,
    CONF_MONTH_START_DAY,
    CONF_MONTH_START_NIGHT,
    DEFAULT_DAY_TARIFF,
    DEFAULT_NIGHT_TARIFF,
    DEFAULT_NIGHT_START,
    DEFAULT_NIGHT_END,
    DEFAULT_TARIFF,
    DEFAULT_PULSES_PER_UNIT,
    DEFAULT_MQTT_TOPIC_DAY,
    DEFAULT_MQTT_TOPIC_NIGHT,
    DEFAULT_MQTT_TOPIC_MAIN,
    DEFAULT_MQTT_TOPIC_COMMAND,
    DEFAULT_MQTT_TOPIC_AVAILABLE,
    DEFAULT_EXPORT_TOPIC_DAY,
    DEFAULT_EXPORT_TOPIC_NIGHT,
    DEFAULT_EXPORT_BROKER,
    DEFAULT_EXPORT_PORT,
    DEFAULT_EXPORT_BROKER_MODE,
)

from .storage import PulseCounterStorage

_LOGGER = logging.getLogger(__name__)

MQTT_SCHEMA = vol.Schema({
    vol.Required(CONF_MQTT_BROKER, default="192.168.1.11"): str,
    vol.Required(CONF_MQTT_PORT, default=1883): int,
    vol.Optional(CONF_MQTT_USERNAME): str,
    vol.Optional(CONF_MQTT_PASSWORD): str,
})


async def test_mqtt_connection(broker, port, username=None, password=None):
    """Проверка подключения к MQTT брокеру."""
    try:
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        await loop.run_in_executor(None, sock.connect, (broker, port))
        sock.close()
        return True
    except Exception as e:
        _LOGGER.error("Ошибка подключения к MQTT брокеру %s:%s - %s", broker, port, e)
        return False


class PulseCounterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow для Pulse Counter Manager."""
    
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Первый шаг - настройка MQTT брокера."""
        errors = {}
        
        if user_input is not None:
            _LOGGER.info("Проверка подключения к MQTT брокеру %s:%s", 
                        user_input[CONF_MQTT_BROKER], user_input[CONF_MQTT_PORT])
            
            connected = await test_mqtt_connection(
                user_input[CONF_MQTT_BROKER],
                user_input[CONF_MQTT_PORT],
                user_input.get(CONF_MQTT_USERNAME),
                user_input.get(CONF_MQTT_PASSWORD)
            )
            
            if connected:
                broker = user_input[CONF_MQTT_BROKER]
                title = f"Pulse Counter ({broker})"
                
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_MQTT_BROKER: broker,
                        CONF_MQTT_PORT: user_input[CONF_MQTT_PORT],
                        CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                        CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
                        CONF_COUNTERS: {},
                    }
                )
            else:
                errors["base"] = "cannot_connect"
        
        return self.async_show_form(
            step_id="user",
            data_schema=MQTT_SCHEMA,
            errors=errors
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Настройки интеграции - добавление счетчиков."""
    
    def __init__(self, config_entry):
        self._entry = config_entry
        self._meter_type = None
        self._selected_counter_id = None
    
    async def async_step_init(self, user_input=None):
        """Главное меню управления счетчиками."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add_counter":
                return await self.async_step_select_type()
            elif action == "edit_counter":
                return await self.async_step_edit_counter()
            else:
                return self.async_create_entry(title="", data={})
        
        actions = {
            "add_counter": "Добавить счетчик",
            "edit_counter": "Редактировать счетчик",
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)})
        )
    
    async def async_step_select_type(self, user_input=None):
        """Выбор типа счетчика."""
        if user_input is not None:
            self._meter_type = user_input[CONF_METER_TYPE]
            return await self.async_step_add_counter()
        
        return self.async_show_form(
            step_id="select_type",
            data_schema=vol.Schema({
                vol.Required(CONF_METER_TYPE): vol.In(METER_TYPES)
            })
        )
    
    async def async_step_add_counter(self, user_input=None):
        """Добавление счетчика в зависимости от типа."""
        errors = {}
        defaults = METER_DEFAULTS[self._meter_type]
        counters = self._entry.data.get(CONF_COUNTERS, {})
        used_ids = list(counters.keys())
        
        if user_input is not None:
            try:
                counter_name = user_input[CONF_NAME]
                counter_id = f"counter_{counter_name.lower().replace(' ', '_')}"
                
                if counter_id in used_ids:
                    errors[CONF_NAME] = "name_exists"
                else:
                    # Общие поля для всех типов
                    new_counter = {
                        CONF_COUNTER_ID: counter_id,
                        CONF_NAME: counter_name,
                        CONF_METER_TYPE: self._meter_type,
                        CONF_UNIT: defaults["unit"],
                        CONF_PULSES_PER_UNIT: user_input.get(CONF_PULSES_PER_UNIT, defaults["pulses_per_unit"]),
                        CONF_INITIAL_VALUE: user_input.get(CONF_INITIAL_VALUE, 0),
                        CONF_MONTH_START_VALUE: user_input.get(CONF_MONTH_START_VALUE, 0),
                        CONF_EXPORT_ENABLED: user_input.get(CONF_EXPORT_ENABLED, False),
                        CONF_EXPORT_BROKER_MODE: user_input.get(CONF_EXPORT_BROKER_MODE, DEFAULT_EXPORT_BROKER_MODE),
                        CONF_EXPORT_BROKER: user_input.get(CONF_EXPORT_BROKER, DEFAULT_EXPORT_BROKER),
                        CONF_EXPORT_PORT: user_input.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT),
                        CONF_EXPORT_USERNAME: user_input.get(CONF_EXPORT_USERNAME, ""),
                        CONF_EXPORT_PASSWORD: user_input.get(CONF_EXPORT_PASSWORD, ""),
                    }
                    
                    # Для электроэнергии (двухтарифный)
                    if self._meter_type == METER_TYPE_ELECTRICITY:
                        new_counter.update({
                            CONF_MQTT_TOPIC_DAY: user_input[CONF_MQTT_TOPIC_DAY],
                            CONF_MQTT_TOPIC_NIGHT: user_input[CONF_MQTT_TOPIC_NIGHT],
                            CONF_MQTT_TOPIC_COMMAND: user_input[CONF_MQTT_TOPIC_COMMAND],
                            CONF_MQTT_TOPIC_AVAILABLE: user_input[CONF_MQTT_TOPIC_AVAILABLE],
                            CONF_DAY_TARIFF: user_input[CONF_DAY_TARIFF],
                            CONF_NIGHT_TARIFF: user_input[CONF_NIGHT_TARIFF],
                            CONF_NIGHT_START: user_input[CONF_NIGHT_START],
                            CONF_NIGHT_END: user_input[CONF_NIGHT_END],
                            CONF_INITIAL_DAY_KWH: user_input[CONF_INITIAL_DAY_KWH],
                            CONF_INITIAL_NIGHT_KWH: user_input[CONF_INITIAL_NIGHT_KWH],
                            CONF_MONTH_START_DAY: user_input[CONF_MONTH_START_DAY],
                            CONF_MONTH_START_NIGHT: user_input[CONF_MONTH_START_NIGHT],
                            CONF_EXPORT_TOPIC_DAY: user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY),
                            CONF_EXPORT_TOPIC_NIGHT: user_input.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT),
                        })
                    else:
                        # Для воды, газа, тепла (однотарифный)
                        new_counter.update({
                            CONF_MQTT_TOPIC_MAIN: user_input[CONF_MQTT_TOPIC_MAIN],
                            CONF_MQTT_TOPIC_AVAILABLE: user_input.get(CONF_MQTT_TOPIC_AVAILABLE, defaults["topics"]["available"]),
                            CONF_TARIFF: user_input.get(CONF_TARIFF, DEFAULT_TARIFF),
                            CONF_EXPORT_TOPIC_DAY: user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY),
                            CONF_EXPORT_TOPIC_NIGHT: user_input.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT),
                        })
                    
                    # КЛЮЧОМ СЛОВАРЯ ДОЛЖЕН БЫТЬ counter_id
                    new_counters = dict(counters)
                    new_counters[counter_id] = new_counter
                    
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={**self._entry.data, CONF_COUNTERS: new_counters}
                    )
                    
                    if DOMAIN not in self.hass.data:
                        self.hass.data[DOMAIN] = {}
                    self.hass.data[DOMAIN][CONF_COUNTERS] = new_counters
                    
                    async_dispatcher_send(self.hass, f"{DOMAIN}_add_counter", new_counter)
                    
                    return self.async_create_entry(title="", data={})
                    
            except Exception as e:
                _LOGGER.exception("Ошибка при добавлении счетчика: %s", e)
                errors["base"] = "invalid_data"
        
        # Форма в зависимости от типа
        if self._meter_type == METER_TYPE_ELECTRICITY:
            schema = vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_MQTT_TOPIC_DAY, default=DEFAULT_MQTT_TOPIC_DAY): str,
                vol.Required(CONF_MQTT_TOPIC_NIGHT, default=DEFAULT_MQTT_TOPIC_NIGHT): str,
                vol.Required(CONF_MQTT_TOPIC_COMMAND, default=DEFAULT_MQTT_TOPIC_COMMAND): str,
                vol.Required(CONF_MQTT_TOPIC_AVAILABLE, default=DEFAULT_MQTT_TOPIC_AVAILABLE): str,
                vol.Required(CONF_DAY_TARIFF, default=DEFAULT_DAY_TARIFF): vol.Coerce(float),
                vol.Required(CONF_NIGHT_TARIFF, default=DEFAULT_NIGHT_TARIFF): vol.Coerce(float),
                vol.Required(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): str,
                vol.Required(CONF_NIGHT_END, default=DEFAULT_NIGHT_END): str,
                vol.Required(CONF_PULSES_PER_UNIT, default=defaults["pulses_per_unit"]): int,
                vol.Required(CONF_INITIAL_DAY_KWH, default=0): vol.Coerce(float),
                vol.Required(CONF_INITIAL_NIGHT_KWH, default=0): vol.Coerce(float),
                vol.Required(CONF_MONTH_START_DAY, default=0): vol.Coerce(float),
                vol.Required(CONF_MONTH_START_NIGHT, default=0): vol.Coerce(float),
                vol.Optional(CONF_EXPORT_ENABLED, default=False): bool,
                vol.Optional(CONF_EXPORT_BROKER_MODE, default=DEFAULT_EXPORT_BROKER_MODE): vol.In({
                    EXPORT_BROKER_MAIN: "Основной брокер",
                    EXPORT_BROKER_CUSTOM: "Отдельный брокер",
                }),
                vol.Optional(CONF_EXPORT_BROKER, default=DEFAULT_EXPORT_BROKER): str,
                vol.Optional(CONF_EXPORT_PORT, default=DEFAULT_EXPORT_PORT): int,
                vol.Optional(CONF_EXPORT_USERNAME, default=""): str,
                vol.Optional(CONF_EXPORT_PASSWORD, default=""): str,
                vol.Optional(CONF_EXPORT_TOPIC_DAY, default=DEFAULT_EXPORT_TOPIC_DAY): str,
                vol.Optional(CONF_EXPORT_TOPIC_NIGHT, default=DEFAULT_EXPORT_TOPIC_NIGHT): str,
            })
        else:
            schema = vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_MQTT_TOPIC_MAIN, default=defaults["topics"]["main"]): str,
                vol.Optional(CONF_MQTT_TOPIC_AVAILABLE, default=defaults["topics"]["available"]): str,
                vol.Required(CONF_PULSES_PER_UNIT, default=defaults["pulses_per_unit"]): int,
                vol.Required(CONF_INITIAL_VALUE, default=0): vol.Coerce(float),
                vol.Required(CONF_MONTH_START_VALUE, default=0): vol.Coerce(float),
                vol.Optional(CONF_TARIFF, default=DEFAULT_TARIFF): vol.Coerce(float),
                vol.Optional(CONF_EXPORT_ENABLED, default=False): bool,
                vol.Optional(CONF_EXPORT_BROKER_MODE, default=DEFAULT_EXPORT_BROKER_MODE): vol.In({
                    EXPORT_BROKER_MAIN: "Основной брокер",
                    EXPORT_BROKER_CUSTOM: "Отдельный брокер",
                }),
                vol.Optional(CONF_EXPORT_BROKER, default=DEFAULT_EXPORT_BROKER): str,
                vol.Optional(CONF_EXPORT_PORT, default=DEFAULT_EXPORT_PORT): int,
                vol.Optional(CONF_EXPORT_USERNAME, default=""): str,
                vol.Optional(CONF_EXPORT_PASSWORD, default=""): str,
                vol.Optional(CONF_EXPORT_TOPIC_DAY, default=DEFAULT_EXPORT_TOPIC_DAY): str,
            })
        
        return self.async_show_form(
            step_id="add_counter",
            data_schema=schema,
            errors=errors
        )
    
    async def async_step_edit_counter(self, user_input=None):
        """Выбор счетчика для редактирования."""
        counters = self._entry.data.get(CONF_COUNTERS, {})
        
        if not counters:
            return self.async_abort(reason="no_counters")
        
        # Создаем словарь для выбора: ключ = counter_id, значение = название
        counter_options = {}
        for cid, cconfig in counters.items():
            counter_options[cid] = cconfig[CONF_NAME]
        
        if user_input is not None:
            selected_id = user_input["counter_id"]
            self._selected_counter_id = selected_id
            counter_name = counters[selected_id][CONF_NAME]
            _LOGGER.debug("Выбран счетчик: ID=%s, ИМЯ=%s", selected_id, counter_name)
            return await self.async_step_edit_choice()
        
        return self.async_show_form(
            step_id="edit_counter",
            data_schema=vol.Schema({vol.Required("counter_id"): vol.In(counter_options)})
        )
    
    async def async_step_edit_choice(self, user_input=None):
        """Действия с выбранным счетчиком."""
        actions = {
            "edit_current": "Изменить текущие показания",
            "edit_month_start": "Изменить показания на начало месяца",
            "edit_accumulated": "Изменить накопленные импульсы",
            "edit_tariffs": "Изменить тарифы",
            "edit_pulses": "Изменить коэффициент импульсов",
            "edit_export": "Настроить экспорт показаний",
            "edit_topics": "Изменить MQTT топики",
            "delete": "Удалить счетчик",
        }
        
        if user_input is not None:
            action = user_input["action"]
            if action == "edit_current":
                return await self.async_step_edit_current()
            elif action == "edit_month_start":
                return await self.async_step_edit_month_start()
            elif action == "edit_accumulated":
                return await self.async_step_edit_accumulated()
            elif action == "edit_tariffs":
                return await self.async_step_edit_tariffs()
            elif action == "edit_pulses":
                return await self.async_step_edit_pulses()
            elif action == "edit_export":
                return await self.async_step_edit_export()
            elif action == "edit_topics":
                return await self.async_step_edit_topics()
            elif action == "delete":
                return await self.async_step_delete_counter()
        
        return self.async_show_form(
            step_id="edit_choice",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)})
        )
    
    def _get_handler_by_counter_id(self):
        """Получить handler по counter_id."""
        handlers = self.hass.data[DOMAIN]["handlers"]
        return handlers.get(self._selected_counter_id)
    
    async def async_step_edit_current(self, user_input=None):
        """Изменение текущих показаний."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter[CONF_METER_TYPE]
        
        if user_input is not None:
            handler = self._get_handler_by_counter_id()
            if handler:
                if meter_type == METER_TYPE_ELECTRICITY:
                    await handler.async_set_day_kwh(user_input["day_kwh"])
                    await handler.async_set_night_kwh(user_input["night_kwh"])
                    _LOGGER.info("Изменены текущие показания для %s: день=%.1f, ночь=%.1f", 
                                counter[CONF_NAME], user_input["day_kwh"], user_input["night_kwh"])
                else:
                    await handler.async_set_total_value(user_input["total_value"])
                    _LOGGER.info("Изменены текущие показания для %s: %.1f", 
                                counter[CONF_NAME], user_input["total_value"])
            return self.async_create_entry(title="", data={})
        
        # Загружаем значения напрямую из storage
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("day_total_kwh", 0) if data else 0
            current_night = data.get("night_total_kwh", 0) if data else 0
            _LOGGER.info("Текущие показания для %s из storage: день=%.1f, ночь=%.1f", 
                        counter[CONF_NAME], current_day, current_night)
            
            schema = vol.Schema({
                vol.Required("day_kwh", default=current_day): vol.Coerce(float),
                vol.Required("night_kwh", default=current_night): vol.Coerce(float),
            })
        else:
            current_val = data.get("total_value", 0) if data else 0
            _LOGGER.info("Текущие показания для %s из storage: %.1f", counter[CONF_NAME], current_val)
            
            schema = vol.Schema({
                vol.Required("total_value", default=current_val): vol.Coerce(float),
            })
        
        return self.async_show_form(step_id="edit_current", data_schema=schema)
    
    async def async_step_edit_month_start(self, user_input=None):
        """Изменение показаний на начало месяца."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter[CONF_METER_TYPE]
        
        if user_input is not None:
            handler = self._get_handler_by_counter_id()
            if handler:
                if meter_type == METER_TYPE_ELECTRICITY:
                    await handler.async_set_month_start_day(user_input["month_start_day"])
                    await handler.async_set_month_start_night(user_input["month_start_night"])
                    _LOGGER.info("Изменено начало месяца для %s: день=%.1f, ночь=%.1f", 
                                counter[CONF_NAME], user_input["month_start_day"], user_input["month_start_night"])
                else:
                    await handler.async_set_month_start_value(user_input["month_start_value"])
                    _LOGGER.info("Изменено начало месяца для %s: %.1f", 
                                counter[CONF_NAME], user_input["month_start_value"])
            return self.async_create_entry(title="", data={})
        
        # Загружаем значения напрямую из storage
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("month_start_day", 0) if data else 0
            current_night = data.get("month_start_night", 0) if data else 0
            _LOGGER.info("Начало месяца для %s из storage: день=%.1f, ночь=%.1f", 
                        counter[CONF_NAME], current_day, current_night)
            
            schema = vol.Schema({
                vol.Required("month_start_day", default=current_day): vol.Coerce(float),
                vol.Required("month_start_night", default=current_night): vol.Coerce(float),
            })
        else:
            current_val = data.get("month_start_value", 0) if data else 0
            _LOGGER.info("Начало месяца для %s из storage: %.1f", counter[CONF_NAME], current_val)
            
            schema = vol.Schema({
                vol.Required("month_start_value", default=current_val): vol.Coerce(float),
            })
        
        return self.async_show_form(step_id="edit_month_start", data_schema=schema)
    
    async def async_step_edit_accumulated(self, user_input=None):
        """Изменение накопленных импульсов (остаток до 1000)."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        
        if user_input is not None:
            handler = self._get_handler_by_counter_id()
            if handler:
                if meter_type == METER_TYPE_ELECTRICITY:
                    day_val = user_input.get("day_impulses", 0)
                    night_val = user_input.get("night_impulses", 0)
                    
                    handler._day_partial = day_val
                    handler._night_partial = night_val
                    await handler._save_state()
                    await handler._notify_listeners()
                    _LOGGER.info("Изменены накопленные импульсы для %s: день=%d, ночь=%d", 
                                counter[CONF_NAME], day_val, night_val)
                else:
                    val = user_input.get("impulses", 0)
                    handler._partial = val
                    await handler._save_state()
                    await handler._notify_listeners()
                    _LOGGER.info("Изменены накопленные импульсы для %s: %d", 
                                counter[CONF_NAME], val)
            return self.async_create_entry(title="", data={})
        
        # Загружаем значения напрямую из storage
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("day_partial", 0) if data else 0
            current_night = data.get("night_partial", 0) if data else 0
            _LOGGER.info("Текущие накопленные импульсы для %s из storage: день=%d, ночь=%d", 
                        counter[CONF_NAME], current_day, current_night)
            
            schema = vol.Schema({
                vol.Required("day_impulses", default=current_day): int,
                vol.Required("night_impulses", default=current_night): int,
            })
        else:
            current_val = data.get("partial", 0) if data else 0
            _LOGGER.info("Текущие накопленные импульсы для %s из storage: %d", 
                        counter[CONF_NAME], current_val)
            
            schema = vol.Schema({
                vol.Required("impulses", default=current_val): int,
            })
        
        return self.async_show_form(
            step_id="edit_accumulated",
            data_schema=schema
        )
    
    async def async_step_edit_tariffs(self, user_input=None):
        """Изменение тарифов."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter[CONF_METER_TYPE]
        
        if user_input is not None:
            new_counter = dict(counter)
            if meter_type == METER_TYPE_ELECTRICITY:
                new_counter[CONF_DAY_TARIFF] = user_input[CONF_DAY_TARIFF]
                new_counter[CONF_NIGHT_TARIFF] = user_input[CONF_NIGHT_TARIFF]
                new_counter[CONF_NIGHT_START] = user_input[CONF_NIGHT_START]
                new_counter[CONF_NIGHT_END] = user_input[CONF_NIGHT_END]
            else:
                new_counter[CONF_TARIFF] = user_input[CONF_TARIFF]
            
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters[self._selected_counter_id] = new_counter
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            handler = self._get_handler_by_counter_id()
            if handler:
                if meter_type == METER_TYPE_ELECTRICITY:
                    handler.day_tariff = user_input[CONF_DAY_TARIFF]
                    handler.night_tariff = user_input[CONF_NIGHT_TARIFF]
                    handler.night_start = user_input[CONF_NIGHT_START]
                    handler.night_end = user_input[CONF_NIGHT_END]
                else:
                    handler.tariff = user_input[CONF_TARIFF]
            
            return self.async_create_entry(title="", data={})
        
        handler = self._get_handler_by_counter_id()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            schema = vol.Schema({
                vol.Required(CONF_DAY_TARIFF, default=handler.day_tariff if handler else DEFAULT_DAY_TARIFF): vol.Coerce(float),
                vol.Required(CONF_NIGHT_TARIFF, default=handler.night_tariff if handler else DEFAULT_NIGHT_TARIFF): vol.Coerce(float),
                vol.Required(CONF_NIGHT_START, default=handler.night_start if handler else DEFAULT_NIGHT_START): str,
                vol.Required(CONF_NIGHT_END, default=handler.night_end if handler else DEFAULT_NIGHT_END): str,
            })
        else:
            schema = vol.Schema({
                vol.Required(CONF_TARIFF, default=handler.tariff if handler else DEFAULT_TARIFF): vol.Coerce(float),
            })
        
        return self.async_show_form(
            step_id="edit_tariffs",
            data_schema=schema,
            description_placeholders={
                "tariff_info_url": TARIFF_INFO_URL
            }
        )
    
    async def async_step_edit_pulses(self, user_input=None):
        """Изменение коэффициента импульсов."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        unit = counter.get(CONF_UNIT, METER_DEFAULTS.get(meter_type, {}).get("unit", "ед"))
        
        if user_input is not None:
            new_counter = dict(counter)
            new_counter[CONF_PULSES_PER_UNIT] = user_input["pulses_per_unit"]
            
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters[self._selected_counter_id] = new_counter
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            handler = self._get_handler_by_counter_id()
            if handler:
                old_value = handler.pulses_per_unit
                handler.pulses_per_unit = user_input["pulses_per_unit"]
                _LOGGER.info("Изменен коэффициент импульсов для %s: %d -> %d импульсов на %s", 
                            counter[CONF_NAME], old_value, user_input["pulses_per_unit"], unit)
            
            return self.async_create_entry(title="", data={})
        
        handler = self._get_handler_by_counter_id()
        
        schema = vol.Schema({
            vol.Required("pulses_per_unit", default=handler.pulses_per_unit if handler else DEFAULT_PULSES_PER_UNIT): int,
        })
        
        return self.async_show_form(
            step_id="edit_pulses",
            data_schema=schema
        )
    
    async def async_step_edit_export(self, user_input=None):
        """Изменение настроек экспорта показаний."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        
        if user_input is not None:
            new_counter = dict(counter)
            new_counter[CONF_EXPORT_ENABLED] = user_input[CONF_EXPORT_ENABLED]
            new_counter[CONF_EXPORT_BROKER_MODE] = user_input[CONF_EXPORT_BROKER_MODE]
            
            if user_input[CONF_EXPORT_BROKER_MODE] == EXPORT_BROKER_CUSTOM:
                new_counter[CONF_EXPORT_BROKER] = user_input[CONF_EXPORT_BROKER]
                new_counter[CONF_EXPORT_PORT] = user_input[CONF_EXPORT_PORT]
                new_counter[CONF_EXPORT_USERNAME] = user_input.get(CONF_EXPORT_USERNAME, "")
                new_counter[CONF_EXPORT_PASSWORD] = user_input.get(CONF_EXPORT_PASSWORD, "")
            else:
                new_counter[CONF_EXPORT_BROKER] = ""
                new_counter[CONF_EXPORT_PORT] = DEFAULT_EXPORT_PORT
                new_counter[CONF_EXPORT_USERNAME] = ""
                new_counter[CONF_EXPORT_PASSWORD] = ""
            
            new_counter[CONF_EXPORT_TOPIC_DAY] = user_input[CONF_EXPORT_TOPIC_DAY]
            new_counter[CONF_EXPORT_TOPIC_NIGHT] = user_input[CONF_EXPORT_TOPIC_NIGHT]
            
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters[self._selected_counter_id] = new_counter
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            # Обновляем handler
            handler = self._get_handler_by_counter_id()
            if handler:
                handler.export_enabled = user_input[CONF_EXPORT_ENABLED]
                handler.export_broker_mode = user_input[CONF_EXPORT_BROKER_MODE]
                handler.export_topic_day = user_input[CONF_EXPORT_TOPIC_DAY]
                handler.export_topic_night = user_input[CONF_EXPORT_TOPIC_NIGHT]
                
                if user_input[CONF_EXPORT_BROKER_MODE] == EXPORT_BROKER_CUSTOM:
                    handler.export_broker = user_input[CONF_EXPORT_BROKER]
                    handler.export_port = user_input[CONF_EXPORT_PORT]
                    handler.export_username = user_input.get(CONF_EXPORT_USERNAME, "")
                    handler.export_password = user_input.get(CONF_EXPORT_PASSWORD, "")
                else:
                    handler.export_broker = None
                
                await handler._connect_export_mqtt()
            
            return self.async_create_entry(title="", data={})
        
        schema = vol.Schema({
            vol.Required(CONF_EXPORT_ENABLED, default=counter.get(CONF_EXPORT_ENABLED, False)): bool,
            vol.Required(CONF_EXPORT_BROKER_MODE, default=counter.get(CONF_EXPORT_BROKER_MODE, DEFAULT_EXPORT_BROKER_MODE)): vol.In({
                EXPORT_BROKER_MAIN: "Основной брокер",
                EXPORT_BROKER_CUSTOM: "Отдельный брокер",
            }),
            vol.Optional(CONF_EXPORT_BROKER, default=counter.get(CONF_EXPORT_BROKER, DEFAULT_EXPORT_BROKER)): str,
            vol.Optional(CONF_EXPORT_PORT, default=counter.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT)): int,
            vol.Optional(CONF_EXPORT_USERNAME, default=counter.get(CONF_EXPORT_USERNAME, "")): str,
            vol.Optional(CONF_EXPORT_PASSWORD, default=counter.get(CONF_EXPORT_PASSWORD, "")): str,
            vol.Optional(CONF_EXPORT_TOPIC_DAY, default=counter.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY)): str,
            vol.Optional(CONF_EXPORT_TOPIC_NIGHT, default=counter.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT)): str,
        })
        
        return self.async_show_form(
            step_id="edit_export",
            data_schema=schema,
            description_placeholders={
                "name": counter[CONF_NAME]
            }
        )
    
    async def async_step_edit_topics(self, user_input=None):
        """Изменение MQTT топиков."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter[CONF_METER_TYPE]
        
        if user_input is not None:
            new_counter = dict(counter)
            if meter_type == METER_TYPE_ELECTRICITY:
                new_counter[CONF_MQTT_TOPIC_DAY] = user_input[CONF_MQTT_TOPIC_DAY]
                new_counter[CONF_MQTT_TOPIC_NIGHT] = user_input[CONF_MQTT_TOPIC_NIGHT]
                new_counter[CONF_MQTT_TOPIC_COMMAND] = user_input[CONF_MQTT_TOPIC_COMMAND]
                new_counter[CONF_MQTT_TOPIC_AVAILABLE] = user_input[CONF_MQTT_TOPIC_AVAILABLE]
            else:
                new_counter[CONF_MQTT_TOPIC_MAIN] = user_input[CONF_MQTT_TOPIC_MAIN]
                new_counter[CONF_MQTT_TOPIC_AVAILABLE] = user_input[CONF_MQTT_TOPIC_AVAILABLE]
            
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters[self._selected_counter_id] = new_counter
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            
            return self.async_create_entry(title="", data={})
        
        handler = self._get_handler_by_counter_id()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            schema = vol.Schema({
                vol.Required(CONF_MQTT_TOPIC_DAY, default=handler.topic_day if handler else DEFAULT_MQTT_TOPIC_DAY): str,
                vol.Required(CONF_MQTT_TOPIC_NIGHT, default=handler.topic_night if handler else DEFAULT_MQTT_TOPIC_NIGHT): str,
                vol.Required(CONF_MQTT_TOPIC_COMMAND, default=handler.topic_command if handler else DEFAULT_MQTT_TOPIC_COMMAND): str,
                vol.Required(CONF_MQTT_TOPIC_AVAILABLE, default=handler.topic_available if handler else DEFAULT_MQTT_TOPIC_AVAILABLE): str,
            })
        else:
            schema = vol.Schema({
                vol.Required(CONF_MQTT_TOPIC_MAIN, default=handler.topic_main if handler else DEFAULT_MQTT_TOPIC_MAIN): str,
                vol.Optional(CONF_MQTT_TOPIC_AVAILABLE, default=handler.topic_available if handler else ""): str,
            })
        
        return self.async_show_form(step_id="edit_topics", data_schema=schema)
    
    async def async_step_delete_counter(self, user_input=None):
        """Удаление счетчика."""
        if user_input is not None:
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters.pop(self._selected_counter_id)
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            return self.async_create_entry(title="", data={})
        
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        
        return self.async_show_form(
            step_id="delete_counter",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": counter[CONF_NAME]
            }
        )
