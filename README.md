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

Importante: este proyecto no contiene claves reales. Los valores sensibles deben proporcionarse mediante variables de entorno o un archivo local que no se suba al repositorio.

1. Arquitectura de conexión

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

2. Datos necesarios

Para realizar la conexión se necesitan:

Parámetro	Descripción
ID_SCOPE	ID Scope de la aplicación/dispositivo en Azure IoT Central
REGISTRATION_ID	ID de registro del dispositivo
DEVICE_ID	Identificador del dispositivo
DEVICE_KEY	Clave primaria del dispositivo
DPS_HOST	Hostname del servicio DPS
DPS_PORT	Puerto MQTT de DPS
HUB	Hostname del IoT Hub asignado por DPS
HUB_PORT	Puerto MQTT del IoT Hub

Ejemplo:

ID_SCOPE=0neXXXXXXXX
REGISTRATION_ID=mi-dispositivo
DEVICE_ID=mi-dispositivo
DEVICE_KEY=<CLAVE_SECRETA>
DPS_HOST=global.azure-devices-provisioning.net
DPS_PORT=8883
HUB_PORT=8883

Nunca subir DEVICE_KEY al repositorio.

3. ¿Qué es el SAS?

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

4. Generación manual del SAS

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

La clave del dispositivo no se utiliza directamente como texto para HMAC. Primero debe decodificarse desde Base64.

5. Función HMAC-SHA256

En Python se puede utilizar la biblioteca estándar:

import hmac
import hashlib
import base64
import urllib.parse

La función puede implementarse así:

def create_sas(resource_uri, device_key, expiry):
    encoded_resource_uri = urllib.parse.quote(
        resource_uri,
        safe=""
    )

    string_to_sign = (
        encoded_resource_uri
        + "\n"
        + str(expiry)
    )

    key = base64.b64decode(device_key)

    signature = hmac.new(
        key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256
    ).digest()

    signature = base64.b64encode(
        signature
    ).decode()

    signature = urllib.parse.quote(
        signature,
        safe=""
    )

    sas = (
        "SharedAccessSignature "
        + "sr=" + encoded_resource_uri
        + "&sig=" + signature
        + "&se=" + str(expiry)
    )

    return sas

Esta función genera el SAS de forma explícita, en lugar de permitir que un SDK realice internamente la operación.

6. Generación del SAS para DPS

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

El usuario MQTT de DPS tiene la forma:

<ID_SCOPE>/registrations/<REGISTRATION_ID>/api-version=2019-03-31
7. Conexión MQTT con DPS

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

8. Registro del dispositivo en DPS

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

9. Generación del SAS para IoT Hub

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
10. Conexión MQTT explícita al IoT Hub

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
11. Publicación de telemetría

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
12. Medición del tamaño del payload

Para obtener el tamaño real del payload en bytes:

print(
    "Payload size:",
    len(payload.encode("utf-8")),
    "bytes"
)

Es importante utilizar:

len(payload.encode("utf-8"))

y no solamente:

len(payload)

porque len(payload) mide caracteres mientras que len(payload.encode("utf-8")) mide los bytes que serán enviados.

13. Timestamp de la telemetría

También se puede agregar un timestamp al mensaje:

timestamp = time.time()

Por ejemplo:

payload = json.dumps(
    {
        "Temperature": 85.3,
        "BreathRate": 18,
        "HeartRate": 75,
        "timestamp": timestamp
    }
)

Y mostrarlo:

print("Timestamp:", timestamp)

Esto permite identificar el momento en que se generó/envió cada mensaje.

14. Intervalo de publicación

Para publicar periódicamente se puede utilizar:

TELEMETRY_INTERVAL = 10

y posteriormente:

if now - last_telemetry >= TELEMETRY_INTERVAL:
    send_telemetry()
    last_telemetry = now

En este caso la telemetría se publica aproximadamente cada:

10 segundos
15. Diferencia frente al SDK
MQTT explícito

En este laboratorio, el programa controla directamente:

HMAC-SHA256
       ↓
Base64
       ↓
URL Encoding
       ↓
SAS
       ↓
MQTT username/password
       ↓
TLS
       ↓
MQTT publish

El código permite observar directamente cómo se construye el mecanismo de autenticación.

SDK

Con un SDK, normalmente se proporciona:

Device ID
ID Scope
Device Key
        ↓
      SDK
        ↓
Generación/autenticación
        ↓
Conexión MQTT
        ↓
Telemetría

La generación del SAS y otros detalles de autenticación quedan encapsulados dentro de la biblioteca.

Por esta razón, ambos métodos pueden utilizar el mismo mecanismo de autenticación de Azure, pero el nivel de abstracción es diferente.

16. Seguridad de credenciales

No colocar nunca en Git:

DEVICE_KEY = "clave-real"

Tampoco colocar:

DEVICE_KEY=clave-real

en un archivo que vaya a ser subido al repositorio.

Usar variables de entorno

En Python se puede utilizar:

import os

ID_SCOPE = os.environ["AZURE_ID_SCOPE"]
DEVICE_ID = os.environ["AZURE_DEVICE_ID"]
DEVICE_KEY = os.environ["AZURE_DEVICE_KEY"]

Antes de ejecutar el programa:

Windows PowerShell
$env:AZURE_ID_SCOPE="tu-id-scope"
$env:AZURE_DEVICE_ID="tu-device-id"
$env:AZURE_DEVICE_KEY="tu-device-key"
Linux / Ubuntu
export AZURE_ID_SCOPE="tu-id-scope"
export AZURE_DEVICE_ID="tu-device-id"
export AZURE_DEVICE_KEY="tu-device-key"

El código puede entonces obtener las credenciales sin almacenarlas directamente.

17. Archivo .gitignore

Se recomienda crear un archivo:

.gitignore

con:

.env
*.key
secrets.py
config_secrets.py
__pycache__/

Si se utiliza un archivo .env:

.env

debe permanecer fuera del repositorio.

18. Resumen de la práctica

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
