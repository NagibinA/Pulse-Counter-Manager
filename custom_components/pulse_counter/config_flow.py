"""Config Flow для Pulse Counter Manager."""

import logging
import asyncio
import socket
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.components import persistent_notification
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    VERSION,
    METER_TYPES,
    METER_DEFAULTS,
    METER_TYPE_ELECTRICITY,
    METER_TYPE_WATER,
    METER_TYPE_GAS,
    METER_TYPE_HEAT,
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
    CONF_NOTIFICATION_ENABLED,
    CONF_NOTIFICATION_DAY,
    CONF_NOTIFICATION_TIME,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_SHOW_DAY,
    CONF_NOTIFICATION_SHOW_NIGHT,
    CONF_NOTIFICATION_SHOW_TOTAL,
    CONF_NOTIFICATION_SHOW_COST,
    CONF_NOTIFICATION_SHOW_MONTH,
    CONF_NOTIFICATION_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_SEND_TO_ALL,
    CONF_NOTIFICATION_TARGET_DEVICES,
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
    DEFAULT_NOTIFICATION_DAY,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_SERVICE,
    DEFAULT_NOTIFICATION_SHOW_DAY,
    DEFAULT_NOTIFICATION_SHOW_NIGHT,
    DEFAULT_NOTIFICATION_SHOW_TOTAL,
    DEFAULT_NOTIFICATION_SHOW_COST,
    DEFAULT_NOTIFICATION_SHOW_MONTH,
    DEFAULT_NOTIFICATION_SEND_TO_ALL,
    DEFAULT_NOTIFICATION_TARGET_DEVICES,
    NOTIFICATION_SERVICES,
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


def validate_time_format(time_str: str) -> bool:
    """Проверка формата времени HH:MM или HH:MM:SS."""
    pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])(:([0-5][0-9]))?$')
    return bool(pattern.match(time_str))


def get_topic_preview(topic: str, context: str = "") -> str:
    """Создает предпросмотр MQTT топика."""
    if not topic:
        return "—"
    
    preview = topic
    if "{name}" in preview and context:
        preview = preview.replace("{name}", context.lower().replace(" ", "_"))
    
    return preview


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
            errors=errors,
            description_placeholders={
                "info": "Укажите параметры MQTT брокера, к которому подключены ESP.",
            }
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
    
    async def async_get_mobile_devices(self):
        """Получить список мобильных устройств из device_registry."""
        device_registry = dr.async_get(self.hass)
        mobile_devices = []
        
        all_services = self.hass.services.async_services()
        notify_services = all_services.get("notify", [])
        
        for device in device_registry.devices.values():
            device_name = device.name_by_user or device.name or "Неизвестное устройство"
            
            for domain, device_id in device.identifiers:
                if domain == "mobile_app":
                    service_name = f"notify.mobile_app_{device_id}"
                    if service_name in notify_services:
                        mobile_devices.append({
                            "id": device_id,
                            "name": device_name,
                            "service": service_name
                        })
                    break
        
        for service_name in notify_services:
            if service_name.startswith("mobile_app_"):
                service_full = f"notify.{service_name}"
                if not any(d["service"] == service_full for d in mobile_devices):
                    device_name = service_name.replace("mobile_app_", "").replace("_", " ").title()
                    mobile_devices.append({
                        "id": service_name,
                        "name": f"📱 {device_name}",
                        "service": service_full
                    })
        
        return mobile_devices
    
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
            "add_counter": "➕ Добавить счетчик",
            "edit_counter": "✏️ Редактировать счетчик",
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
            description_placeholders={
                "info": "Управление счетчиками: добавление нового или редактирование существующего.",
            }
        )
    
    async def async_step_select_type(self, user_input=None):
        """Выбор типа счетчика."""
        if user_input is not None:
            self._meter_type = user_input[CONF_METER_TYPE]
            return await self.async_step_add_counter()
        
        meter_types_desc = {
            METER_TYPE_ELECTRICITY: "⚡ Счетчик электроэнергии (двухтарифный, день/ночь)",
            METER_TYPE_WATER: "💧 Счетчик воды (однотарифный)",
            METER_TYPE_GAS: "🔥 Счетчик газа (однотарифный)",
            METER_TYPE_HEAT: "🌡️ Счетчик тепла (однотарифный)",
        }
        
        return self.async_show_form(
            step_id="select_type",
            data_schema=vol.Schema({
                vol.Required(CONF_METER_TYPE): vol.In(meter_types_desc)
            }),
            description_placeholders={
                "info": "Выберите тип добавляемого счетчика. От этого зависят доступные настройки.",
            }
        )
    
    async def async_step_add_counter(self, user_input=None):
        """Добавление счетчика в зависимости от типа."""
        errors = {}
        defaults = METER_DEFAULTS[self._meter_type]
        counters = self._entry.data.get(CONF_COUNTERS, {})
        used_ids = list(counters.keys())
        
        if user_input is not None:
            try:
                if self._meter_type == METER_TYPE_ELECTRICITY:
                    if not validate_time_format(user_input[CONF_NIGHT_START]):
                        errors[CONF_NIGHT_START] = "invalid_time_format"
                    if not validate_time_format(user_input[CONF_NIGHT_END]):
                        errors[CONF_NIGHT_END] = "invalid_time_format"
                    
                    if user_input[CONF_DAY_TARIFF] < 0:
                        errors[CONF_DAY_TARIFF] = "tariff_negative"
                    if user_input[CONF_NIGHT_TARIFF] < 0:
                        errors[CONF_NIGHT_TARIFF] = "tariff_negative"
                
                if user_input.get(CONF_PULSES_PER_UNIT, 0) <= 0:
                    errors[CONF_PULSES_PER_UNIT] = "pulses_positive"
                
                if user_input.get(CONF_EXPORT_PORT, 1883) < 1 or user_input.get(CONF_EXPORT_PORT, 1883) > 65535:
                    errors[CONF_EXPORT_PORT] = "invalid_port"
                
                if user_input.get(CONF_NOTIFICATION_ENABLED, False):
                    notification_day = user_input.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
                    if notification_day < 1 or notification_day > 31:
                        errors[CONF_NOTIFICATION_DAY] = "invalid_day"
                
                if not errors:
                    counter_name = user_input[CONF_NAME]
                    counter_id = f"counter_{counter_name.lower().replace(' ', '_')}"
                    
                    if counter_id in used_ids:
                        errors[CONF_NAME] = "name_exists"
                    else:
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
                            CONF_NOTIFICATION_ENABLED: user_input.get(CONF_NOTIFICATION_ENABLED, False),
                            CONF_NOTIFICATION_DAY: user_input.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY),
                            CONF_NOTIFICATION_TIME: user_input.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME),
                            CONF_NOTIFICATION_SERVICE: user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE),
                            CONF_NOTIFICATION_SHOW_DAY: user_input.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY),
                            CONF_NOTIFICATION_SHOW_NIGHT: user_input.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT),
                            CONF_NOTIFICATION_SHOW_TOTAL: user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL),
                            CONF_NOTIFICATION_SHOW_COST: user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST),
                            CONF_NOTIFICATION_SHOW_MONTH: user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH),
                            CONF_NOTIFICATION_CUSTOM_MESSAGE: user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, ""),
                            CONF_NOTIFICATION_SEND_TO_ALL: user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL),
                            CONF_NOTIFICATION_TARGET_DEVICES: user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES),
                        }
                        
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
                            new_counter.update({
                                CONF_MQTT_TOPIC_MAIN: user_input[CONF_MQTT_TOPIC_MAIN],
                                CONF_MQTT_TOPIC_AVAILABLE: user_input.get(CONF_MQTT_TOPIC_AVAILABLE, defaults["topics"]["available"]),
                                CONF_TARIFF: user_input.get(CONF_TARIFF, DEFAULT_TARIFF),
                                CONF_EXPORT_TOPIC_DAY: user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY),
                                CONF_EXPORT_TOPIC_NIGHT: user_input.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT),
                            })
                        
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
        
        if self._meter_type == METER_TYPE_ELECTRICITY:
            schema = self._build_electricity_schema(defaults, user_input)
            description = self._get_electricity_description(user_input)
        else:
            schema = self._build_utility_schema(defaults, user_input)
            description = self._get_utility_description(self._meter_type, user_input)
        
        return self.async_show_form(
            step_id="add_counter",
            data_schema=schema,
            errors=errors,
            description_placeholders=description
        )
    
    def _build_electricity_schema(self, defaults, user_input):
        """Построение схемы для электричества с группировкой."""
        schema_dict = {}
        
        schema_dict[vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, "") if user_input else "")] = str
        
        schema_dict[vol.Required(CONF_MQTT_TOPIC_DAY, 
            default=user_input.get(CONF_MQTT_TOPIC_DAY, DEFAULT_MQTT_TOPIC_DAY) if user_input else DEFAULT_MQTT_TOPIC_DAY)] = str
        schema_dict[vol.Required(CONF_MQTT_TOPIC_NIGHT, 
            default=user_input.get(CONF_MQTT_TOPIC_NIGHT, DEFAULT_MQTT_TOPIC_NIGHT) if user_input else DEFAULT_MQTT_TOPIC_NIGHT)] = str
        schema_dict[vol.Required(CONF_MQTT_TOPIC_COMMAND, 
            default=user_input.get(CONF_MQTT_TOPIC_COMMAND, DEFAULT_MQTT_TOPIC_COMMAND) if user_input else DEFAULT_MQTT_TOPIC_COMMAND)] = str
        schema_dict[vol.Required(CONF_MQTT_TOPIC_AVAILABLE, 
            default=user_input.get(CONF_MQTT_TOPIC_AVAILABLE, DEFAULT_MQTT_TOPIC_AVAILABLE) if user_input else DEFAULT_MQTT_TOPIC_AVAILABLE)] = str
        
        schema_dict[vol.Required(CONF_DAY_TARIFF, 
            default=user_input.get(CONF_DAY_TARIFF, DEFAULT_DAY_TARIFF) if user_input else DEFAULT_DAY_TARIFF)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_NIGHT_TARIFF, 
            default=user_input.get(CONF_NIGHT_TARIFF, DEFAULT_NIGHT_TARIFF) if user_input else DEFAULT_NIGHT_TARIFF)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_NIGHT_START, 
            default=user_input.get(CONF_NIGHT_START, DEFAULT_NIGHT_START) if user_input else DEFAULT_NIGHT_START)] = str
        schema_dict[vol.Required(CONF_NIGHT_END, 
            default=user_input.get(CONF_NIGHT_END, DEFAULT_NIGHT_END) if user_input else DEFAULT_NIGHT_END)] = str
        
        schema_dict[vol.Required(CONF_PULSES_PER_UNIT, 
            default=user_input.get(CONF_PULSES_PER_UNIT, defaults["pulses_per_unit"]) if user_input else defaults["pulses_per_unit"])] = int
        
        schema_dict[vol.Required(CONF_INITIAL_DAY_KWH, 
            default=user_input.get(CONF_INITIAL_DAY_KWH, 0) if user_input else 0)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_INITIAL_NIGHT_KWH, 
            default=user_input.get(CONF_INITIAL_NIGHT_KWH, 0) if user_input else 0)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_MONTH_START_DAY, 
            default=user_input.get(CONF_MONTH_START_DAY, 0) if user_input else 0)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_MONTH_START_NIGHT, 
            default=user_input.get(CONF_MONTH_START_NIGHT, 0) if user_input else 0)] = vol.Coerce(float)
        
        schema_dict[vol.Optional(CONF_EXPORT_ENABLED, 
            default=user_input.get(CONF_EXPORT_ENABLED, False) if user_input else False)] = bool
        schema_dict[vol.Optional(CONF_EXPORT_BROKER_MODE, 
            default=user_input.get(CONF_EXPORT_BROKER_MODE, DEFAULT_EXPORT_BROKER_MODE) if user_input else DEFAULT_EXPORT_BROKER_MODE)] = vol.In({
                EXPORT_BROKER_MAIN: "Основной брокер",
                EXPORT_BROKER_CUSTOM: "Отдельный брокер",
            })
        schema_dict[vol.Optional(CONF_EXPORT_BROKER, 
            default=user_input.get(CONF_EXPORT_BROKER, DEFAULT_EXPORT_BROKER) if user_input else DEFAULT_EXPORT_BROKER)] = str
        schema_dict[vol.Optional(CONF_EXPORT_PORT, 
            default=user_input.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT) if user_input else DEFAULT_EXPORT_PORT)] = int
        schema_dict[vol.Optional(CONF_EXPORT_USERNAME, 
            default=user_input.get(CONF_EXPORT_USERNAME, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_EXPORT_PASSWORD, 
            default=user_input.get(CONF_EXPORT_PASSWORD, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_EXPORT_TOPIC_DAY, 
            default=user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY) if user_input else DEFAULT_EXPORT_TOPIC_DAY)] = str
        schema_dict[vol.Optional(CONF_EXPORT_TOPIC_NIGHT, 
            default=user_input.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT) if user_input else DEFAULT_EXPORT_TOPIC_NIGHT)] = str
        
        schema_dict[vol.Optional(CONF_NOTIFICATION_ENABLED, 
            default=user_input.get(CONF_NOTIFICATION_ENABLED, False) if user_input else False)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_DAY, 
            default=user_input.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY) if user_input else DEFAULT_NOTIFICATION_DAY)] = int
        schema_dict[vol.Optional(CONF_NOTIFICATION_TIME, 
            default=user_input.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME) if user_input else DEFAULT_NOTIFICATION_TIME)] = str
        schema_dict[vol.Optional(CONF_NOTIFICATION_SERVICE, 
            default=user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE) if user_input else DEFAULT_NOTIFICATION_SERVICE)] = vol.In(NOTIFICATION_SERVICES)
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_DAY, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY) if user_input else DEFAULT_NOTIFICATION_SHOW_DAY)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_NIGHT, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT) if user_input else DEFAULT_NOTIFICATION_SHOW_NIGHT)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_TOTAL, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL) if user_input else DEFAULT_NOTIFICATION_SHOW_TOTAL)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_COST, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST) if user_input else DEFAULT_NOTIFICATION_SHOW_COST)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_MONTH, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH) if user_input else DEFAULT_NOTIFICATION_SHOW_MONTH)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_CUSTOM_MESSAGE, 
            default=user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_NOTIFICATION_SEND_TO_ALL, 
            default=user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL) if user_input else DEFAULT_NOTIFICATION_SEND_TO_ALL)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_TARGET_DEVICES, 
            default=user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES) if user_input else DEFAULT_NOTIFICATION_TARGET_DEVICES)] = vol.All(vol.Coerce(list), vol.Length(min=0))
        
        return vol.Schema(schema_dict)
    
    def _build_utility_schema(self, defaults, user_input):
        """Построение схемы для воды/газа/тепла с группировкой."""
        schema_dict = {}
        
        schema_dict[vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, "") if user_input else "")] = str
        
        schema_dict[vol.Required(CONF_MQTT_TOPIC_MAIN, 
            default=user_input.get(CONF_MQTT_TOPIC_MAIN, defaults["topics"]["main"]) if user_input else defaults["topics"]["main"])] = str
        schema_dict[vol.Optional(CONF_MQTT_TOPIC_AVAILABLE, 
            default=user_input.get(CONF_MQTT_TOPIC_AVAILABLE, defaults["topics"]["available"]) if user_input else defaults["topics"]["available"])] = str
        
        schema_dict[vol.Required(CONF_PULSES_PER_UNIT, 
            default=user_input.get(CONF_PULSES_PER_UNIT, defaults["pulses_per_unit"]) if user_input else defaults["pulses_per_unit"])] = int
        
        schema_dict[vol.Optional(CONF_TARIFF, 
            default=user_input.get(CONF_TARIFF, DEFAULT_TARIFF) if user_input else DEFAULT_TARIFF)] = vol.Coerce(float)
        
        schema_dict[vol.Required(CONF_INITIAL_VALUE, 
            default=user_input.get(CONF_INITIAL_VALUE, 0) if user_input else 0)] = vol.Coerce(float)
        schema_dict[vol.Required(CONF_MONTH_START_VALUE, 
            default=user_input.get(CONF_MONTH_START_VALUE, 0) if user_input else 0)] = vol.Coerce(float)
        
        schema_dict[vol.Optional(CONF_EXPORT_ENABLED, 
            default=user_input.get(CONF_EXPORT_ENABLED, False) if user_input else False)] = bool
        schema_dict[vol.Optional(CONF_EXPORT_BROKER_MODE, 
            default=user_input.get(CONF_EXPORT_BROKER_MODE, DEFAULT_EXPORT_BROKER_MODE) if user_input else DEFAULT_EXPORT_BROKER_MODE)] = vol.In({
                EXPORT_BROKER_MAIN: "Основной брокер",
                EXPORT_BROKER_CUSTOM: "Отдельный брокер",
            })
        schema_dict[vol.Optional(CONF_EXPORT_BROKER, 
            default=user_input.get(CONF_EXPORT_BROKER, DEFAULT_EXPORT_BROKER) if user_input else DEFAULT_EXPORT_BROKER)] = str
        schema_dict[vol.Optional(CONF_EXPORT_PORT, 
            default=user_input.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT) if user_input else DEFAULT_EXPORT_PORT)] = int
        schema_dict[vol.Optional(CONF_EXPORT_USERNAME, 
            default=user_input.get(CONF_EXPORT_USERNAME, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_EXPORT_PASSWORD, 
            default=user_input.get(CONF_EXPORT_PASSWORD, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_EXPORT_TOPIC_DAY, 
            default=user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY) if user_input else DEFAULT_EXPORT_TOPIC_DAY)] = str
        
        schema_dict[vol.Optional(CONF_NOTIFICATION_ENABLED, 
            default=user_input.get(CONF_NOTIFICATION_ENABLED, False) if user_input else False)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_DAY, 
            default=user_input.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY) if user_input else DEFAULT_NOTIFICATION_DAY)] = int
        schema_dict[vol.Optional(CONF_NOTIFICATION_TIME, 
            default=user_input.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME) if user_input else DEFAULT_NOTIFICATION_TIME)] = str
        schema_dict[vol.Optional(CONF_NOTIFICATION_SERVICE, 
            default=user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE) if user_input else DEFAULT_NOTIFICATION_SERVICE)] = vol.In(NOTIFICATION_SERVICES)
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_TOTAL, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL) if user_input else DEFAULT_NOTIFICATION_SHOW_TOTAL)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_MONTH, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH) if user_input else DEFAULT_NOTIFICATION_SHOW_MONTH)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_COST, 
            default=user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST) if user_input else DEFAULT_NOTIFICATION_SHOW_COST)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_CUSTOM_MESSAGE, 
            default=user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "") if user_input else "")] = str
        schema_dict[vol.Optional(CONF_NOTIFICATION_SEND_TO_ALL, 
            default=user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL) if user_input else DEFAULT_NOTIFICATION_SEND_TO_ALL)] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_TARGET_DEVICES, 
            default=user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES) if user_input else DEFAULT_NOTIFICATION_TARGET_DEVICES)] = vol.All(vol.Coerce(list), vol.Length(min=0))
        
        return vol.Schema(schema_dict)
    
    def _get_electricity_description(self, user_input):
        """Подсказки для формы электричества с предпросмотром."""
        name = user_input.get(CONF_NAME, "") if user_input else ""
        
        topic_day = user_input.get(CONF_MQTT_TOPIC_DAY, DEFAULT_MQTT_TOPIC_DAY) if user_input else DEFAULT_MQTT_TOPIC_DAY
        topic_night = user_input.get(CONF_MQTT_TOPIC_NIGHT, DEFAULT_MQTT_TOPIC_NIGHT) if user_input else DEFAULT_MQTT_TOPIC_NIGHT
        topic_command = user_input.get(CONF_MQTT_TOPIC_COMMAND, DEFAULT_MQTT_TOPIC_COMMAND) if user_input else DEFAULT_MQTT_TOPIC_COMMAND
        topic_available = user_input.get(CONF_MQTT_TOPIC_AVAILABLE, DEFAULT_MQTT_TOPIC_AVAILABLE) if user_input else DEFAULT_MQTT_TOPIC_AVAILABLE
        export_topic_day = user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY) if user_input else DEFAULT_EXPORT_TOPIC_DAY
        export_topic_night = user_input.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT) if user_input else DEFAULT_EXPORT_TOPIC_NIGHT
        
        notification_service = user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE) if user_input else DEFAULT_NOTIFICATION_SERVICE
        notification_service_desc = NOTIFICATION_SERVICES.get(notification_service, notification_service)
        
        return {
            "section1_title": "📋 Основные параметры",
            "name_desc": "Удобное название счетчика (например, 'Квартира', 'Гараж')",
            
            "section2_title": "📡 MQTT Топики",
            "topic_day_desc": f"Топик, куда ESP публикует дневные импульсы\n"
                             f"📌 Пример: `Counter/day`\n"
                             f"🔍 Предпросмотр: `{get_topic_preview(topic_day, name)}`",
            "topic_night_desc": f"Топик, куда ESP публикует ночные импульсы\n"
                               f"📌 Пример: `Counter/night`\n"
                               f"🔍 Предпросмотр: `{get_topic_preview(topic_night, name)}`",
            "topic_command_desc": f"Топик для отправки команд на ESP (day/night/+/-)\n"
                                 f"📌 Пример: `Counter/choice`\n"
                                 f"🔍 Предпросмотр: `{get_topic_preview(topic_command, name)}`",
            "topic_available_desc": f"Топик статуса ESP (LWT)\n"
                                   f"📌 Пример: `Counter/Available`\n"
                                   f"🔍 Предпросмотр: `{get_topic_preview(topic_available, name)}`",
            
            "section3_title": "💰 Тарифы",
            "day_tariff_desc": f"Дневной тариф (руб/кВт·ч)\nАктуальные тарифы: {TARIFF_INFO_URL}",
            "night_tariff_desc": f"Ночной тариф (руб/кВт·ч)\nАктуальные тарифы: {TARIFF_INFO_URL}",
            "night_start_desc": "Время начала ночного тарифа\nФормат: ЧЧ:ММ (например, 23:00)",
            "night_end_desc": "Время окончания ночного тарифа\nФормат: ЧЧ:ММ (например, 07:00)",
            
            "section4_title": "⚙️ Параметры счетчика",
            "pulses_desc": "Количество импульсов на 1 кВт·ч\nОбычно указано на счетчике (например, 1000 имп/кВт·ч)",
            
            "section5_title": "📊 Начальные показания",
            "initial_day_desc": "Текущие дневные показания счетчика (кВт·ч)\nВведите значение с прибора учета",
            "initial_night_desc": "Текущие ночные показания счетчика (кВт·ч)\nВведите значение с прибора учета",
            "month_start_day_desc": "Дневные показания на начало месяца (кВт·ч)\nДля расчета потребления за текущий месяц",
            "month_start_night_desc": "Ночные показания на начало месяца (кВт·ч)\nДля расчета потребления за текущий месяц",
            
            "section6_title": "📤 Экспорт показаний",
            "export_enabled_desc": "Отправлять показания в дополнительные MQTT топики",
            "export_broker_mode_desc": "Использовать основной брокер или отдельный",
            "export_broker_desc": "IP адрес брокера для экспорта\nПример: 192.168.1.100",
            "export_port_desc": "Порт брокера для экспорта (обычно 1883)",
            "export_username_desc": "Имя пользователя для экспорта (если требуется)",
            "export_password_desc": "Пароль для экспорта (если требуется)",
            "export_topic_day_desc": f"Топик для экспорта дневных показаний\n"
                                    f"📌 Пример: `energy/day`\n"
                                    f"🔍 Предпросмотр: `{get_topic_preview(export_topic_day, name)}`",
            "export_topic_night_desc": f"Топик для экспорта ночных показаний\n"
                                      f"📌 Пример: `energy/night`\n"
                                      f"🔍 Предпросмотр: `{get_topic_preview(export_topic_night, name)}`",
            
            "section7_title": "📬 Ежемесячные уведомления",
            "notification_enabled_desc": "Автоматически отправлять показания в указанный день месяца",
            "notification_day_desc": "День месяца для отправки уведомления (1-31)",
            "notification_time_desc": "Время отправки уведомления (формат ЧЧ:ММ:СС)",
            "notification_service_desc": f"Куда отправлять уведомление\nТекущий выбор: {notification_service_desc}",
            "notification_show_day_desc": "Показывать дневные показания в уведомлении",
            "notification_show_night_desc": "Показывать ночные показания в уведомлении",
            "notification_show_total_desc": "Показывать общие показания в уведомлении",
            "notification_show_cost_desc": "Показывать стоимость в уведомлении",
            "notification_show_month_desc": "Показывать потребление за месяц",
            "notification_custom_message_desc": "Дополнительный текст в уведомлении\n(например, 'Пора передавать показания')",
            "notification_send_to_all_desc": "Отправлять на все мобильные устройства",
            "notification_target_devices_desc": "Выберите конкретные устройства для отправки",
            
            "tariff_url": TARIFF_INFO_URL,
        }
    
    def _get_utility_description(self, meter_type, user_input):
        """Подсказки для форм воды/газа/тепла с предпросмотром."""
        type_names = {
            METER_TYPE_WATER: "воды",
            METER_TYPE_GAS: "газа",
            METER_TYPE_HEAT: "тепла",
        }
        type_name = type_names.get(meter_type, "счетчика")
        units = {
            METER_TYPE_WATER: "м³",
            METER_TYPE_GAS: "м³",
            METER_TYPE_HEAT: "Гкал",
        }
        unit = units.get(meter_type, "ед")
        
        name = user_input.get(CONF_NAME, "") if user_input else ""
        topic_main = user_input.get(CONF_MQTT_TOPIC_MAIN, "") if user_input else ""
        topic_available = user_input.get(CONF_MQTT_TOPIC_AVAILABLE, "") if user_input else ""
        export_topic = user_input.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY) if user_input else DEFAULT_EXPORT_TOPIC_DAY
        
        notification_service = user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE) if user_input else DEFAULT_NOTIFICATION_SERVICE
        notification_service_desc = NOTIFICATION_SERVICES.get(notification_service, notification_service)
        
        return {
            "section1_title": "📋 Основные параметры",
            "name_desc": f"Удобное название счетчика {type_name} (например, 'Холодная вода', 'Отопление')",
            
            "section2_title": "📡 MQTT Топики",
            "topic_main_desc": f"Топик, куда ESP публикует импульсы\n"
                              f"📌 Пример: `{type_name.capitalize()}/meter`\n"
                              f"🔍 Предпросмотр: `{get_topic_preview(topic_main, name)}`",
            "topic_available_desc": f"Топик статуса ESP (LWT)\n"
                                   f"📌 Пример: `{type_name.capitalize()}/available`\n"
                                   f"🔍 Предпросмотр: `{get_topic_preview(topic_available, name)}`",
            
            "section3_title": "⚙️ Параметры счетчика",
            "pulses_desc": f"Количество импульсов на 1 {unit}\nОбычно указано на счетчике (например, 100 имп/{unit})",
            
            "section4_title": "💰 Тариф",
            "tariff_desc": f"Тариф на {type_name} (руб/{unit})\nВведите актуальную стоимость",
            
            "section5_title": "📊 Начальные показания",
            "initial_value_desc": f"Текущие показания счетчика ({unit})\nВведите значение с прибора учета",
            "month_start_value_desc": f"Показания на начало месяца ({unit})\nДля расчета потребления за текущий месяц",
            
            "section6_title": "📤 Экспорт показаний",
            "export_enabled_desc": "Отправлять показания в дополнительные MQTT топики",
            "export_broker_mode_desc": "Использовать основной брокер или отдельный",
            "export_broker_desc": "IP адрес брокера для экспорта\nПример: 192.168.1.100",
            "export_port_desc": "Порт брокера для экспорта (обычно 1883)",
            "export_username_desc": "Имя пользователя для экспорта (если требуется)",
            "export_password_desc": "Пароль для экспорта (если требуется)",
            "export_topic_day_desc": f"Топик для экспорта показаний\n"
                                    f"📌 Пример: `{type_name}/total`\n"
                                    f"🔍 Предпросмотр: `{get_topic_preview(export_topic, name)}`",
            
            "section7_title": "📬 Ежемесячные уведомления",
            "notification_enabled_desc": "Автоматически отправлять показания в указанный день месяца",
            "notification_day_desc": "День месяца для отправки уведомления (1-31)",
            "notification_time_desc": "Время отправки уведомления (формат ЧЧ:ММ:СС)",
            "notification_service_desc": f"Куда отправлять уведомление\nТекущий выбор: {notification_service_desc}",
            "notification_show_total_desc": "Показывать общие показания в уведомлении",
            "notification_show_month_desc": "Показывать потребление за месяц",
            "notification_show_cost_desc": "Показывать стоимость в уведомлении",
            "notification_custom_message_desc": "Дополнительный текст в уведомлении",
            "notification_send_to_all_desc": "Отправлять на все мобильные устройства",
            "notification_target_devices_desc": "Выберите конкретные устройства для отправки",
        }
    
    async def async_step_edit_counter(self, user_input=None):
        """Выбор счетчика для редактирования."""
        counters = self._entry.data.get(CONF_COUNTERS, {})
        
        if not counters:
            return self.async_abort(reason="no_counters")
        
        counter_options = {}
        for cid, cconfig in counters.items():
            counter_options[cid] = cconfig[CONF_NAME]
        
        if user_input is not None:
            selected_id = user_input["counter_id"]
            self._selected_counter_id = selected_id
            return await self.async_step_edit_choice()
        
        return self.async_show_form(
            step_id="edit_counter",
            data_schema=vol.Schema({vol.Required("counter_id"): vol.In(counter_options)}),
            description_placeholders={
                "info": "Выберите счетчик, который хотите отредактировать.",
            }
        )
    
    async def async_step_edit_choice(self, user_input=None):
        """Действия с выбранным счетчиком."""
        actions = {
            "edit_current": "📊 Изменить текущие показания",
            "edit_month_start": "📅 Изменить показания на начало месяца",
            "edit_accumulated": "⚡ Изменить накопленные импульсы",
            "edit_tariffs": "💰 Изменить тарифы",
            "edit_pulses": "⚙️ Изменить коэффициент импульсов",
            "edit_threshold": "🔧 Настроить порог ESP",
            "edit_export": "📤 Настроить экспорт показаний",
            "edit_topics": "📡 Изменить MQTT топики",
            "edit_notifications": "📬 Настроить уведомления",
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
            elif action == "edit_threshold":
                return await self.async_step_edit_threshold()
            elif action == "edit_export":
                return await self.async_step_edit_export()
            elif action == "edit_topics":
                return await self.async_step_edit_topics()
            elif action == "edit_notifications":
                return await self.async_step_edit_notifications()
        
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        
        return self.async_show_form(
            step_id="edit_choice",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
            description_placeholders={
                "name": counter[CONF_NAME],
                "info": f"Выберите действие для счетчика **{counter[CONF_NAME]}**",
            }
        )
    
    def _get_handler_by_counter_id(self):
        """Получить handler по counter_id."""
        handlers = self.hass.data[DOMAIN]["handlers"]
        return handlers.get(self._selected_counter_id)
    
    async def _send_test_notification(self, handler):
        """Отправить тестовое уведомление с текущими настройками."""
        message_lines = []
        
        message_lines.append(f"📊 Показания счетчика")
        message_lines.append(f"🏠 {handler.name}")
        message_lines.append("")
        
        if handler.meter_type == METER_TYPE_ELECTRICITY:
            if handler.notification_show_day:
                message_lines.append(f"☀️ День: **{handler.day_kwh:.1f}** kWh")
            if handler.notification_show_night:
                message_lines.append(f"🌙 Ночь: **{handler.night_kwh:.1f}** kWh")
            if handler.notification_show_total:
                message_lines.append(f"📈 Всего: **{handler.total_value:.1f}** kWh")
            if handler.notification_show_month:
                message_lines.append(f"📅 За месяц: **{handler.month_value:.1f}** kWh")
            if handler.notification_show_cost:
                message_lines.append(f"💰 Стоимость за месяц: **{handler.month_total_cost:.2f}** руб")
        else:
            if handler.notification_show_total:
                message_lines.append(f"📈 Всего: **{handler.total_value:.1f}** {handler.unit}")
            if handler.notification_show_month:
                message_lines.append(f"📅 За месяц: **{handler.month_value:.1f}** {handler.unit}")
            if handler.notification_show_cost:
                message_lines.append(f"💰 Стоимость за месяц: **{handler.month_cost:.2f}** руб")
        
        if handler.notification_custom_message:
            message_lines.append("")
            message_lines.append(f"💬 {handler.notification_custom_message}")
        
        message = "\n".join(message_lines)
        message_title = f"📊 {handler.name}"
        
        service = handler.notification_service
        send_to_all = getattr(handler, 'notification_send_to_all', True)
        target_devices = getattr(handler, 'notification_target_devices', [])
        
        _LOGGER.info("=" * 60)
        _LOGGER.info("Отправка ТЕСТОВОГО уведомления для счетчика: %s", handler.name)
        _LOGGER.info("Выбранный сервис: '%s'", service)
        _LOGGER.info("Отправлять на все устройства: %s", send_to_all)
        _LOGGER.info("Целевые устройства: %s", target_devices)
        
        try:
            if service == "persistent_notification":
                _LOGGER.info("→ Отправка через persistent_notification")
                persistent_notification.async_create(
                    handler.hass,
                    message,
                    title=message_title,
                    notification_id=f"pulse_counter_test_{handler.counter_id}"
                )
                _LOGGER.info("✓ Уведомление создано в persistent_notification")
            
            elif service == "notify.notify" or service.startswith("notify.mobile_app_"):
                all_services = handler.hass.services.async_services()
                mobile_services = []
                
                for service_name in all_services.get("notify", []):
                    if service_name.startswith("mobile_app_"):
                        mobile_services.append(f"notify.{service_name}")
                
                _LOGGER.info("Найдено мобильных устройств: %d", len(mobile_services))
                
                if not mobile_services:
                    _LOGGER.warning("Мобильные устройства не найдены!")
                    persistent_notification.async_create(
                        handler.hass,
                        f"❌ Не найдено мобильных устройств с Companion App.",
                        title="📬 Pulse Counter Manager",
                        notification_id="pulse_counter_mobile_error"
                    )
                    return
                
                devices_to_send = []
                
                if service == "notify.notify" and send_to_all:
                    devices_to_send = mobile_services
                    _LOGGER.info("Режим: отправка на ВСЕ устройства")
                elif service == "notify.notify" and not send_to_all:
                    for device in target_devices:
                        if device in mobile_services:
                            devices_to_send.append(device)
                    _LOGGER.info("Режим: отправка на ВЫБРАННЫЕ устройства: %s", devices_to_send)
                elif service.startswith("notify.mobile_app_"):
                    if service in mobile_services:
                        devices_to_send = [service]
                        _LOGGER.info("Режим: отправка на КОНКРЕТНОЕ устройство: %s", service)
                
                if not devices_to_send:
                    _LOGGER.warning("Нет устройств для отправки")
                    return
                
                for mobile_service_name in devices_to_send:
                    _LOGGER.info("→ Отправка на устройство: %s", mobile_service_name)
                    await handler.hass.services.async_call(
                        "notify",
                        mobile_service_name.replace("notify.", ""),
                        {
                            "title": message_title,
                            "message": message
                        },
                        blocking=False
                    )
                _LOGGER.info("✓ Отправлено на %d устройств", len(devices_to_send))
            
            _LOGGER.info("✅ Тестовое уведомление для %s успешно отправлено", handler.name)
            _LOGGER.info("=" * 60)
            
        except Exception as e:
            _LOGGER.error("❌ ОШИБКА отправки тестового уведомления для %s: %s", handler.name, e)
            _LOGGER.error("=" * 60)
    
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
        
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("day_total_kwh", 0) if data else 0
            current_night = data.get("night_total_kwh", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("day_kwh", default=current_day, description="Дневные показания (кВт·ч)"): vol.Coerce(float),
                vol.Required("night_kwh", default=current_night, description="Ночные показания (кВт·ч)"): vol.Coerce(float),
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Введите текущие показания счетчика. Они будут отображаться в сенсорах.",
            }
        else:
            current_val = data.get("total_value", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("total_value", default=current_val, description=f"Показания ({counter[CONF_UNIT]})"): vol.Coerce(float),
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": f"Введите текущие показания счетчика в {counter[CONF_UNIT]}.",
            }
        
        return self.async_show_form(
            step_id="edit_current", 
            data_schema=schema,
            description_placeholders=description
        )
    
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
        
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("month_start_day", 0) if data else 0
            current_night = data.get("month_start_night", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("month_start_day", default=current_day, description="Дневные показания на начало месяца (кВт·ч)"): vol.Coerce(float),
                vol.Required("month_start_night", default=current_night, description="Ночные показания на начало месяца (кВт·ч)"): vol.Coerce(float),
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Введите показания счетчика на начало текущего месяца.\nПотребление за месяц будет рассчитано как: текущие - начальные.",
            }
        else:
            current_val = data.get("month_start_value", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("month_start_value", default=current_val, description=f"Показания на начало месяца ({counter[CONF_UNIT]})"): vol.Coerce(float),
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": f"Введите показания счетчика на начало текущего месяца в {counter[CONF_UNIT]}.\nПотребление за месяц будет рассчитано как: текущие - начальные.",
            }
        
        return self.async_show_form(
            step_id="edit_month_start", 
            data_schema=schema,
            description_placeholders=description
        )
    
    async def async_step_edit_accumulated(self, user_input=None):
        """Изменение накопленных импульсов."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        
        if user_input is not None:
            handler = self._get_handler_by_counter_id()
            if handler:
                if meter_type == METER_TYPE_ELECTRICITY:
                    await handler.async_set_day_partial(user_input["day_impulses"])
                    await handler.async_set_night_partial(user_input["night_impulses"])
                    _LOGGER.info("Изменены накопленные импульсы для %s: день=%d, ночь=%d", 
                                counter[CONF_NAME], user_input["day_impulses"], user_input["night_impulses"])
                else:
                    await handler.async_set_partial(user_input["impulses"])
                    _LOGGER.info("Изменены накопленные импульсы для %s: %d", 
                                counter[CONF_NAME], user_input["impulses"])
            return self.async_create_entry(title="", data={})
        
        storage = PulseCounterStorage(self.hass, counter[CONF_COUNTER_ID])
        data = await storage.async_load()
        
        if meter_type == METER_TYPE_ELECTRICITY:
            current_day = data.get("day_partial", 0) if data else 0
            current_night = data.get("night_partial", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("day_impulses", default=current_day, description="Дневные накопленные импульсы"): int,
                vol.Required("night_impulses", default=current_night, description="Ночные накопленные импульсы"): int,
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Накопленные импульсы — это остаток импульсов, не достигший целой единицы.\n"
                       "Обычно не требует ручной корректировки. Используйте для исправления расхождений.",
            }
        else:
            current_val = data.get("partial", 0) if data else 0
            
            schema = vol.Schema({
                vol.Required("impulses", default=current_val, description="Накопленные импульсы"): int,
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": f"Накопленные импульсы — это остаток импульсов, не достигший целой {counter[CONF_UNIT]}.\n"
                       f"Обычно не требует ручной корректировки. Используйте для исправления расхождений.",
            }
        
        return self.async_show_form(
            step_id="edit_accumulated",
            data_schema=schema,
            description_placeholders=description
        )
    
    async def async_step_edit_tariffs(self, user_input=None):
        """Изменение тарифов."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter[CONF_METER_TYPE]
        errors = {}
        
        if user_input is not None:
            if meter_type == METER_TYPE_ELECTRICITY:
                if not validate_time_format(user_input[CONF_NIGHT_START]):
                    errors[CONF_NIGHT_START] = "invalid_time_format"
                if not validate_time_format(user_input[CONF_NIGHT_END]):
                    errors[CONF_NIGHT_END] = "invalid_time_format"
                
                if user_input[CONF_DAY_TARIFF] < 0:
                    errors[CONF_DAY_TARIFF] = "tariff_negative"
                if user_input[CONF_NIGHT_TARIFF] < 0:
                    errors[CONF_NIGHT_TARIFF] = "tariff_negative"
            
            if not errors:
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
                vol.Required(CONF_DAY_TARIFF, default=handler.day_tariff if handler else DEFAULT_DAY_TARIFF, description="Дневной тариф (руб/кВт·ч)"): vol.Coerce(float),
                vol.Required(CONF_NIGHT_TARIFF, default=handler.night_tariff if handler else DEFAULT_NIGHT_TARIFF, description="Ночной тариф (руб/кВт·ч)"): vol.Coerce(float),
                vol.Required(CONF_NIGHT_START, default=handler.night_start if handler else DEFAULT_NIGHT_START, description="Начало ночного тарифа (ЧЧ:ММ)"): str,
                vol.Required(CONF_NIGHT_END, default=handler.night_end if handler else DEFAULT_NIGHT_END, description="Конец ночного тарифа (ЧЧ:ММ)"): str,
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Измените тарифы на электроэнергию.",
                "tariff_info_url": TARIFF_INFO_URL,
            }
        else:
            schema = vol.Schema({
                vol.Required(CONF_TARIFF, default=handler.tariff if handler else DEFAULT_TARIFF, description=f"Тариф (руб/{counter[CONF_UNIT]})"): vol.Coerce(float),
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": f"Измените тариф на {counter[CONF_UNIT]}.",
                "tariff_info_url": TARIFF_INFO_URL,
            }
        
        return self.async_show_form(
            step_id="edit_tariffs",
            data_schema=schema,
            errors=errors,
            description_placeholders=description
        )
    
    async def async_step_edit_pulses(self, user_input=None):
        """Изменение коэффициента импульсов."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        unit = counter.get(CONF_UNIT, METER_DEFAULTS.get(meter_type, {}).get("unit", "ед"))
        errors = {}
        
        if user_input is not None:
            if user_input["pulses_per_unit"] <= 0:
                errors["pulses_per_unit"] = "pulses_positive"
            else:
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
        current_value = handler.pulses_per_unit if handler else DEFAULT_PULSES_PER_UNIT
        
        schema = vol.Schema({
            vol.Required("pulses_per_unit", default=current_value, description=f"Импульсов на {unit}"): int,
        })
        
        description = {
            "name": counter[CONF_NAME],
            "info": f"Укажите, сколько импульсов соответствует 1 {unit}.\n"
                   f"Обычно это значение указано на счетчике.",
        }
        
        return self.async_show_form(
            step_id="edit_pulses",
            data_schema=schema,
            errors=errors,
            description_placeholders=description
        )
    
    async def async_step_edit_threshold(self, user_input=None):
        """Настройка порога ESP (+/-)."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        handler = self._get_handler_by_counter_id()
        
        if user_input is not None:
            action = user_input["action"]
            if action == "increase":
                await handler.async_send_threshold_command("+")
                _LOGGER.info("Отправлена команда увеличения порога для %s", counter[CONF_NAME])
            elif action == "decrease":
                await handler.async_send_threshold_command("-")
                _LOGGER.info("Отправлена команда уменьшения порога для %s", counter[CONF_NAME])
            elif action == "done":
                return self.async_create_entry(title="", data={})
            
            return self.async_show_form(
                step_id="edit_threshold",
                data_schema=vol.Schema({
                    vol.Required("action"): vol.In({
                        "increase": "➕ +10 (увеличить порог)",
                        "decrease": "➖ -10 (уменьшить порог)",
                        "done": "✅ Готово",
                    })
                }),
                description_placeholders={
                    "name": counter[CONF_NAME],
                    "info": "Настройка чувствительности ESP.\n\n"
                           "Когда светодиод счетчика мигает, ESP должна это видеть.\n\n"
                           "• Если ESP пропускает импульсы — уменьшайте порог\n"
                           "• Если ESP ловит лишние импульсы — увеличивайте порог\n\n"
                           "**Команда отправлена!** Используйте + и - несколько раз.\n\n"
                           "Нажмите 'Готово', когда закончите настройку.",
                }
            )
        
        return self.async_show_form(
            step_id="edit_threshold",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In({
                    "increase": "➕ +10 (увеличить порог)",
                    "decrease": "➖ -10 (уменьшить порог)",
                    "done": "✅ Готово",
                })
            }),
            description_placeholders={
                "name": counter[CONF_NAME],
                "info": "Настройка чувствительности ESP.\n\n"
                       "Когда светодиод счетчика мигает, ESP должна это видеть.\n\n"
                       "• Если ESP пропускает импульсы — уменьшайте порог\n"
                       "• Если ESP ловит лишние импульсы — увеличивайте порог\n\n"
                       "Нажмите + или - несколько раз для подбора значения.\n\n"
                       "Нажмите 'Готово', когда закончите настройку.",
            }
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
            vol.Optional(CONF_EXPORT_ENABLED, default=counter.get(CONF_EXPORT_ENABLED, False), description="Включить экспорт показаний"): bool,
            vol.Optional(CONF_EXPORT_BROKER_MODE, default=counter.get(CONF_EXPORT_BROKER_MODE, DEFAULT_EXPORT_BROKER_MODE), description="Брокер для экспорта"): vol.In({
                EXPORT_BROKER_MAIN: "Основной брокер",
                EXPORT_BROKER_CUSTOM: "Отдельный брокер",
            }),
            vol.Optional(CONF_EXPORT_BROKER, default=counter.get(CONF_EXPORT_BROKER, DEFAULT_EXPORT_BROKER), description="IP адрес брокера"): str,
            vol.Optional(CONF_EXPORT_PORT, default=counter.get(CONF_EXPORT_PORT, DEFAULT_EXPORT_PORT), description="Порт брокера"): int,
            vol.Optional(CONF_EXPORT_USERNAME, default=counter.get(CONF_EXPORT_USERNAME, ""), description="Имя пользователя"): str,
            vol.Optional(CONF_EXPORT_PASSWORD, default=counter.get(CONF_EXPORT_PASSWORD, ""), description="Пароль"): str,
            vol.Optional(CONF_EXPORT_TOPIC_DAY, default=counter.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY), description="Топик для показаний"): str,
        })
        
        if counter.get(CONF_METER_TYPE) == METER_TYPE_ELECTRICITY:
            schema = schema.extend({
                vol.Optional(CONF_EXPORT_TOPIC_NIGHT, default=counter.get(CONF_EXPORT_TOPIC_NIGHT, DEFAULT_EXPORT_TOPIC_NIGHT), description="Топик для ночных показаний"): str,
            })
        
        name = counter[CONF_NAME]
        export_topic = user_input.get(CONF_EXPORT_TOPIC_DAY, counter.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY)) if user_input else counter.get(CONF_EXPORT_TOPIC_DAY, DEFAULT_EXPORT_TOPIC_DAY)
        
        description = {
            "name": counter[CONF_NAME],
            "info": "Экспорт позволяет отправлять показания счетчика в любые MQTT топики.\n"
                   "Может использоваться для интеграции с другими системами.",
            "preview": f"🔍 Предпросмотр: `{get_topic_preview(export_topic, name)}`",
        }
        
        return self.async_show_form(
            step_id="edit_export",
            data_schema=schema,
            description_placeholders=description
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
        name = counter[CONF_NAME]
        
        if meter_type == METER_TYPE_ELECTRICITY:
            topic_day = handler.topic_day if handler else DEFAULT_MQTT_TOPIC_DAY
            topic_night = handler.topic_night if handler else DEFAULT_MQTT_TOPIC_NIGHT
            topic_command = handler.topic_command if handler else DEFAULT_MQTT_TOPIC_COMMAND
            topic_available = handler.topic_available if handler else DEFAULT_MQTT_TOPIC_AVAILABLE
            
            schema = vol.Schema({
                vol.Required(CONF_MQTT_TOPIC_DAY, default=topic_day, description="Топик дневных импульсов"): str,
                vol.Required(CONF_MQTT_TOPIC_NIGHT, default=topic_night, description="Топик ночных импульсов"): str,
                vol.Required(CONF_MQTT_TOPIC_COMMAND, default=topic_command, description="Топик команд"): str,
                vol.Required(CONF_MQTT_TOPIC_AVAILABLE, default=topic_available, description="Топик статуса (LWT)"): str,
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Измените MQTT топики.\nПосле изменения интеграция будет перезагружена.",
                "day_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_day, name)}`",
                "night_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_night, name)}`",
                "command_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_command, name)}`",
                "available_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_available, name)}`",
            }
        else:
            topic_main = handler.topic_main if handler else DEFAULT_MQTT_TOPIC_MAIN
            topic_available = handler.topic_available if handler else ""
            
            schema = vol.Schema({
                vol.Required(CONF_MQTT_TOPIC_MAIN, default=topic_main, description="MQTT топик импульсов"): str,
                vol.Optional(CONF_MQTT_TOPIC_AVAILABLE, default=topic_available, description="Топик статуса (LWT)"): str,
            })
            
            description = {
                "name": counter[CONF_NAME],
                "info": "Измените MQTT топики.\nПосле изменения интеграция будет перезагружена.",
                "main_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_main, name)}`",
                "available_preview": f"🔍 Предпросмотр: `{get_topic_preview(topic_available, name)}`" if topic_available else "",
            }
        
        return self.async_show_form(
            step_id="edit_topics", 
            data_schema=schema,
            description_placeholders=description
        )
    
    async def async_step_edit_notifications(self, user_input=None):
        """Изменение настроек уведомлений."""
        counter = self._entry.data[CONF_COUNTERS][self._selected_counter_id]
        meter_type = counter.get(CONF_METER_TYPE, METER_TYPE_ELECTRICITY)
        
        # Получаем список мобильных устройств
        mobile_devices = await self.async_get_mobile_devices()
        device_options = {device["service"]: device["name"] for device in mobile_devices}
        
        # Если пользователь нажал кнопку тестового уведомления
        if user_input is not None and user_input.get("test_notification"):
            handler = self._get_handler_by_counter_id()
            if handler:
                # Обновляем настройки уведомлений перед отправкой теста
                handler.notification_enabled = user_input.get(CONF_NOTIFICATION_ENABLED, False)
                handler.notification_day = user_input.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
                handler.notification_time = user_input.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
                handler.notification_service = user_input.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)
                handler.notification_send_to_all = user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL)
                handler.notification_target_devices = user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, [])
                
                if meter_type == METER_TYPE_ELECTRICITY:
                    handler.notification_show_day = user_input.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
                    handler.notification_show_night = user_input.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
                else:
                    handler.notification_show_day = False
                    handler.notification_show_night = False
                
                handler.notification_show_total = user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
                handler.notification_show_month = user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
                handler.notification_show_cost = user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
                handler.notification_custom_message = user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
                
                await self._send_test_notification(handler)
            return await self.async_step_edit_notifications()
        
        # Обычное сохранение настроек
        if user_input is not None and not user_input.get("test_notification"):
            new_counter = dict(counter)
            new_counter[CONF_NOTIFICATION_ENABLED] = user_input[CONF_NOTIFICATION_ENABLED]
            new_counter[CONF_NOTIFICATION_DAY] = user_input[CONF_NOTIFICATION_DAY]
            new_counter[CONF_NOTIFICATION_TIME] = user_input[CONF_NOTIFICATION_TIME]
            new_counter[CONF_NOTIFICATION_SERVICE] = user_input[CONF_NOTIFICATION_SERVICE]
            new_counter[CONF_NOTIFICATION_SEND_TO_ALL] = user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL)
            new_counter[CONF_NOTIFICATION_TARGET_DEVICES] = user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, [])
            
            if meter_type == METER_TYPE_ELECTRICITY:
                new_counter[CONF_NOTIFICATION_SHOW_DAY] = user_input.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
                new_counter[CONF_NOTIFICATION_SHOW_NIGHT] = user_input.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
            else:
                new_counter[CONF_NOTIFICATION_SHOW_DAY] = False
                new_counter[CONF_NOTIFICATION_SHOW_NIGHT] = False
            
            new_counter[CONF_NOTIFICATION_SHOW_TOTAL] = user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
            new_counter[CONF_NOTIFICATION_SHOW_MONTH] = user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
            new_counter[CONF_NOTIFICATION_SHOW_COST] = user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
            new_counter[CONF_NOTIFICATION_CUSTOM_MESSAGE] = user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
            
            counters = dict(self._entry.data[CONF_COUNTERS])
            counters[self._selected_counter_id] = new_counter
            
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, CONF_COUNTERS: counters}
            )
            
            handler = self._get_handler_by_counter_id()
            if handler:
                handler.notification_enabled = user_input[CONF_NOTIFICATION_ENABLED]
                handler.notification_day = user_input[CONF_NOTIFICATION_DAY]
                handler.notification_time = user_input[CONF_NOTIFICATION_TIME]
                handler.notification_service = user_input[CONF_NOTIFICATION_SERVICE]
                handler.notification_send_to_all = user_input.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL)
                handler.notification_target_devices = user_input.get(CONF_NOTIFICATION_TARGET_DEVICES, [])
                
                if meter_type == METER_TYPE_ELECTRICITY:
                    handler.notification_show_day = user_input.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
                    handler.notification_show_night = user_input.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
                else:
                    handler.notification_show_day = False
                    handler.notification_show_night = False
                
                handler.notification_show_total = user_input.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
                handler.notification_show_month = user_input.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
                handler.notification_show_cost = user_input.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
                handler.notification_custom_message = user_input.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
                
                if DOMAIN in self.hass.data and "notified_this_month" in self.hass.data[DOMAIN]:
                    self.hass.data[DOMAIN]["notified_this_month"][self._selected_counter_id] = False
                
                _LOGGER.info("Обновлены настройки уведомлений для %s", counter[CONF_NAME])
            
            return self.async_create_entry(title="", data={})
        
        # Формируем схему для редактирования уведомлений
        schema_dict = {}
        
        schema_dict[vol.Optional(CONF_NOTIFICATION_ENABLED, 
            default=counter.get(CONF_NOTIFICATION_ENABLED, False))] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_DAY, 
            default=counter.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY))] = int
        schema_dict[vol.Optional(CONF_NOTIFICATION_TIME, 
            default=counter.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME))] = str
        
        # Список сервисов уведомлений: только первый пункт и мобильные устройства
        notification_services = NOTIFICATION_SERVICES.copy()
        # Добавляем пункт "На все мобильные устройства"
        notification_services["notify.notify"] = "📱 На все мобильные устройства"
        # Добавляем конкретные мобильные устройства
        for device in mobile_devices:
            notification_services[device["service"]] = f"📱 {device['name']}"
        
        schema_dict[vol.Optional(CONF_NOTIFICATION_SERVICE, 
            default=counter.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE))] = vol.In(notification_services)
        
        # Добавляем настройки выбора устройств
        schema_dict[vol.Optional(CONF_NOTIFICATION_SEND_TO_ALL, 
            default=counter.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL))] = bool
        
        if device_options:
            current_devices = counter.get(CONF_NOTIFICATION_TARGET_DEVICES, [])
            current_devices = [d for d in current_devices if d in device_options]
            schema_dict[vol.Optional(CONF_NOTIFICATION_TARGET_DEVICES, 
                default=current_devices)] = cv.multi_select(device_options)
        
        if meter_type == METER_TYPE_ELECTRICITY:
            schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_DAY, 
                default=counter.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY))] = bool
            schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_NIGHT, 
                default=counter.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT))] = bool
        
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_TOTAL, 
            default=counter.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL))] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_MONTH, 
            default=counter.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH))] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_SHOW_COST, 
            default=counter.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST))] = bool
        schema_dict[vol.Optional(CONF_NOTIFICATION_CUSTOM_MESSAGE, 
            default=counter.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, ""))] = str
        
        schema_dict[vol.Optional("test_notification", default=False)] = bool
        
        schema = vol.Schema(schema_dict)
        
        info_text = (
            f"Настройте автоматическую отправку показаний счетчика **{counter[CONF_NAME]}**.\n\n"
            f"• **День месяца**: укажите число, когда нужно отправлять уведомление (например, 24)\n"
            f"• **Время**: формат ЧЧ:ММ:СС (например, 19:00:00)\n"
            f"• **Сервис уведомлений**:\n"
            f"   - **Уведомление в Home Assistant** — только в веб-интерфейс\n"
            f"   - **На все мобильные устройства** — на ВСЕ телефоны с Companion App\n"
            f"   - **Отдельные устройства** — выберите конкретные телефоны из списка ниже\n"
            f"• **Отправлять на все устройства** - если выключить, можно выбрать конкретные\n"
            f"• **Показания**: отметьте, что включать в уведомление\n\n"
            f"💡 **Совет:** Включите опцию **'Отправить тестовое уведомление'** ниже и нажмите **'Подтвердить'**, "
            f"чтобы проверить текущие настройки немедленно."
        )
        
        return self.async_show_form(
            step_id="edit_notifications",
            data_schema=schema,
            description_placeholders={
                "name": counter[CONF_NAME],
                "info": info_text,
            }
        )
