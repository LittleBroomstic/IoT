#include <Arduino.h>
#include <SPI.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>

#define BME_CS   5
#define BME_SCK  18
#define BME_MISO 19
#define BME_MOSI 23

// WiFi credentials
const char* ssid = "StumilowyLas";
const char* password = "netlab123";

// MQTT broker settings
const int esp_id = 1;
const char* mqtt_server = "192.168.220.1";
const int mqtt_port = 1883;
const char* mqtt_topic = "esp32/humid";

// Encryption variables
int key = 2137;
int keylimiter = 69;

// BME680 object
Adafruit_BME680 bme(BME_CS);

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

    if (client.connect("ESP32_BME680_Client")) {

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

float readHumidity() {

  if (!bme.performReading()) {

    Serial.println("Read failed");
    return NAN;
  }

  return bme.humidity;
}

void setup() {

  Serial.begin(115200);

  delay(1000);

  SPI.begin(BME_SCK, BME_MISO, BME_MOSI, BME_CS);

  if (!bme.begin()) {

    Serial.println("BME680 not found!");

    while (1);
  }

  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setTemperatureOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_NONE);
  bme.setGasHeater(0, 0);

  setup_wifi();

  client.setServer(mqtt_server, mqtt_port);
}

void loop() {

  if (!client.connected()) {

    reconnect_mqtt();
  }

  client.loop();

  float humidity = readHumidity();

  if (!isnan(humidity)) {

    Serial.print("Humidity: ");
    Serial.print(humidity);
    Serial.println(" %");

    char payload[10];

    dtostrf(humidity, 1, 2, payload);

    encryptData(payload);

    Serial.print("Encrypted payload: ");
    Serial.println(payload);

    client.publish(mqtt_topic, payload);

  } else {

    Serial.println("Failed to read humidity");
  }

  delay(2000);
}
