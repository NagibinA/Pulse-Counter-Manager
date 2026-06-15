"""Константы для интеграции Pulse Counter Manager."""

DOMAIN = "pulse_counter"
VERSION = "1.5.1"

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
        "unit": "kWh",
        "unit_cost": "руб/kWh",
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
        "unit": "m³",
        "unit_cost": "руб/m³",
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
        "unit": "m³",
        "unit_cost": "руб/m³",
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
        "unit": "Gcal",
        "unit_cost": "руб/Gcal",
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

# Константы для уведомлений
CONF_NOTIFICATION_ENABLED = "notification_enabled"
CONF_NOTIFICATION_DAY = "notification_day"
CONF_NOTIFICATION_TIME = "notification_time"
CONF_NOTIFICATION_SERVICE = "notification_service"
CONF_NOTIFICATION_SHOW_DAY = "notification_show_day"
CONF_NOTIFICATION_SHOW_NIGHT = "notification_show_night"
CONF_NOTIFICATION_SHOW_TOTAL = "notification_show_total"
CONF_NOTIFICATION_SHOW_COST = "notification_show_cost"
CONF_NOTIFICATION_SHOW_MONTH = "notification_show_month"
CONF_NOTIFICATION_CUSTOM_MESSAGE = "notification_custom_message"

# Константы для выбора устройств
CONF_NOTIFICATION_SEND_TO_ALL = "notification_send_to_all"
CONF_NOTIFICATION_TARGET_DEVICES = "notification_target_devices"

# Значения по умолчанию для уведомлений
DEFAULT_NOTIFICATION_DAY = 24
DEFAULT_NOTIFICATION_TIME = "19:00:00"
DEFAULT_NOTIFICATION_SERVICE = "persistent_notification"
DEFAULT_NOTIFICATION_SHOW_DAY = True
DEFAULT_NOTIFICATION_SHOW_NIGHT = True
DEFAULT_NOTIFICATION_SHOW_TOTAL = True
DEFAULT_NOTIFICATION_SHOW_COST = True
DEFAULT_NOTIFICATION_SHOW_MONTH = True
DEFAULT_NOTIFICATION_SEND_TO_ALL = True
DEFAULT_NOTIFICATION_TARGET_DEVICES = []

# Доступные сервисы уведомлений - ТОЛЬКО ПЕРВЫЙ ПУНКТ И МОБИЛЬНЫЕ
NOTIFICATION_SERVICES = {
    "persistent_notification": "📢 Уведомление в Home Assistant",
}

# Значения по умолчанию
DEFAULT_DAY_TARIFF = 8.10
DEFAULT_NIGHT_TARIFF = 4.42
DEFAULT_NIGHT_START = "20:19"
DEFAULT_NIGHT_END = "04:19"
DEFAULT_TARIFF = 0
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
UNIT_KWH = "kWh"
UNIT_M3 = "m³"
UNIT_GCAL = "Gcal"
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
