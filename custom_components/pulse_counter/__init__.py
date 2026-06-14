"""Инициализация интеграции Pulse Counter Manager."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    VERSION,
    CONF_COUNTERS,
    CONF_MQTT_BROKER,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_MQTT_PASSWORD,
    CONF_COUNTER_ID,
    METER_TYPE_ELECTRICITY,
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
    DEFAULT_NOTIFICATION_DAY,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_SERVICE,
    DEFAULT_NOTIFICATION_SHOW_DAY,
    DEFAULT_NOTIFICATION_SHOW_NIGHT,
    DEFAULT_NOTIFICATION_SHOW_TOTAL,
    DEFAULT_NOTIFICATION_SHOW_COST,
    DEFAULT_NOTIFICATION_SHOW_MONTH,
)

from .mqtt_handler import (
    PulseCounterMQTTHandler,
    PulseCounterWaterMQTTHandler,
    PulseCounterGasMQTTHandler,
    PulseCounterHeatMQTTHandler,
)

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Настройка интеграции из config entry."""
    
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][CONF_COUNTERS] = {}
        hass.data[DOMAIN]["handlers"] = {}
        hass.data[DOMAIN]["polling_enabled"] = False
        hass.data[DOMAIN]["notified_this_month"] = {}  # Для отслеживания отправленных уведомлений

    broker = entry.data[CONF_MQTT_BROKER]
    port = entry.data[CONF_MQTT_PORT]
    username = entry.data.get(CONF_MQTT_USERNAME, "")
    password = entry.data.get(CONF_MQTT_PASSWORD, "")
    
    counters = entry.data.get(CONF_COUNTERS, {})
    
    # Создаем обработчики для каждого счетчика
    for counter_name, counter_config in counters.items():
        meter_type = counter_config.get("meter_type", METER_TYPE_ELECTRICITY)
        
        if meter_type == METER_TYPE_ELECTRICITY:
            handler_class = PulseCounterMQTTHandler
        else:
            handler_class = PulseCounterWaterMQTTHandler
        
        handler = handler_class(
            hass,
            broker=broker,
            port=port,
            username=username,
            password=password,
            config=counter_config,
        )
        
        # Добавляем настройки уведомлений в handler
        handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
        handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
        handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
        handler.notification_service = counter_config.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)
        handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
        handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
        handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
        handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
        handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
        handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
        
        await handler.async_initialize()
        hass.data[DOMAIN]["handlers"][counter_config[CONF_COUNTER_ID]] = handler
        hass.data[DOMAIN]["notified_this_month"][counter_config[CONF_COUNTER_ID]] = False
    
    # Регистрируем платформы сенсоров
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Добавляем слушатель обновления опций
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    # Слушатель для добавления нового счетчика через опции
    async def async_add_counter(counter_config):
        meter_type = counter_config.get("meter_type", METER_TYPE_ELECTRICITY)
        
        if meter_type == METER_TYPE_ELECTRICITY:
            handler_class = PulseCounterMQTTHandler
        else:
            handler_class = PulseCounterWaterMQTTHandler
        
        handler = handler_class(
            hass,
            broker=broker,
            port=port,
            username=username,
            password=password,
            config=counter_config,
        )
        
        # Добавляем настройки уведомлений
        handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
        handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
        handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
        handler.notification_service = counter_config.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)
        handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
        handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
        handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
        handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
        handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
        handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
        
        await handler.async_initialize()
        hass.data[DOMAIN]["handlers"][counter_config[CONF_COUNTER_ID]] = handler
        hass.data[DOMAIN]["notified_this_month"][counter_config[CONF_COUNTER_ID]] = False
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_counter", async_add_counter)
    )
    
    # Функция проверки и отправки ежемесячных уведомлений
    async def check_monthly_notifications(now):
        """Проверяет, нужно ли отправить уведомления."""
        current = dt_util.now()
        current_month = current.month
        current_day = current.day
        current_hour = current.hour
        current_minute = current.minute
        
        for counter_id, handler in hass.data[DOMAIN]["handlers"].items():
            if not handler.notification_enabled:
                continue
            
            # Парсим время из настроек
            try:
                time_parts = handler.notification_time.split(":")
                target_hour = int(time_parts[0])
                target_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            except (ValueError, IndexError):
                _LOGGER.warning("Неверный формат времени для %s: %s", handler.name, handler.notification_time)
                continue
            
            # Проверяем день и время
            if current_day == handler.notification_day and current_hour == target_hour and current_minute == target_minute:
                # Проверяем, не отправляли ли уже уведомление в этом месяце
                if not hass.data[DOMAIN]["notified_this_month"].get(counter_id, False):
                    await send_monthly_notification(hass, handler)
                    hass.data[DOMAIN]["notified_this_month"][counter_id] = True
                    _LOGGER.info("Отправлено ежемесячное уведомление для %s", handler.name)
        
        # Сбрасываем флаги в первый день следующего месяца
        if current_day == 1 and current_hour == 0 and current_minute == 0:
            for counter_id in hass.data[DOMAIN]["notified_this_month"]:
                hass.data[DOMAIN]["notified_this_month"][counter_id] = False
    
    # Функция отправки уведомления
    async def send_monthly_notification(hass, handler):
        """Отправляет уведомление с показаниями счетчика."""
        
        message_lines = []
        
        # Заголовок
        message_lines.append(f"🏠 **{handler.name}**")
        message_lines.append("")
        
        # Показания в зависимости от типа счетчика
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
        
        # Дополнительное сообщение
        if handler.notification_custom_message:
            message_lines.append("")
            message_lines.append(f"💬 {handler.notification_custom_message}")
        
        message = "\n".join(message_lines)
        
        # Отправка через выбранный сервис
        service = handler.notification_service
        
        if service == "persistent_notification":
            hass.components.persistent_notification.async_create(
                message,
                title=f"📊 {handler.name} - ежемесячные показания",
                notification_id=f"pulse_counter_monthly_{handler.counter_id}"
            )
        elif service.startswith("notify."):
            # Для notify сервисов
            service_name = service.split(".")[-1] if "." in service else service
            await hass.services.async_call(
                "notify",
                service_name,
                {
                    "title": f"📊 {handler.name}",
                    "message": message
                },
                blocking=False
            )
        else:
            # Попробуем как есть
            await hass.services.async_call(
                "notify",
                service,
                {
                    "title": f"📊 {handler.name}",
                    "message": message
                },
                blocking=False
            )
    
    # Запускаем проверку уведомлений каждую минуту
    async_track_time_interval(hass, check_monthly_notifications, timedelta(minutes=1))
    
    # Обработчик остановки HA
    async def handle_ha_stop(event):
        """При остановке HA останавливаем опрос ESP."""
        _LOGGER.info("Остановка Home Assistant, прекращение опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = False
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_stop_polling()
            await handler.async_save_state()
        _LOGGER.info("Опрос всех счетчиков остановлен, состояние сохранено")

    # Обработчик запуска HA
    async def handle_ha_start(event):
        """При запуске HA возобновляем опрос ESP."""
        _LOGGER.info("Запуск Home Assistant, возобновление опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = True
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_start_polling()
        _LOGGER.info("Опрос всех счетчиков возобновлен")
    
    # Регистрируем обработчики событий
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_ha_stop)
    
    # Если HA уже запущен, запускаем опрос сразу, иначе ждем события старта
    if hass.state == CoreState.running:
        await handle_ha_start(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, handle_ha_start)
    
    _LOGGER.info("Pulse Counter Manager v%s успешно загружен с %d счетчиками", 
                 VERSION, len(hass.data[DOMAIN]["handlers"]))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Выгрузка интеграции."""
    
    _LOGGER.info("Выгрузка Pulse Counter Manager")
    
    # Останавливаем все обработчики
    for handler_id, handler in hass.data[DOMAIN]["handlers"].items():
        await handler.async_shutdown()
    
    hass.data[DOMAIN]["handlers"].clear()
    hass.data[DOMAIN]["polling_enabled"] = False
    hass.data[DOMAIN]["notified_this_month"].clear()
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        if not hass.data[DOMAIN]["handlers"]:
            hass.data.pop(DOMAIN)
        _LOGGER.info("Pulse Counter Manager успешно выгружен")
    else:
        _LOGGER.error("Ошибка при выгрузке Pulse Counter Manager")
    
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Обработчик обновления опций."""
    _LOGGER.info("Обновление конфигурации Pulse Counter Manager")
    await hass.config_entries.async_reload(entry.entry_id)
