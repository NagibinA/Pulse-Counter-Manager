"""Константы для интеграции Pulse Counter Manager"""

DOMAIN = "pulse_counter"
VERSION = "1.0.0"

# Конфигурационные ключи
CONF_DEVICES = "devices"
CONF_NAME = "name"
CONF_MQTT_TOPIC_DAY = "mqtt_topic_day"
CONF_MQTT_TOPIC_NIGHT = "mqtt_topic_night"
CONF_MQTT_TOPIC_COMMAND = "mqtt_topic_command"
CONF_MQTT_TOPIC_AVAILABLE = "mqtt_topic_available"
CONF_DAY_TARIFF = "day_tariff"
CONF_NIGHT_TARIFF = "night_tariff"
CONF_NIGHT_START = "night_start"
CONF_NIGHT_END = "night_end"
CONF_PULSES_PER_KWH = "pulses_per_kwh"
CONF_LEGACY_MQTT = "legacy_mqtt"
CONF_LEGACY_TOPIC_DAY = "legacy_topic_day"
CONF_LEGACY_TOPIC_NIGHT = "legacy_topic_night"
CONF_INITIAL_DAY_KWH = "initial_day_kwh"
CONF_INITIAL_NIGHT_KWH = "initial_night_kwh"

# Значения по умолчанию
DEFAULT_DAY_TARIFF = 8.10
DEFAULT_NIGHT_TARIFF = 4.42
DEFAULT_NIGHT_START = "20:19"
DEFAULT_NIGHT_END = "04:19"
DEFAULT_PULSES_PER_KWH = 1000
DEFAULT_MQTT_TOPIC_DAY = "Counter/day"
DEFAULT_MQTT_TOPIC_NIGHT = "Counter/night"
DEFAULT_MQTT_TOPIC_COMMAND = "Counter/choice"
DEFAULT_MQTT_TOPIC_AVAILABLE = "Counter/Available"

# События и состояния
EVENT_IMPULSE_RECEIVED = f"{DOMAIN}_impulse_received"
STATE_DAY = "day"
STATE_NIGHT = "night"

# Единицы измерения
UNIT_RUB = "руб"
UNIT_KWH = "кВт·ч"
UNIT_IMPULSE = "имп"

# Атрибуты сенсоров
ATTR_PARTIAL_IMPULSES = "partial_impulses"
ATTR_TOTAL_KWH = "total_kwh"
ATTR_DAY_RATE = "day_rate"
ATTR_NIGHT_RATE = "night_rate"
ATTR_CURRENT_TARIFF = "current_tariff"
ATTR_LAST_RESET = "last_reset"
