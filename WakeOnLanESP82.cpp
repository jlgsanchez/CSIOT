#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>
#include <WiFiUdp.h>

//WiFiClient espClient;
WiFiClientSecure espClientSecure;
//PubSubClient client(espClient);
PubSubClient client(espClientSecure);
//const char* mqtt_server = "mqtt.armriot.com";
WiFiUDP Udp;

void reconnect();  // Declarar funcion
void callback(char* topic, byte* payload, unsigned int length);

void setup() {
  // put your setup code here, to run once:
  const char* mqtt_server = "mqtt.armriot.com";

  Serial.begin(115200);
  Serial.println("Hello, ESP8266!");
  pinMode(LED_BUILTIN, OUTPUT);     // Numero de pin, variable en este caso, y el modo, output.

  //WiFi.begin("munics", "BayernMunich");
  WiFi.begin("MIWIFI_vTZw", "Joseluis19112502");

  while (WiFi.status() != WL_CONNECTED) {
    Serial.print('.');
    delay(500);
  }
  Serial.println();
  Serial.print("connected, Mac address=");
  Serial.println(WiFi.macAddress());
  Serial.print("connected, Ip address=");
  Serial.println(WiFi.localIP());


  const uint8_t mqttCertFingerprint[] = {0xD7,0xFC,0xD6,0x8A,0xF7,0x6A,0xAA,0x06,0x8B,0x81,0x70,0xC4,0xC9,0x23,0xD0,0x92,0xFB,0x17,0x4E,0xF6};

  //espClientSecure.setInsecure();
  espClientSecure.setFingerprint(mqttCertFingerprint);

  client.setServer(mqtt_server, 8883);
  client.setCallback(callback);
}


  unsigned long blinkTimeStamp = 0;  // Marcas de tiempo para comprobar si ha pasado o no el tiempo
  int estadoLed = LOW;
  String swtch = "";

  unsigned int localPort = 9;      // local port to listen for UDP packets

  // Mac address of the device you want to wake up
  // byte mac[] = { 0xb8, 0x27, 0xeb, 0xa0, 0xe2, 0xc4 }; // RaspBerry
  byte mac[6] = { 0xd8, 0xbb, 0xc1, 0x96, 0x2c, 0xed }; // Mesa ether
  // byte mac[] = { 0x8c, 0x1d, 0x96, 0xda, 0xe2, 0x24 }; // Mesa Wifi

void sendWOL() {
    Serial.println("Sending WOL packet");

    byte WOLPacket[102];
    // for (int i = 0; i < 6; i++)
    //     WOLPacket[i] = 0xFF;
    // for (int i = 1; i <= 16; i++)
    //     for (int j = 0; j < 6; j++)
    //         WOLPacket[i * 6 + j] = mac[j];

    memset(WOLPacket, 0xFF, 6);
    for (int i = 0; i < 16; i++) {
      int ofs = i * sizeof(mac) + 6;
      memcpy(&WOLPacket[ofs], mac, sizeof(mac));
    }

    Udp.beginPacket(IPAddress(192, 168, 1, 255), localPort);
    Udp.write(WOLPacket, 102);
    Udp.endPacket();
    Serial.println("Sended WOL packet");
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // put your main code here, to run repeatedly:
  // Flag swtch para activar el blink del led
  if (millis() - blinkTimeStamp > 1000) {
    blinkTimeStamp = millis();
    if (estadoLed == LOW) {
      estadoLed = HIGH;
    } else {
      estadoLed = LOW;
    }
    digitalWrite(LED_BUILTIN, estadoLed);

    if ( swtch == "1"){
        if (Udp.begin(localPort) == 1) {
          Serial.println("Se puede enviar");
          sendWOL();
        }
        swtch = "0";
    }

    //client.publish("SlowHedgehog/jose-csiot-pruebas", (estadoLed == HIGH? "Estado Led Jose: OFF" : "Estado Led Jose: ON"));

  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print(topic);
  // Test: Mensaje
  Serial.print(": ");
  Serial.println(char(payload[0]));  // Primer caracter del mensaje [0]

  swtch = char(payload[0]); // recoger valor del switch de Node-Red y asignarlo 
}

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Create a random client ID
    String clientId = "Otro-";
    clientId += String(random(0xffff), HEX);
    // Attempt to connect
    if (client.connect(clientId.c_str(), "SlowHedgehog", "SlowHedgehog")) {
      Serial.println("connected");
      // Once connected, publish an announcement...
      //client.publish("SlowHedgehog/jose-csiot-pruebas", "Prueba MQTT");
      // ... and resubscribe
      client.subscribe("SlowHedgehog/control/input");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}


// PRUEBA LED BUILD IN

// void setup() {
//   // put your setup code here, to run once:
//   Serial.begin(115200);
//   Serial.println("Hello, ESP32!");
//   pinMode(LED_BUILTIN, OUTPUT);     // Numero de pin, variable en este caso, y el modo, output.
// }

// void loop() {
//   // put your main code here, to run repeatedly:
//   digitalWrite(LED_BUILTIN, HIGH);
//   delay(1000); // en milisegundos, 1 seg
//   digitalWrite(LED_BUILTIN, LOW);
//   delay(1000);
// }


