/*
 * Pulse Counter Manager - ESP8266 Firmware v1.4.0
 * For two-tariff electricity meter with pulse output
 * 
 * Features:
 * - Two-tariff support (day/night)
 * - MQTT retain for state persistence
 * - Adjustable threshold via MQTT (+/- commands)
 * - LWT (Last Will and Testament)
 * - WiFi STA mode only (AP disabled)
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// ========== НАСТРОЙКИ (ИЗМЕНИТЕ ПОД СЕБЯ) ==========
const char* ssid = "YourWiFi";
const char* password = "YourPassword";
IPAddress mqttServer(192, 168, 1, 100);
const char* clientID = "PulseCounter";
const char* mqtt_username = "";
const char* mqtt_password = "";

const char* mqttOutTopic = "Counter/day";
const char* mqtt_choice = "Counter/choice";
const char* mqtt_willTopic = "Counter/Available";
const char* mqtt_payloadAvailable = "online";
const char* mqtt_payloadNotAvailable = "offline";

const int pinSensor = A0;
int illuminanceThreshold = 40;

unsigned int impulseCounter = 0;
bool impulseDetected = false;
bool sendReply = false;

WiFiClient espClient;
PubSubClient client(mqttServer, 1883, callback, espClient);

void callback(char* topic, byte* payload, unsigned int length) {
    payload[length] = '\0';
    String value = String((char*)payload);
    
    if (String(topic) == mqtt_choice) {
        if (value == "day") {
            mqttOutTopic = "Counter/day";
            sendReply = true;
        } else if (value == "night") {
            mqttOutTopic = "Counter/night";
            sendReply = true;
        } else if (value == "+") {
            illuminanceThreshold += 10;
        } else if (value == "-") {
            if (illuminanceThreshold >= 15) illuminanceThreshold -= 10;
        }
    }
}

void setup_wifi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
}

void reconnect() {
    while (!client.connected()) {
        if (client.connect(clientID, mqtt_username, mqtt_password,
                          mqtt_willTopic, 0, true, mqtt_payloadNotAvailable)) {
            client.publish(mqtt_willTopic, mqtt_payloadAvailable, true);
            client.publish(mqttOutTopic, String(impulseCounter).c_str(), true);
            client.subscribe(mqtt_choice);
        } else {
            delay(5000);
        }
    }
}

void setup() {
    pinMode(pinSensor, INPUT);
    setup_wifi();
    client.setServer(mqttServer, 1883);
    client.setCallback(callback);
    reconnect();
}

void loop() {
    if (!client.connected()) {
        reconnect();
    }
    
    int illuminanceValue = analogRead(pinSensor);
    delay(10);
    
    if ((illuminanceValue > illuminanceThreshold) && !impulseDetected) {
        impulseDetected = true;
        delay(10);
    }
    
    if ((illuminanceValue < illuminanceThreshold) && impulseDetected) {
        impulseDetected = false;
        impulseCounter++;
        client.publish(mqttOutTopic, String(impulseCounter).c_str(), true);
        delay(10);
    }
    
    if (sendReply) {
        client.publish(mqttOutTopic, String(impulseCounter).c_str(), true);
        impulseCounter = 0;
        sendReply = false;
    }
    
    client.loop();
}
