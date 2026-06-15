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
    CONF_NOTIFICATION_SEND_TO_ALL,
    CONF_NOTIFICATION_TARGET_DEVICES,
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
        handler.notification_send_to_all = counter_config.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL)
        handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
        
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
        handler.notification_send_to_all = counter_config.get(CONF_NOTIFICATION_SEND_TO_ALL, DEFAULT_NOTIFICATION_SEND_TO_ALL)
        handler.notification_target_devices = counter_config.get(CONF_NOTIFICATION_TARGET_DEVICES, DEFAULT_NOTIFICATION_TARGET_DEVICES)
        
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
        
        # Первая строка: "📊 Показания счетчика"
        message_lines.append(f"📊 Показания счетчика")
        # Вторая строка: "🏠 Электроэнергия" (или название счетчика)
        message_lines.append(f"🏠 {handler.name}")
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
        message_title = f"📊 {handler.name}"
        
        # Получаем выбранный сервис и настройки устройств
        service = handler.notification_service
        send_to_all = getattr(handler, 'notification_send_to_all', True)
        target_devices = getattr(handler, 'notification_target_devices', [])
        
        _LOGGER.info("=" * 60)
        _LOGGER.info("Отправка ЕЖЕМЕСЯЧНОГО уведомления для счетчика: %s", handler.name)
        _LOGGER.info("Выбранный сервис: '%s'", service)
        _LOGGER.info("Отправлять на все устройства: %s", send_to_all)
        _LOGGER.info("Целевые устройства: %s", target_devices)
        
        try:
            # Вариант 1: persistent_notification
            if service == "persistent_notification":
                _LOGGER.info("→ Отправка через persistent_notification")
                hass.components.persistent_notification.async_create(
                    message,
                    title=message_title,
                    notification_id=f"pulse_counter_monthly_{handler.counter_id}"
                )
                _LOGGER.info("✓ Уведомление создано в persistent_notification")
            
            # Вариант 2: notify.notify или конкретные мобильные устройства
            elif service == "notify.notify" or service.startswith("notify.mobile_app_"):
                # Ищем все мобильные устройства
                all_services = hass.services.async_services()
                mobile_services = []
                
                for service_name in all_services.get("notify", []):
                    if service_name.startswith("mobile_app_"):
                        mobile_services.append(f"notify.{service_name}")
                
                _LOGGER.info("Найдено мобильных устройств: %d", len(mobile_services))
                
                if not mobile_services:
                    _LOGGER.warning("Мобильные устройства не найдены!")
                    hass.components.persistent_notification.async_create(
                        f"❌ Не найдено мобильных устройств с Companion App.\n\n"
                        f"1. Убедитесь, что приложение установлено и вы вошли в аккаунт.\n"
                        f"2. Перезагрузите Home Assistant.\n"
                        f"3. Затем снова откройте приложение на телефоне.\n\n"
                        f"Инструкция: https://companion.home-assistant.io/docs/getting_started/",
                        title="📬 Pulse Counter Manager",
                        notification_id="pulse_counter_mobile_error"
                    )
                    return
                
                # Определяем, на какие устройства отправлять
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
                    await hass.services.async_call(
                        "notify",
                        mobile_service_name.replace("notify.", ""),
                        {
                            "title": message_title,
                            "message": message
                        },
                        blocking=False
                    )
                _LOGGER.info("✓ Отправлено на %d устройств", len(devices_to_send))
            
            _LOGGER.info("✅ Ежемесячное уведомление для %s успешно отправлено", handler.name)
            _LOGGER.info("=" * 60)
            
        except Exception as e:
            _LOGGER.error("❌ ОШИБКА отправки ежемесячного уведомления для %s: %s", handler.name, e)
            _LOGGER.error("=" * 60)
    
    # Функция проверки и отправки ежемесячных уведомлений
    async def check_monthly_notifications(now):
        """Проверяет, нужно ли отправить уведомления."""
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
