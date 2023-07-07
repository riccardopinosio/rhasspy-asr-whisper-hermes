"""Command-line interface to rhasspyasr-asr-whisper-hermes"""
import argparse
import asyncio
import logging
import typing
import os

import paho.mqtt.client as mqtt
import rhasspyhermes.cli as hermes_cli
from rhasspysilence.const import SilenceMethod
from rhasspyasr import Transcriber, Transcription
import openai

from . import AsrHermesMqtt

_LOGGER = logging.getLogger("rhasspyasr_whisper_hermes")

# -----------------------------------------------------------------------------


def main():
    """Main method."""
    args = get_args()

    hermes_cli.setup_logging(args)
    _LOGGER.debug(args)

    run_mqtt(args)


# -----------------------------------------------------------------------------


def get_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(prog="rhasspy-asr-whisper-hermes")
    
    # openai
    parser.add_argument(
        "--openai-api-key",
        type=str,
        help="The openai api key to send requests to Whisper",
        default=os.getenv("OPENAI_API_KEY") # will attempt to read from environment vars
    )
    # Silence detection
    parser.add_argument(
        "--voice-skip-seconds",
        type=float,
        default=0.0,
        help="Seconds of audio to skip before a voice command",
    )
    parser.add_argument(
        "--voice-min-seconds",
        type=float,
        default=1.0,
        help="Minimum number of seconds for a voice command",
    )
    parser.add_argument(
        "--voice-max-seconds",
        type=float,
        help="Maximum number of seconds for a voice command",
    )
    parser.add_argument(
        "--voice-speech-seconds",
        type=float,
        default=0.3,
        help="Consecutive seconds of speech before start",
    )
    parser.add_argument(
        "--voice-silence-seconds",
        type=float,
        default=0.5,
        help="Consecutive seconds of silence before stop",
    )
    parser.add_argument(
        "--voice-before-seconds",
        type=float,
        default=0.5,
        help="Seconds to record before start",
    )
    parser.add_argument(
        "--voice-sensitivity",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="VAD sensitivity (1-3)",
    )
    parser.add_argument(
        "--voice-silence-method",
        choices=[e.value for e in SilenceMethod],
        default=SilenceMethod.VAD_ONLY,
        help="Method used to determine if an audio frame contains silence (see rhasspy-silence)",
    )
    parser.add_argument(
        "--voice-current-energy-threshold",
        type=float,
        help="Debiased energy threshold of current audio frame (see --voice-silence-method)",
    )
    parser.add_argument(
        "--voice-max-energy",
        type=float,
        help="Fixed maximum energy for ratio calculation (default: observed, see --voice-silence-method)",
    )
    parser.add_argument(
        "--voice-max-current-energy-ratio-threshold",
        type=float,
        help="Threshold of ratio between max energy and current audio frame (see --voice-silence-method)",
    )
    parser.add_argument("--lang", help="Set lang in hotword detected message")

    hermes_cli.add_hermes_args(parser)

    return parser.parse_args()


# -----------------------------------------------------------------------------


def run_mqtt(args: argparse.Namespace):
    """Runs Hermes ASR MQTT service."""
    openai_transcriber = WhisperTranscriber(args.openai_api_key)

    # Listen for messages
    client = mqtt.Client()
    hermes = AsrHermesMqtt(
        client,
        openai_transcriber,
        skip_seconds=args.voice_skip_seconds,
        min_seconds=args.voice_min_seconds,
        max_seconds=args.voice_max_seconds,
        speech_seconds=args.voice_speech_seconds,
        silence_seconds=args.voice_silence_seconds,
        before_seconds=args.voice_before_seconds,
        vad_mode=args.voice_sensitivity,
        silence_method=args.voice_silence_method,
        current_energy_threshold=args.voice_current_energy_threshold,
        max_energy=args.voice_max_energy,
        max_current_energy_ratio_threshold=args.voice_max_current_energy_ratio_threshold,
        site_ids=args.site_id,
        lang=args.lang,
    )

    _LOGGER.debug("Connecting to %s:%s", args.host, args.port)
    hermes_cli.connect(client, args)
    client.loop_start()

    try:
        # Run event loop
        asyncio.run(hermes.handle_messages_async())
    except KeyboardInterrupt:
        pass
    finally:
        _LOGGER.debug("Shutting down")
        client.loop_stop()


# -----------------------------------------------------------------------------

class WhisperTranscriber(Transcriber):
    
    def __init__(self, openai_api_key: str):
        if not openai_api_key:
            raise ValueError("OpenAI api key must be defined to send requests to Whisper.")
        self.openai_api_key = openai_api_key
    
    def transcribe_wav(self, wav_bytes: bytes) -> typing.Union[Transcription, None]:
        # TODO fix here
        with open("/tmp/audio.wav", "wb") as wf:
            wf.write(wav_bytes)
        with open("/tmp/audio.wav", "rb") as wf:
            whisper_transcription = openai.Audio.transcribe("whisper-1", wf)
        transcription = Transcription(
            text = whisper_transcription["text"],
            likelihood= 1,
            transcribe_seconds=0.5, # TODO change
            wav_seconds=0.5 # TODO change
        )
        print(transcription)
        return transcription
    
    def transcribe_stream(self, audio_stream: typing.Iterable[bytes], sample_rate: int, sample_width: int, channels: int) -> typing.Union[Transcription, None]:
        raise NotImplementedError()
    
    def stop(self):
        """Stop the transcriber"""


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()