import os
import asyncio
import random
from azure.iot.device.aio import ProvisioningDeviceClient, IoTHubDeviceClient
from azure.iot.device import MethodResponse

ID_SCOPE = os.environ["ID_SCOPE"]
DEVICE_ID = os.environ["DEVICE_ID"]
PRIMARY_KEY = os.environ["PRIMARY_KEY"]

async def provision_device():
    provisioning_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host="global.azure-devices-provisioning.net",
        registration_id=DEVICE_ID,
        id_scope=ID_SCOPE,
        symmetric_key=PRIMARY_KEY,
    )
    return await provisioning_client.register()

import time
async def main():
    registration_result = await provision_device()
    device_client = IoTHubDeviceClient.create_from_symmetric_key(
        symmetric_key=PRIMARY_KEY,
        hostname=registration_result.registration_state.assigned_hub,
        device_id=DEVICE_ID,
    )
    await device_client.connect()
    print("Conectado a IoT Central desde la VM ✅")

    async def command_handler(method_request):
        print(f"Comando recibido: {method_request.name} -> {method_request.payload}")
        response = MethodResponse.create_from_method_request(method_request, 200, {"result": "ok"})
        await device_client.send_method_response(response)

    device_client.on_method_request_received = command_handler

    while True:
        timestamp = time.time()
        payload = {
            "HeartRate": random.randint(60, 100),
            "Temperature": round(random.uniform(36.0, 38.0), 2),
            "SPO2": random.randint(90, 100),
            "timestamp": timestamp
        }
        msg = str(payload).replace("'", '"')          # el JSON exacto que se envía
        print("Enviando telemetría:", msg)
        print(f"Payload size: {len(msg.encode('utf-8'))} bytes")
        await device_client.send_message(msg)
        await asyncio.sleep(5)

asyncio.run(main())
