
import network
import time
import ntptime
import hashlib
import ubinascii
import json
from machine import Pin
from umqtt.simple import MQTTClient
#Temperature

# ============================================================
# CONFIGURACION
# ============================================================

WIFI_SSID = "Wokwi-GUEST"
WIFI_PASSWORD = ""

ID_SCOPE = "0ne00FE096E"
REGISTRATION_ID = "65sxptcib"

DEVICE_ID = "65sxptcib"

DEVICE_KEY = "SQ+GkoQEzXO4HQ01JOVAeFsa+C/AC3UclNMrwluQUEI="

DPS_HOST = "global.azure-devices-provisioning.net"

DPS_PORT = 8883
HUB_PORT = 8883

LED_PIN = 2

TELEMETRY_INTERVAL = 10


# ============================================================
# LED
# ============================================================

led = Pin(LED_PIN, Pin.OUT)
led.value(0)


# ============================================================
# HMAC-SHA256
# ============================================================

def hmac_sha256(key, message):

    block_size = 64

    if len(key) > block_size:
        key = hashlib.sha256(key).digest()

    if len(key) < block_size:
        key += b"\x00" * (block_size - len(key))

    o_key_pad = bytes((x ^ 0x5c) for x in key)
    i_key_pad = bytes((x ^ 0x36) for x in key)

    inner = hashlib.sha256(
        i_key_pad + message
    ).digest()

    return hashlib.sha256(
        o_key_pad + inner
    ).digest()


# ============================================================
# URL ENCODING
# ============================================================

def url_encode(value):

    safe = b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~"

    result = ""

    for byte in value:

        if byte in safe:
            result += chr(byte)

        else:
            result += "%" + "{:02x}".format(byte)

    return result


# ============================================================
# SAS PARA DPS
# ============================================================

def create_dps_sas(id_scope, registration_id, device_key, expiry):

    resource_uri = (
        id_scope.lower()
        + "/registrations/"
        + registration_id.lower()
    )

    encoded_resource_uri = url_encode(
        resource_uri.encode()
    )

    string_to_sign = (
        encoded_resource_uri
        + "\n"
        + str(expiry)
    )

    key = ubinascii.a2b_base64(
        device_key
    )

    signature = hmac_sha256(
        key,
        string_to_sign.encode()
    )

    signature = ubinascii.b2a_base64(
        signature
    ).decode().strip()

    signature = url_encode(
        signature.encode()
    )

    token = (
        "SharedAccessSignature "
        + "sr=" + encoded_resource_uri
        + "&sig=" + signature
        + "&se=" + str(expiry)
        + "&skn=registration"
    )

    return token


# ============================================================
# SAS PARA IOT HUB
# ============================================================

def create_hub_sas(hub, device_id, device_key, expiry):

    resource_uri = (
        hub
        + "/devices/"
        + device_id
    )

    encoded_resource_uri = url_encode(
        resource_uri.encode()
    )

    string_to_sign = (
        encoded_resource_uri
        + "\n"
        + str(expiry)
    )

    key = ubinascii.a2b_base64(
        device_key
    )

    signature = hmac_sha256(
        key,
        string_to_sign.encode()
    )

    signature = ubinascii.b2a_base64(
        signature
    ).decode().strip()

    signature = url_encode(
        signature.encode()
    )

    return (
        "SharedAccessSignature "
        + "sr=" + encoded_resource_uri
        + "&sig=" + signature
        + "&se=" + str(expiry)
    )


# ============================================================
# WIFI
# ============================================================

def connect_wifi():

    print("Conectando a Wi-Fi...")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():

        wlan.connect(
            WIFI_SSID,
            WIFI_PASSWORD
        )

        timeout = 20

        while not wlan.isconnected() and timeout > 0:

            time.sleep(1)
            timeout -= 1

            print(".", end="")

    print()

    if not wlan.isconnected():

        print("ERROR: no se pudo conectar a Wi-Fi")

        raise Exception(
            "Wi-Fi failed"
        )

    print("Wi-Fi conectado")
    print("IP:", wlan.ifconfig()[0])

    return wlan


# ============================================================
# NTP
# ============================================================

def synchronize_time():

    print("Sincronizando hora...")

    for attempt in range(5):

        try:

            ntptime.settime()

            unix_time = (
                time.time()
                + 946684800
            )

            print(
                "Hora sincronizada:",
                time.gmtime(unix_time)
            )

            return

        except Exception as e:

            print(
                "Error NTP:",
                e
            )

            time.sleep(2)

    raise Exception(
        "NTP failed"
    )


# ============================================================
# DPS
# ============================================================

dps_messages = []


def dps_callback(topic, msg):

    print(
        "DPS:",
        topic,
        msg
    )

    dps_messages.append(
        (topic, msg)
    )


def connect_dps():

    print()
    print("================================")
    print("CONECTANDO A DPS")
    print("================================")

    expiry = int(
        time.time()
        + 946684800
        + 3600
    )

    dps_sas = create_dps_sas(
        ID_SCOPE,
        REGISTRATION_ID,
        DEVICE_KEY,
        expiry
    )

    username = (
        ID_SCOPE
        + "/registrations/"
        + REGISTRATION_ID
        + "/api-version=2019-03-31"
    )

    client = MQTTClient(
        REGISTRATION_ID,
        DPS_HOST,
        user=username,
        password=dps_sas,
        port=DPS_PORT,
        ssl=True
    )

    client.set_callback(
        dps_callback
    )

    print("Conectando MQTT DPS...")

    client.connect()

    print("DPS conectado")

    client.subscribe(
        b"$dps/registrations/res/#"
    )

    request_id = "1"

    topic = (
        "$dps/registrations/PUT/"
        "iotdps-register/?$rid="
        + request_id
    )

    payload = (
        '{"registrationId":"'
        + REGISTRATION_ID
        + '"}'
    )

    print("Registrando dispositivo...")

    client.publish(
        topic.encode(),
        payload.encode()
    )

    operation_id = None

    start = time.time()

    while operation_id is None:

        client.check_msg()

        for topic, msg in dps_messages:

            try:

                data = json.loads(
                    msg.decode()
                )

                if "operationId" in data:

                    operation_id = data[
                        "operationId"
                    ]

                    print(
                        "Operation ID:",
                        operation_id
                    )

                    break

            except Exception:
                pass

        if time.time() - start > 30:

            client.disconnect()

            raise Exception(
                "DPS registration timeout"
            )

        time.sleep(1)

    dps_messages.clear()

    # --------------------------------------------------------
    # Polling
    # --------------------------------------------------------

    print(
        "Esperando asignacion del IoT Hub..."
    )

    assigned_hub = None

    start = time.time()

    while assigned_hub is None:

        request_id = "2"

        topic = (
            "$dps/registrations/GET/"
            "iotdps-get-operationstatus/"
            "?$rid="
            + request_id
            + "&operationId="
            + operation_id
        )

        client.publish(
            topic.encode(),
            b""
        )

        for _ in range(10):

            client.check_msg()

            for topic2, msg in dps_messages:

                try:

                    data = json.loads(
                        msg.decode()
                    )

                    status = data.get(
                        "status"
                    )

                    print(
                        "DPS status:",
                        status
                    )

                    if status == "assigned":

                        registration_state = data.get(
                            "registrationState",
                            {}
                        )

                        assigned_hub = registration_state.get(
                            "assignedHub"
                        )

                        if assigned_hub:

                            break

                    elif status == "failed":

                        client.disconnect()

                        raise Exception(
                            "DPS assignment failed"
                        )

                except Exception:
                    pass

            dps_messages.clear()

            if assigned_hub:
                break

            time.sleep(1)

        if time.time() - start > 60:

            client.disconnect()

            raise Exception(
                "DPS assignment timeout"
            )

    print()
    print(
        "IoT Hub asignado:"
    )
    print(
        assigned_hub
    )

    client.disconnect()

    print(
        "DPS desconectado"
    )

    return assigned_hub


# ============================================================
# COMANDOS DE IOT CENTRAL
# ============================================================

def handle_command(topic, msg):

    print()
    print("================================")
    print("COMANDO RECIBIDO")
    print("================================")

    print(
        "Topic:",
        topic
    )

    print(
        "Payload:",
        msg
    )

    topic_text = topic.decode()

    # Ejemplo:
    # $iothub/methods/POST/setAlertLed/?$rid=1

    if "/setAlertLed/" not in topic_text:

        print(
            "Comando desconocido"
        )

        return

    # --------------------------------------------------------
    # Obtener request ID
    # --------------------------------------------------------

    request_id = "1"

    if "?$rid=" in topic_text:

        request_id = topic_text.split(
            "?$rid="
        )[1]

    # --------------------------------------------------------
    # Interpretar payload
    # --------------------------------------------------------

    state = None

    try:

        data = json.loads(
            msg.decode()
        )

        print(
            "JSON del comando:",
            data
        )

        # Intentamos varios nombres posibles
        # para hacer el programa tolerante.

        if isinstance(data, dict):

            if "value" in data:
                state = data["value"]

            elif "state" in data:
                state = data["state"]

            elif "enabled" in data:
                state = data["enabled"]

            elif "alert" in data:
                state = data["alert"]

        elif isinstance(data, bool):

            state = data

    except Exception as e:

        print(
            "Payload no JSON:",
            e
        )

        text = msg.decode().lower()

        if text == "true":
            state = True

        elif text == "false":
            state = False

        elif text == "1":
            state = True

        elif text == "0":
            state = False

    # --------------------------------------------------------
    # Control LED
    # --------------------------------------------------------

    if state is None:

        # Si el comando no tiene parametro,
        # simplemente alternamos el LED.

        state = not bool(
            led.value()
        )

    if state:

        led.value(1)

        print(
            "LED ALERTA: ENCENDIDO"
        )

    else:

        led.value(0)

        print(
            "LED ALERTA: APAGADO"
        )

    # --------------------------------------------------------
    # Respuesta al comando
    # --------------------------------------------------------

    response_topic = (
        "$iothub/methods/res/200/?$rid="
        + request_id
    )

    response_payload = json.dumps(
        {
            "status": 200,
            "payload": {
                "led": bool(
                    led.value()
                )
            }
        }
    )

    client.publish(
        response_topic.encode(),
        response_payload.encode()
    )

    print(
        "Respuesta enviada a IoT Central"
    )


# ============================================================
# CALLBACK IOT HUB
# ============================================================

def hub_callback(topic, msg):

    topic_text = topic.decode()

    if "/methods/POST/" in topic_text:

        handle_command(
            topic,
            msg
        )

    else:

        print(
            "Mensaje recibido:",
            topic,
            msg
        )


# ============================================================
# CONECTAR IOT HUB
# ============================================================

def connect_hub(hub):

    print()
    print("================================")
    print("CONECTANDO A IOT HUB")
    print("================================")

    expiry = int(
        time.time()
        + 946684800
        + 3600
    )

    sas_hub = create_hub_sas(
        hub,
        DEVICE_ID,
        DEVICE_KEY,
        expiry
    )

    username_hub = (
        hub
        + "/"
        + DEVICE_ID
        + "/?api-version=2021-04-12"
    )

    client = MQTTClient(
        DEVICE_ID,
        hub,
        user=username_hub,
        password=sas_hub,
        port=HUB_PORT,
        ssl=True
    )

    client.set_callback(
        hub_callback
    )

    print(
        "Conectando MQTT..."
    )

    client.connect()

    print(
        "IoT Hub conectado"
    )

    # --------------------------------------------------------
    # Suscripción a comandos
    # --------------------------------------------------------

    client.subscribe(
        b"$iothub/methods/POST/#"
    )

    print(
        "Escuchando comandos de IoT Central"
    )

    return client


# ============================================================
# TELEMETRIA
# ============================================================
QOS_LEVEL=1

def send_telemetry():
    timestamp = time.time() + 946684800
    payload = json.dumps(
        {
            "Temperature": 85.3,
            "BreathRate": 18,
            "HeartRate": 75,
            "timestamp": timestamp,
            #"alertLed": bool(
            #    led.value()
            #)
        }
    )

    topic = (
        "devices/"
        + DEVICE_ID
        + "/messages/events/"
    )

    client.publish(
        topic.encode(),
        payload.encode(),
        qos=QOS_LEVEL
    )

    print(
        "Telemetria enviada:",
        payload,
        "Tamaño del payload = ", len(payload.encode()),

    )


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

print()
print("================================")
print("ESP32 - AZURE IOT CENTRAL")
print("================================")

try:

    # 1. Wi-Fi
    connect_wifi()

    # 2. NTP
    synchronize_time()

    # 3. DPS
    HUB = connect_dps()

    # 4. IoT Hub
    client = connect_hub(
        HUB
    )

    print()
    print("================================")
    print("SISTEMA LISTO")
    print("================================")

    # --------------------------------------------------------
    # Bucle principal
    # --------------------------------------------------------

    last_telemetry = 0

    while True:

        # Revisar comandos provenientes
        # de Azure IoT Central.
        client.check_msg()

        # Telemetria periódica.
        now = time.time()

        if now - last_telemetry >= TELEMETRY_INTERVAL:

            send_telemetry()

            last_telemetry = now

        time.sleep(1)


except Exception as e:

    print()
    print("================================")
    print("ERROR")
    print("================================")

    print(
        e
    )

    print(
        "El programa se detuvo."
    )

#17e8847a84636888af5a7abe0910e50a0fa28d6f1d3591a175e6e01fcf80b41
#send_telemetry
#DEVICE KEY = SQ+GkoQEzXO4HQ01JOVAeFsa+C/AC3UclNMrwluQUEI=