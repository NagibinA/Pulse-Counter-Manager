"""Константы для интеграции Pulse Counter Manager."""

DOMAIN = "pulse_counter"
VERSION = "1.3.2"  # ← ОБНОВЛЕНО

# Ссылка на официальные тарифы
TARIFF_INFO_URL = "https://www.elec.ru/library/rd/tarify-elektroenergiya-2026/st-peterburg.html"

# Режимы брокера для экспорта
EXPORT_BROKER_MAIN = "main"
EXPORT_BROKER_CUSTOM = "custom"

# Типы счетчиков
METER_TYPE_ELECTRICITY = "electricity"
METER_TYPE_WATER = "water"
METER_TYPE_GAS = "gas"
METER_TYPE_HEAT = "heat"

METER_TYPES = {
    METER_TYPE_ELECTRICITY: "Счетчик электроэнергии",
    METER_TYPE_WATER: "Счетчик воды",
    METER_TYPE_GAS: "Счетчик газа",
    METER_TYPE_HEAT: "Счетчик тепла",
}

# Настройки по умолчанию для разных типов
METER_DEFAULTS = {
    METER_TYPE_ELECTRICITY: {
        "name": "Электроэнергия",
        "unit": "кВт·ч",
        "unit_cost": "руб/кВт·ч",
        "pulses_per_unit": 1000,
        "has_tariffs": True,
        "has_day_night": True,
        "icon": "mdi:lightning-bolt",
        "topics": {
            "day": "Counter/day",
            "night": "Counter/night",
            "command": "Counter/choice",
            "available": "Counter/Available",
        }
    },
    METER_TYPE_WATER: {
        "name": "Вода",
        "unit": "м³",
        "unit_cost": "руб/м³",
        "pulses_per_unit": 100,
        "has_tariffs": False,
        "has_day_night": False,
        "icon": "mdi:water",
        "topics": {
            "main": "Water/meter",
            "command": None,
            "available": "Water/available",
        }
    },
    METER_TYPE_GAS: {
        "name": "Газ",
        "unit": "м³",
        "unit_cost": "руб/м³",
        "pulses_per_unit": 10,
        "has_tariffs": False,
        "has_day_night": False,
        "icon": "mdi:fire",
        "topics": {
            "main": "Gas/meter",
            "command": None,
            "available": "Gas/available",
        }
    },
    METER_TYPE_HEAT: {
        "name": "Тепло",
        "unit": "Гкал",
        "unit_cost": "руб/Гкал",
        "pulses_per_unit": 1000,
        "has_tariffs": False,
        "has_day_night": False,
        "icon": "mdi:radiator",
        "topics": {
            "main": "Heat/meter",
            "command": None,
            "available": "Heat/available",
        }
    },
}

# Конфигурационные ключи
CONF_NAME = "name"
CONF_METER_TYPE = "meter_type"
CONF_MQTT_BROKER = "broker"
CONF_MQTT_PORT = "port"
CONF_MQTT_USERNAME = "username"
CONF_MQTT_PASSWORD = "password"
CONF_COUNTERS = "counters"
CONF_COUNTER_ID = "id"
CONF_MQTT_TOPIC_DAY = "topic_day"
CONF_MQTT_TOPIC_NIGHT = "topic_night"
CONF_MQTT_TOPIC_MAIN = "topic_main"
CONF_MQTT_TOPIC_COMMAND = "topic_command"
CONF_MQTT_TOPIC_AVAILABLE = "topic_available"
CONF_DAY_TARIFF = "day_tariff"
CONF_NIGHT_TARIFF = "night_tariff"
CONF_TARIFF = "tariff"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_PULSES_PER_UNIT = "pulses_per_unit"
CONF_UNIT = "unit"
CONF_EXPORT_ENABLED = "export_enabled"
CONF_EXPORT_BROKER_MODE = "export_broker_mode"
CONF_EXPORT_BROKER = "export_broker"
CONF_EXPORT_PORT = "export_port"
CONF_EXPORT_USERNAME = "export_username"
CONF_EXPORT_PASSWORD = "export_password"
CONF_EXPORT_TOPIC_DAY = "export_topic_day"
CONF_EXPORT_TOPIC_NIGHT = "export_topic_night"
CONF_INITIAL_VALUE = "initial_value"
CONF_INITIAL_DAY_KWH = "initial_day_kwh"
CONF_INITIAL_NIGHT_KWH = "initial_night_kwh"
CONF_MONTH_START_VALUE = "month_start_value"
CONF_MONTH_START_DAY = "month_start_day"
CONF_MONTH_START_NIGHT = "month_start_night"

# Значения по умолчанию для электроэнергии
DEFAULT_DAY_TARIFF = 8.10
DEFAULT_NIGHT_TARIFF = 4.42
DEFAULT_NIGHT_START = "20:19"
DEFAULT_NIGHT_END = "04:19"

# Значения по умолчанию для воды/газа/тепла
DEFAULT_TARIFF = 0

# Общие значения по умолчанию
DEFAULT_PULSES_PER_UNIT = 1000
DEFAULT_MQTT_TOPIC_DAY = "Counter/day"
DEFAULT_MQTT_TOPIC_NIGHT = "Counter/night"
DEFAULT_MQTT_TOPIC_MAIN = "meter"
DEFAULT_MQTT_TOPIC_COMMAND = "Counter/choice"
DEFAULT_MQTT_TOPIC_AVAILABLE = "Counter/Available"
DEFAULT_EXPORT_TOPIC_DAY = "export/day"
DEFAULT_EXPORT_TOPIC_NIGHT = "export/night"
DEFAULT_EXPORT_BROKER = ""
DEFAULT_EXPORT_PORT = 1883
DEFAULT_EXPORT_BROKER_MODE = EXPORT_BROKER_MAIN

# События и состояния
EVENT_IMPULSE_RECEIVED = f"{DOMAIN}_impulse_received"
EVENT_THRESHOLD_CHANGED = f"{DOMAIN}_threshold_changed"
STATE_DAY = "day"
STATE_NIGHT = "night"

# Единицы измерения
UNIT_RUB = "руб"
UNIT_KWH = "кВт·ч"
UNIT_M3 = "м³"
UNIT_GCAL = "Гкал"
UNIT_IMPULSE = "имп"

# Атрибуты сенсоров
ATTR_PARTIAL_IMPULSES = "partial_impulses"
ATTR_TOTAL_VALUE = "total_value"
ATTR_DAY_RATE = "day_rate"
ATTR_NIGHT_RATE = "night_rate"
ATTR_CURRENT_TARIFF = "current_tariff"
ATTR_LAST_RESET = "last_reset"
ATTR_MONTH_START = "month_start"
ATTR_MONTH_VALUE = "month_value"
