# Laboratorio3_IoT
# Laboratorio 3 — MQTT explícito con Azure IoT
## Descripción

Este laboratorio implementa la comunicación de un dispositivo con Azure IoT Central / Azure IoT Hub utilizando MQTT de forma explícita, sin delegar la generación del token SAS en un SDK de IoT.

La principal diferencia respecto a una implementación basada en SDK es que en este laboratorio el proceso de autenticación se realiza manualmente:

Se obtiene el Device ID, ID Scope y Device Key.
Se construye el resource URI.
Se calcula la firma mediante HMAC-SHA256.
La firma se codifica en Base64.
La firma se codifica para utilizarla dentro de una URL.
Se construye manualmente el Shared Access Signature (SAS).
El SAS se utiliza como contraseña en la conexión MQTT.
El dispositivo se conecta mediante MQTT sobre TLS al puerto 8883.
Finalmente se publica la telemetría.

## 1. Arquitectura de conexión

El flujo general utilizado es:

ESP32 / Python
      │
      │ MQTT + TLS
      │
      ▼
Azure Device Provisioning Service (DPS)
      │
      │ Asignación
      ▼
Azure IoT Hub
      │
      ▼
Azure IoT Central

En el caso del ESP32 con Wokwi, el dispositivo primero se conecta a DPS para obtener el IoT Hub asignado.

Posteriormente se genera otro SAS para autenticarse contra el IoT Hub.

## 2. Datos necesarios

Para realizar la conexión se necesitan:

* Parámetro      Descripción
* ID_SCOPE	ID Scope de la aplicación/dispositivo en Azure IoT Central
* REGISTRATION_ID	ID de registro del dispositivo
* DEVICE_ID	Identificador del dispositivo
* DEVICE_KEY	Clave primaria del dispositivo
* DPS_HOST	Hostname del servicio DPS
* DPS_PORT	Puerto MQTT de DPS
* HUB	Hostname del IoT Hub asignado por DPS
* HUB_PORT	Puerto MQTT del IoT Hub


## 3. ¿Qué es el SAS?

Azure utiliza un Shared Access Signature (SAS) para autenticar el dispositivo.

Conceptualmente, el token tiene una estructura similar a:

SharedAccessSignature sr=<resource-uri>&sig=<firma>&se=<expiracion>

Donde:

sr = recurso al que se tiene acceso.
sig = firma HMAC-SHA256 codificada.
se = tiempo de expiración del token.

En el caso de DPS también se utiliza:

skn=registration

para indicar que el token corresponde al proceso de registro.

## 4. Generación manual del SAS

La generación manual sigue estos pasos:

DEVICE_KEY
     │
     ▼
Base64 Decode
     │
     ▼
Clave binaria
     │
     │ HMAC-SHA256
     ▼
Firma
     │
     ▼
Base64 Encode
     │
     ▼
URL Encode
     │
     ▼
SAS Token
## 5. Generación del SAS para DPS

Para DPS, el recurso se construye utilizando:

<ID_SCOPE>/registrations/<REGISTRATION_ID>

Por ejemplo, conceptualmente:

resource_uri = (
    ID_SCOPE.lower()
    + "/registrations/"
    + REGISTRATION_ID.lower()
)

Después se genera el SAS:

expiry = int(time.time()) + 3600

dps_sas = create_sas(
    resource_uri,
    DEVICE_KEY,
    expiry
)

## 6. Conexión MQTT con DPS

Una vez generado manualmente el SAS, se utiliza como contraseña de MQTT.

Ejemplo:

from umqtt.simple import MQTTClient

client = MQTTClient(
    REGISTRATION_ID,
    DPS_HOST,
    user=username,
    password=dps_sas,
    port=8883,
    ssl=True
)

client.connect()

Los parámetros importantes son:

Hostname: global.azure-devices-provisioning.net
Puerto:   8883
TLS:      Sí

El uso de:

ssl=True

indica que MQTT se ejecuta sobre una conexión TLS.

## 7. Registro del dispositivo en DPS

Después de establecer la conexión MQTT, se publica una solicitud en:

$dps/registrations/PUT/iotdps-register/?$rid=1

con un payload similar a:

{
    "registrationId": "mi-dispositivo"
}

DPS responde indicando el estado del proceso de aprovisionamiento.

El dispositivo consulta posteriormente el estado mediante:

$dps/registrations/GET/iotdps-get-operationstatus/

Cuando el estado es:

assigned

DPS proporciona el hostname del IoT Hub asignado.

## 8. Generación del SAS para IoT Hub

Una vez obtenido el IoT Hub, el recurso cambia.

Para IoT Hub se utiliza:

<HUB>/devices/<DEVICE_ID>

Por ejemplo:

resource_uri = (
    hub
    + "/devices/"
    + DEVICE_ID
)

Se genera un nuevo SAS:

expiry = int(time.time()) + 3600

sas_hub = create_sas(
    resource_uri,
    DEVICE_KEY,
    expiry
)

El username utilizado para MQTT tiene la forma:

<HUB>/<DEVICE_ID>/?api-version=2021-04-12

## 9. Conexión MQTT explícita al IoT Hub

Finalmente se crea el cliente MQTT:

client = MQTTClient(
    DEVICE_ID,
    hub,
    user=username_hub,
    password=sas_hub,
    port=8883,
    ssl=True
)

client.connect()

De esta manera:

MQTT
 +
TLS
 +
SAS generado manualmente
 +
Azure IoT Hub

## 10. Publicación de telemetría

El topic utilizado para enviar telemetría es:

devices/<DEVICE_ID>/messages/events/

Ejemplo:

payload = json.dumps(
    {
        "Temperature": 85.3,
        "BreathRate": 18,
        "HeartRate": 75
    }
)

topic = (
    "devices/"
    + DEVICE_ID
    + "/messages/events/"
)

client.publish(
    topic.encode(),
    payload.encode()
)

## 11. Intervalo de publicación

Para publicar periódicamente se puede utilizar:

TELEMETRY_INTERVAL = 10

y posteriormente:

if now - last_telemetry >= TELEMETRY_INTERVAL:
    send_telemetry()
    last_telemetry = now

En este caso la telemetría se publica aproximadamente cada:

10 segundos

## 12. Resumen de la práctica

La implementación de MQTT explícito permite observar directamente el proceso:

                 DEVICE KEY
                     │
                     ▼
              Base64 Decode
                     │
                     ▼
                HMAC-SHA256
                     │
                     ▼
              Base64 Encode
                     │
                     ▼
                URL Encode
                     │
                     ▼
                  SAS
                     │
                     ▼
              MQTT + TLS 8883
                     │
                     ▼
                   DPS
                     │
                     ▼
              IoT Hub asignado
                     │
                     ▼
          Nuevo SAS para IoT Hub
                     │
                     ▼
              MQTT + TLS 8883
                     │
                     ▼
                Telemetría
                     │
                     ▼
              Azure IoT Central

De esta forma, el laboratorio demuestra la diferencia entre realizar explícitamente el proceso de autenticación y conexión mediante MQTT y utilizar un SDK que abstrae dichos mecanismos.
