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


def list_output_devices() -> list[dict[str, str]]:
    p = pyaudio.PyAudio()
    devices: list[dict[str, str]] = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if int(info["maxOutputChannels"]) > 0 and int(info["maxInputChannels"]) == 0:
            devices.append({"name": str(info["name"]), "id": str(i)})
    p.terminate()
    return devices


def default_device_ids() -> dict[str, int | None]:
    p = pyaudio.PyAudio()
    try:
        default_input = p.get_default_input_device_info()
        in_id: int | None = int(default_input["index"])
    except OSError:
        in_id = None
    try:
        default_output = p.get_default_output_device_info()
        out_id: int | None = int(default_output["index"])
    except OSError:
        out_id = None
    p.terminate()
    return {"input": in_id, "output": out_id}


if __name__ == "__main__":
    for dev in list_devices():
        print(f"I {dev['name']} ({dev['id']})")
    for dev in list_output_devices():
        print(f"O {dev['name']} ({dev['id']})")
    print(f"Default: {default_device_ids()}")
