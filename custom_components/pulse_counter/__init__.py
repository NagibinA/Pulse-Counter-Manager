"""Инициализация интеграции Pulse Counter Manager."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util
from homeassistant.components import persistent_notification

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
    CONF_NOTIFICATION_SHOW_DAY,
    CONF_NOTIFICATION_SHOW_NIGHT,
    CONF_NOTIFICATION_SHOW_TOTAL,
    CONF_NOTIFICATION_SHOW_COST,
    CONF_NOTIFICATION_SHOW_MONTH,
    CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_CUSTOM_MESSAGE,
    CONF_NOTIFICATION_TARGET_DEVICES,
    CONF_NOTIFICATION_SEND_TO_HA,
    DEFAULT_NOTIFICATION_DAY,
    DEFAULT_NOTIFICATION_TIME,
    DEFAULT_NOTIFICATION_SHOW_DAY,
    DEFAULT_NOTIFICATION_SHOW_NIGHT,
    DEFAULT_NOTIFICATION_SHOW_TOTAL,
    DEFAULT_NOTIFICATION_SHOW_COST,
    DEFAULT_NOTIFICATION_SHOW_MONTH,
    DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE,
    DEFAULT_NOTIFICATION_TARGET_DEVICES,
    DEFAULT_NOTIFICATION_SEND_TO_HA,
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
        hass.data[DOMAIN]["notified_this_month"] = {}

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
        
        # Добавляем настройки уведомлений в handler (НОВЫЕ ПОЛЯ)
        handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
        handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
        handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
        handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
        handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
        handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
        handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
        handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
        handler.notification_show_custom_message = counter_config.get(CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE, DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE)
        handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
        handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
        handler.notification_send_to_ha = counter_config.get(CONF_NOTIFICATION_SEND_TO_HA, DEFAULT_NOTIFICATION_SEND_TO_HA)
        
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
        
        # Добавляем настройки уведомлений (НОВЫЕ ПОЛЯ)
        handler.notification_enabled = counter_config.get(CONF_NOTIFICATION_ENABLED, False)
        handler.notification_day = counter_config.get(CONF_NOTIFICATION_DAY, DEFAULT_NOTIFICATION_DAY)
        handler.notification_time = counter_config.get(CONF_NOTIFICATION_TIME, DEFAULT_NOTIFICATION_TIME)
        handler.notification_show_day = counter_config.get(CONF_NOTIFICATION_SHOW_DAY, DEFAULT_NOTIFICATION_SHOW_DAY)
        handler.notification_show_night = counter_config.get(CONF_NOTIFICATION_SHOW_NIGHT, DEFAULT_NOTIFICATION_SHOW_NIGHT)
        handler.notification_show_total = counter_config.get(CONF_NOTIFICATION_SHOW_TOTAL, DEFAULT_NOTIFICATION_SHOW_TOTAL)
        handler.notification_show_cost = counter_config.get(CONF_NOTIFICATION_SHOW_COST, DEFAULT_NOTIFICATION_SHOW_COST)
        handler.notification_show_month = counter_config.get(CONF_NOTIFICATION_SHOW_MONTH, DEFAULT_NOTIFICATION_SHOW_MONTH)
        handler.notification_show_custom_message = counter_config.get(CONF_NOTIFICATION_SHOW_CUSTOM_MESSAGE, DEFAULT_NOTIFICATION_SHOW_CUSTOM_MESSAGE)
        handler.notification_custom_message = counter_config.get(CONF_NOTIFICATION_CUSTOM_MESSAGE, "")
        handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
        handler.notification_send_to_ha = counter_config.get(CONF_NOTIFICATION_SEND_TO_HA, DEFAULT_NOTIFICATION_SEND_TO_HA)
        
        await handler.async_initialize()
        hass.data[DOMAIN]["handlers"][counter_config[CONF_COUNTER_ID]] = handler
        hass.data[DOMAIN]["notified_this_month"][counter_config[CONF_COUNTER_ID]] = False
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    entry.async_on_unload(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_counter", async_add_counter)
    )
    
    # Функция отправки уведомления
    async def send_monthly_notification(hass, handler):
        """Отправляет уведомление с показаниями счетчика."""
        
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
        
        if handler.notification_show_custom_message and handler.notification_custom_message:
            message_lines.append("")
            message_lines.append(f"💬 {handler.notification_custom_message}")
        
        message = "\n".join(message_lines)
        message_title = f"📊 {handler.name}"
        
        # Получаем сохраненные настройки
        send_to_ha = getattr(handler, 'notification_send_to_ha', True)
        target_devices = getattr(handler, 'notification_target_devices', [])
        
        # Ежемесячные уведомления должны ЗАМЕНЯТЬ предыдущее (фиксированный ID)
        monthly_id = f"pulse_counter_monthly_{handler.counter_id}"
        
        _LOGGER.info("=" * 60)
        _LOGGER.info("Отправка ЕЖЕМЕСЯЧНОГО уведомления для счетчика: %s", handler.name)
        _LOGGER.info("Отправлять в Home Assistant: %s", send_to_ha)
        _LOGGER.info("Выбранные устройства: %s", target_devices)
        
        success_count = 0
        
        # Отправка в Home Assistant (фиксированный ID)
        if send_to_ha:
            _LOGGER.info("→ Отправка в Home Assistant")
            persistent_notification.async_create(
                hass,
                message,
                title=message_title,
                notification_id=monthly_id
            )
            _LOGGER.info("✓ Отправлено в Home Assistant")
            success_count += 1
        
        # Отправка на мобильные устройства
        all_services = hass.services.async_services()
        notify_services = all_services.get("notify", [])
        
        for device_service in target_devices:
            if not device_service.startswith("notify."):
                device_service = f"notify.{device_service}"
            
            service_name = device_service.replace("notify.", "")
            if service_name in notify_services:
                _LOGGER.info("→ Отправка на устройство: %s", device_service)
                try:
                    await hass.services.async_call(
                        "notify",
                        service_name,
                        {
                            "title": message_title,
                            "message": message,
                            "data": {"ttl": 0, "priority": "high"}
                        },
                        blocking=False
                    )
                    _LOGGER.info("✓ Отправлено на %s", device_service)
                    success_count += 1
                except Exception as e:
                    _LOGGER.error("❌ Ошибка отправки на %s: %s", device_service, e)
            else:
                _LOGGER.warning("Сервис не найден: %s", device_service)
        
        _LOGGER.info("✅ Ежемесячное уведомление отправлено в %d мест", success_count)
        _LOGGER.info("=" * 60)
    
    # Функция проверки и отправки ежемесячных уведомлений
    async def check_monthly_notifications(now):
        """Проверяет, нужно ли отправить уведомления."""
        # Проверяем существование данных
        if DOMAIN not in hass.data or "handlers" not in hass.data[DOMAIN]:
            return
        
        current = dt_util.now()
        current_day = current.day
        current_hour = current.hour
        current_minute = current.minute
        current_second = current.second
        
        for counter_id, handler in hass.data[DOMAIN]["handlers"].items():
            if not handler.notification_enabled:
                continue
            
            # Парсим время из настроек
            try:
                time_parts = handler.notification_time.split(":")
                target_hour = int(time_parts[0])
                target_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                target_second = int(time_parts[2]) if len(time_parts) > 2 else 0
            except (ValueError, IndexError):
                _LOGGER.warning("Неверный формат времени для %s: %s", handler.name, handler.notification_time)
                continue
            
            # Проверяем день и время
            time_match = (current_hour == target_hour and 
                         current_minute == target_minute and 
                         current_second == target_second)
            
            if current_day == handler.notification_day and time_match:
                if not hass.data[DOMAIN]["notified_this_month"].get(counter_id, False):
                    _LOGGER.info("Наступило время отправки уведомления для %s", handler.name)
                    await send_monthly_notification(hass, handler)
                    hass.data[DOMAIN]["notified_this_month"][counter_id] = True
        
        # Сбрасываем флаги в первый день следующего месяца
        if current_day == 1 and current_hour == 0 and current_minute == 0 and current_second == 0:
            for counter_id in hass.data[DOMAIN]["notified_this_month"]:
                hass.data[DOMAIN]["notified_this_month"][counter_id] = False
            _LOGGER.info("Флаги уведомлений сброшены")
    
    # Запускаем проверку уведомлений каждые 30 секунд
    async_track_time_interval(hass, check_monthly_notifications, timedelta(seconds=30))
    
    # Обработчик остановки HA
    async def handle_ha_stop(event):
        _LOGGER.info("Остановка Home Assistant, прекращение опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = False
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_stop_polling()
            await handler.async_save_state()
        _LOGGER.info("Опрос всех счетчиков остановлен, состояние сохранено")

    # Обработчик запуска HA
    async def handle_ha_start(event):
        _LOGGER.info("Запуск Home Assistant, возобновление опроса ESP")
        hass.data[DOMAIN]["polling_enabled"] = True
        for handler in hass.data[DOMAIN]["handlers"].values():
            await handler.async_start_polling()
        _LOGGER.info("Опрос всех счетчиков возобновлен")
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, handle_ha_stop)
    
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
