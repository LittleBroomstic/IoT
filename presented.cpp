#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>

#define LIGHT_PIN 34
#define TMP102_ADDR 0x48
// WiFi credentials
const char* ssid = "StumilowyLas";
const char* password = "netlab123";
const int esp_id2 = 2;
const int esp_id = 1;
// MQTT broker settings
const char* mqtt_server = "192.168.220.1";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32/light";
const char* mqtt_topic2 = "esp32/temp";
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

float readTemperature() {
  Wire.beginTransmission(TMP102_ADDR);
  Wire.write(0x00);
  Wire.endTransmission();

  Wire.requestFrom(TMP102_ADDR, 2);

  if (Wire.available() == 2) {
    int msb = Wire.read();
    int lsb = Wire.read();

    int tempRaw = (msb << 4) | (lsb >> 4);

    if (tempRaw & 0x800) {
      tempRaw |= 0xF000;
    }

    return tempRaw * 0.0625;
  }

  return NAN;
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
  Wire.begin();
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
  Serial.print("Light: ");
  Serial.println(payload);
  
  encryptData(payload);

  char finalPayload[24]; 
  sprintf(finalPayload, "%d;%s", esp_id, payload);

  Serial.print("Payload: ");
  Serial.println(finalPayload);
  
  client.publish(mqtt_topic, finalPayload);
  ///////
  float temperature = readTemperature();
  Serial.print("Temperature: ");
  Serial.println(temperature);
  char payload2[10];
  if (!isnan(temperature)) {
    dtostrf(temperature, 1, 2, payload2);
  }
  else {
    strcpy(payload2, "nan");
  }
  encryptData(payload2);
  char finalPayload2[16];
  sprintf(finalPayload2, "%d;%s", esp_id2, payload2);
  Serial.print("Payload: ");
  Serial.println(finalPayload2);
  client.publish(mqtt_topic2, finalPayload2);
  delay(10000); 
}
