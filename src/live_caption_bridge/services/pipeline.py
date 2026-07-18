from live_caption_bridge.domain.models import AudioChunk, Caption
from live_caption_bridge.ports.caption_sink import CaptionSink
from live_caption_bridge.ports.speech import SpeechPort


class Pipeline:
        def __init__(self, stt: SpeechPort, sink: CaptionSink, source_lang: str = "pt") -> None:
            self._stt = stt
            self._sink = sink
            self._source_lang = source_lang
        
        def process(self, chunk: AudioChunk) -> None:
            seg = self._stt.transcribe(chunk) # type: ignore
            if not seg.text: # type: ignore
                return
            caption = Caption(
                original=seg.text, # type: ignore
                translated=seg.text, # type: ignore
                source_lang=seg.language or self._source_lang, # type: ignore
                target_lang=seg.language or self._source_lang, # type: ignore
                started_ns=seg.start_ns, # type: ignore
                ended_ns=seg.end_ns, # type: ignore
            )
            self._sink.publish(caption)