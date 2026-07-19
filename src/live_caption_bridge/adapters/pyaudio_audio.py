import pyaudio


def list_devices() -> list[dict[str, str]]:
    p = pyaudio.PyAudio()
    devices: list[dict[str, str]] = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if int(info["maxInputChannels"]) > 0:
            devices.append({"name": str(info["name"]), "id": str(i)})
    p.terminate()
    return devices


if __name__ == "__main__":
    for dev in list_devices():
        print(dev["name"], dev["id"])
