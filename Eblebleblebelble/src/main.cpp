#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>

#define TMP102_ADDR 0x48

// WiFi credentials
const char* ssid = "StumilowyLas";
const char* password = "netlab123";

const int esp_id = 1;
// MQTT broker settings
const char* mqtt_server = "192.168.220.1"; // e.g. Mosquitto broker IP
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32/temp";

int key = 2137;
int keylimiter = 69;

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

    if (client.connect("ESP32_TMP102_Client")) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5 seconds");
      delay(5000);
    }
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

void setup() {
  Serial.begin(115200);
  Wire.begin();

  setup_wifi();

  client.setServer(mqtt_server, mqtt_port);
}
void encryptData(char * payload)
{
      for(int i = 0 ; payload[i] != '\0' ; i++){
      payload[i] = (char)((int)payload[i] + key%keylimiter);
    }

}
void loop() {
  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  float temperature = readTemperature();

  if (!isnan(temperature)) {
    Serial.print("Temperature: ");
    Serial.println(temperature);
    char payload[10];
    dtostrf(temperature, 1, 2, payload);
    encryptData(payload);
    String tempText = esp_id.ToString();
    payload = tempText + ";" + payload;
    Serial.println(payload);
    client.publish(mqtt_topic, payload);
  } else {
    Serial.println("Failed to read temperature");
  }

  delay(1000);
}
