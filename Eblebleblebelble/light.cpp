#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>

#define LIGHT_PIN 34

// WiFi credentials
const char* ssid = "StumilowyLas";
const char* password = "netlab123";

const int esp_id = 1;
// MQTT broker settings
const char* mqtt_server = "192.168.220.1";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32/light";

// Encryption variables
int key = 2137;
int keylimiter = 69;

// WiFi and MQTT clients
WiFiClient espClient;
PubSubClient client(espClient);

void setup_wifi() {

  delay(10);

  Serial.println("Connecting to WiFi...");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {

    delay(1000);
    Serial.print(WiFi.status());
  }

  Serial.println("\nWiFi connected");

  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void reconnect_mqtt() {

  while (!client.connected()) {

    Serial.print("Connecting to MQTT...");

    if (client.connect("ESP32_LIGHT_Client")) {

      Serial.println("connected");

    } else {

      Serial.print("failed, rc=");
      Serial.print(client.state());

      Serial.println(" retrying in 5 seconds");

      delay(5000);
    }
  }
}

void encryptData(char * payload)
{
  for (int i = 0; payload[i] != '\0'; i++) {

    payload[i] = (char)((int)payload[i] + key % keylimiter);
  }
}

int readLightLevel() {
  int val = analogRead(LIGHT_PIN);
  
  // Basic sanity check: If the value is impossible, return -1 
  // (In your case, analogRead is 0-4095, so -1 is our "Internal Error")
  if (val <= 0 || val >= 2000) return -1; 
  
  return val;
}

void setup() {

  Serial.begin(115200);

  delay(1000);

  pinMode(LIGHT_PIN, INPUT);
  
  setup_wifi();

  client.setServer(mqtt_server, mqtt_port);
}

void loop() {
  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  int lightValue = readLightLevel();
  char payload[10];

  // Logic to handle "Invalid" or "NaN" readings
  if (lightValue != -1) {
    itoa(lightValue, payload, 10);
  } else {
    strcpy(payload, "nan");
  }

  encryptData(payload);

  char finalPayload[24]; 
  sprintf(finalPayload, "%d;%s", esp_id, payload);

  Serial.print("Sending: ");
  Serial.println(finalPayload);
  
  client.publish(mqtt_topic, finalPayload);

  delay(10000); 
}
