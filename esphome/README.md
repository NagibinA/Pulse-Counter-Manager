# ESPHome конфигурация для Pulse Counter Manager

Альтернатива Arduino прошивке для тех, кто использует ESPHome.

## Установка

1. Скопируйте `pulse_counter_minimal.yaml` в папку `esphome` Home Assistant
2. Отредактируйте параметры в секции `substitutions`:
   - `wifi_ssid` / `wifi_password`
   - `mqtt_broker` / `mqtt_username` / `mqtt_password`
3. Прошейте ESP через ESPHome (Install → Plug into this computer)

## Подключение TEMT6000

| TEMT6000 | Wemos D1 mini |
|----------|---------------|
| VCC | 3.3V |
| GND | GND |
| OUT | A0 |

## Что делает прошивка

- Считает импульсы с TEMT6000
- Публикует счетчик в MQTT (день/ночь)
- Принимает команды `day`/`night`, `+`/`-`
- Публикует статус `online`/`offline`

Полностью совместима с интеграцией Pulse Counter Manager.

## Отличие от Arduino версии

| | Arduino | ESPHome |
|--|---------|---------|
| Сложность | Высокая | Низкая |
| Обновление | Перепрошивка | OTA |
| Логи | Serial | Веб-интерфейс |
