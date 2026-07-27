import os
from typing import Any

import speech_recognition as sr  # type: ignore
import whisper  # type: ignore

# from PyStreamingTool.api.api import chat_with_LLM

model: Any = whisper.load_model("turbo")
recognizer = sr.Recognizer()
microphone = sr.Microphone()


def STT():
    """
    STT (Speech to text) é bastante literal
    """
    with microphone as source:  # Utilizando o microfone como fonte
        recognizer.adjust_for_ambient_noise(source, duration=2)  # Supressor de ruído
        audio_data = recognizer.listen(source)  # Escuta o microfone

    """Cria um arquivo temporário com o que foi capturado"""
    arquivo_temporario = "speech_recording.wav"
    with open(arquivo_temporario, "wb") as speech_file:
        speech_file.write(audio_data.get_wav_data())  # type: ignore

    try:
        transcript = model.transcribe(arquivo_temporario)
        texto_capturado = transcript["text"].strip()
        # linguagem_falada = transcript["language"]
        
    except (OSError, RuntimeError, ValueError) as err:
        print(err)
        texto_capturado = ""
    finally:
        """Indepedente de bem sucedido ao final exclua o arquivo temporário"""
        if os.path.exists(arquivo_temporario):
            os.remove(arquivo_temporario)

    return texto_capturado
