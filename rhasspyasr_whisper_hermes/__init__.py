"""Hermes MQTT server for Rhasspy ASR using openai Whisper API"""
import logging
import typing
from dataclasses import dataclass

from rhasspyasr import Transcriber
from rhasspyhermes.asr import (
    AsrAudioCaptured,
    AsrError,
    AsrRecordingFinished,
    AsrStartListening,
    AsrStopListening,
    AsrTextCaptured,
    AsrToggleOff,
    AsrToggleOn,
    AsrToggleReason
)
from rhasspyhermes.audioserver import AudioFrame, AudioSessionFrame
from rhasspyhermes.base import Message
from rhasspyhermes.client import GeneratorType, HermesClient
from rhasspyhermes.nlu import AsrToken, AsrTokenTime
from rhasspysilence.const import (
    SilenceMethod,
    VoiceCommandRecorder,
    VoiceCommandResult,
)
from rhasspysilence import WebRtcVadRecorder

_LOGGER = logging.getLogger("rhasspyasr_whisper_hermes")

# -----------------------------------------------------------------------------


@dataclass
class SessionInfo:
    """Information about an open session."""

    start_listening: AsrStartListening
    session_id: typing.Optional[str] = None
    recorder: typing.Optional[VoiceCommandRecorder] = None
    transcription_sent: bool = False
    num_wav_bytes: int = 0
    audio_buffer: typing.Optional[bytes] = None
    transcriber: typing.Optional[Transcriber] = None


# -----------------------------------------------------------------------------


class AsrHermesMqtt(HermesClient):
    """Hermes MQTT server for Rhasspy ASR using Whisper api."""

    def __init__(
        self,
        client,
        transcriber: Transcriber,
        site_ids: typing.Optional[typing.List[str]] = None,
        enabled: bool = True,
        sample_rate: int = 16000,
        sample_width: int = 2,
        channels: int = 1,
        make_recorder: typing.Callable[[], VoiceCommandRecorder] = None,
        skip_seconds: float = 0.0,
        min_seconds: float = 1.0,
        max_seconds: typing.Optional[float] = None,
        speech_seconds: float = 0.3,
        silence_seconds: float = 0.5,
        before_seconds: float = 0.5,
        vad_mode: int = 3,
        max_energy: typing.Optional[float] = None,
        max_current_energy_ratio_threshold: typing.Optional[float] = None,
        current_energy_threshold: typing.Optional[float] = None,
        silence_method: SilenceMethod = SilenceMethod.VAD_ONLY,
        lang: typing.Optional[str] = None,
    ):
        super().__init__(
            "rhasspyasr_whisper_hermes",
            client,
            site_ids=site_ids,
            sample_rate=sample_rate,
            sample_width=sample_width,
            channels=channels,
        )
        
        self.transcriber = transcriber

        self.subscribe(
            AsrToggleOn,
            AsrToggleOff,
            AsrStartListening,
            AsrStopListening,
            AudioFrame,
            AudioSessionFrame,
        )

        # True if ASR system is enabled
        self.enabled = enabled
        self.disabled_reasons: typing.Set[str] = set()

        self.lang = lang

        def default_recorder():
            return WebRtcVadRecorder(
                max_seconds=max_seconds,
                vad_mode=vad_mode,
                skip_seconds=skip_seconds,
                min_seconds=min_seconds,
                speech_seconds=speech_seconds,
                silence_seconds=silence_seconds,
                before_seconds=before_seconds,
                silence_method=silence_method,
                current_energy_threshold=current_energy_threshold,
                max_energy=max_energy,
                max_current_ratio_threshold=max_current_energy_ratio_threshold,
            )

        self.make_recorder = make_recorder or default_recorder

        # WAV buffers for each session
        self.sessions: typing.Dict[typing.Optional[str], SessionInfo] = {}

        self.first_audio: bool = True

    # -------------------------------------------------------------------------

    async def start_listening(self, message: AsrStartListening) -> None:
        """Start recording audio data for a session."""
        session = self.sessions.get(message.session_id)
        if not session:
            session = SessionInfo(
                session_id=message.session_id, start_listening=message
            )

            if message.stop_on_silence:
                # Use voice command recorder
                session.recorder = self.make_recorder()
            else:
                # Use buffer
                session.audio_buffer = bytes()

            self.sessions[message.session_id] = session

        # Start session
        assert session

        if session.recorder:
            session.recorder.start()

        _LOGGER.debug("Starting listening (session_id=%s)", message.session_id)
        self.first_audio = True

    async def stop_listening(
        self, message: AsrStopListening
    ) -> typing.AsyncIterable[
        typing.Union[
            AsrRecordingFinished,
            AsrTextCaptured,
            AsrError,
            typing.Tuple[AsrAudioCaptured, typing.Dict[str, typing.Any]],
        ]
    ]:
        """Stop recording audio data for a session."""
        try:
            session = self.sessions.pop(message.session_id, None)
            if session:
                # Stop session
                if session.recorder:
                    audio_data = session.recorder.stop()
                else:
                    assert session.audio_buffer is not None
                    audio_data = session.audio_buffer

                wav_bytes = self.to_wav_bytes(audio_data)

                _LOGGER.debug(
                    "Received a total of %s byte(s) for WAV data for session %s",
                    session.num_wav_bytes,
                    message.session_id,
                )

                if not session.transcription_sent:
                    # Send recording finished message
                    yield AsrRecordingFinished(
                        site_id=message.site_id, session_id=message.session_id
                    )

                    # Send transcription
                    session.transcription_sent = True

                    yield (
                        await self.transcribe(
                            wav_bytes,
                            transcriber=session.transcriber,
                            site_id=message.site_id,
                            session_id=message.session_id,
                            lang=(session.start_listening.lang or self.lang),
                        )
                    )

                    if session.start_listening.send_audio_captured:
                        # Send audio data
                        yield (
                            AsrAudioCaptured(wav_bytes=wav_bytes),
                            {
                                "site_id": message.site_id,
                                "session_id": message.session_id,
                            },
                        )

            _LOGGER.debug("Stopping listening (session_id=%s)", message.session_id)
        except Exception as e:
            _LOGGER.exception("stop_listening")
            yield AsrError(
                error=str(e),
                context=repr(self.transcriber),
                site_id=message.site_id,
                session_id=message.session_id,
            )

    async def handle_audio_frame(
        self,
        frame_wav_bytes: bytes,
        site_id: str = "default",
        session_id: typing.Optional[str] = None,
    ) -> typing.AsyncIterable[
        typing.Union[
            AsrRecordingFinished,
            AsrTextCaptured,
            AsrError,
            typing.Tuple[AsrAudioCaptured, typing.Dict[str, typing.Any]],
        ]
    ]:
        """Process single frame of WAV audio"""
        # Don't process audio if no sessions
        if not self.sessions:
            return

        audio_data = self.maybe_convert_wav(frame_wav_bytes)

        if session_id is None:
            # Add to every open session
            target_sessions = list(self.sessions.items())
        else:
            # Add to single session
            target_sessions = [(session_id, self.sessions[session_id])]

        # Add audio to session(s)
        for target_id, session in target_sessions:
            try:
                # Skip if site_id doesn't match
                if session.start_listening.site_id != site_id:
                    continue

                session.num_wav_bytes += len(frame_wav_bytes)
                if session.recorder:
                    # Check for end of voice command
                    command = session.recorder.process_chunk(audio_data)
                    if command and (command.result == VoiceCommandResult.SUCCESS):
                        assert command.audio_data is not None
                        _LOGGER.debug(
                            "Voice command recorded for session %s (%s byte(s))",
                            target_id,
                            len(command.audio_data),
                        )

                        # Send recording finished message
                        yield AsrRecordingFinished(
                            site_id=site_id, session_id=target_id
                        )

                        session.transcription_sent = True
                        wav_bytes = self.to_wav_bytes(command.audio_data)

                        yield (
                            await self.transcribe(
                                wav_bytes,
                                transcriber=session.transcriber,
                                site_id=site_id,
                                session_id=target_id,
                                lang=(session.start_listening.lang or self.lang),
                            )
                        )

                        if session.start_listening.send_audio_captured:
                            # Send audio data
                            yield (
                                AsrAudioCaptured(wav_bytes=wav_bytes),
                                {"site_id": site_id, "session_id": target_id},
                            )

                        # Reset session (but keep open)
                        session.recorder.stop()
                        session.recorder.start()
                else:
                    # Add to buffer
                    assert session.audio_buffer is not None
                    session.audio_buffer += audio_data
            except Exception as e:
                _LOGGER.exception("handle_audio_frame")
                yield AsrError(
                    error=str(e),
                    context=repr(self.transcriber),
                    site_id=site_id,
                    session_id=target_id,
                )

    async def transcribe(
        self,
        wav_bytes: bytes,
        site_id: str,
        transcriber: typing.Optional[Transcriber] = None,
        session_id: typing.Optional[str] = None,
        lang: typing.Optional[str] = None,
    ) -> AsrTextCaptured:
        """Transcribe audio data and publish captured text."""
        transcriber = transcriber or self.transcriber
        assert transcriber, "No transcriber"

        _LOGGER.debug("Transcribing %s byte(s) of audio data", len(wav_bytes))
        transcription = transcriber.transcribe_wav(wav_bytes)
        if transcription:
            _LOGGER.debug(transcription)
            asr_tokens: typing.Optional[typing.List[typing.List[AsrToken]]] = None

            if transcription.tokens:
                # Only one level of ASR tokens
                asr_inner_tokens: typing.List[AsrToken] = []
                asr_tokens = [asr_inner_tokens]
                range_start = 0
                for ps_token in transcription.tokens:
                    range_end = range_start + len(ps_token.token) + 1
                    asr_inner_tokens.append(
                        AsrToken(
                            value=ps_token.token,
                            confidence=ps_token.likelihood,
                            range_start=range_start,
                            range_end=range_start + len(ps_token.token) + 1,
                            time=AsrTokenTime(
                                start=ps_token.start_time, end=ps_token.end_time
                            ),
                        )
                    )

                    range_start = range_end

            # Actual transcription
            return AsrTextCaptured(
                text=transcription.text,
                likelihood=transcription.likelihood,
                seconds=transcription.transcribe_seconds,
                site_id=site_id,
                session_id=session_id,
                asr_tokens=asr_tokens,
                lang=lang,
            )

        _LOGGER.warning("Received empty transcription")
        return AsrTextCaptured(
            text="",
            likelihood=0,
            seconds=0,
            site_id=site_id,
            session_id=session_id,
            lang=lang,
        )


    # -------------------------------------------------------------------------

    async def on_message_blocking(
        self,
        message: Message,
        site_id: typing.Optional[str] = None,
        session_id: typing.Optional[str] = None,
        topic: typing.Optional[str] = None,
    ) -> GeneratorType:
        """Received message from MQTT broker (blocking)."""
        # Check enable/disable messages
        if isinstance(message, AsrToggleOn):
            if message.reason == AsrToggleReason.UNKNOWN:
                # Always enable on unknown
                self.disabled_reasons.clear()
            else:
                self.disabled_reasons.discard(message.reason)

            if self.disabled_reasons:
                _LOGGER.debug("Still disabled: %s", self.disabled_reasons)
            else:
                self.enabled = True
                self.first_audio = True
                _LOGGER.debug("Enabled")
        elif isinstance(message, AsrToggleOff):
            self.enabled = False
            self.disabled_reasons.add(message.reason)
            _LOGGER.debug("Disabled")
        elif isinstance(message, AudioFrame):
            if self.enabled:
                assert site_id, "Missing site_id"
                if self.first_audio:
                    _LOGGER.debug("Receiving audio")
                    self.first_audio = False

                # Add to all active sessions
                async for frame_result in self.handle_audio_frame(
                    message.wav_bytes, site_id=site_id
                ):
                    yield frame_result
        elif isinstance(message, AudioSessionFrame):
            if self.enabled:
                assert site_id and session_id, "Missing site_id or session_id"
                if session_id in self.sessions:
                    if self.first_audio:
                        _LOGGER.debug("Receiving audio")
                        self.first_audio = False

                    # Add to specific session only
                    async for session_frame_result in self.handle_audio_frame(
                        message.wav_bytes, site_id=site_id, session_id=session_id
                    ):
                        yield session_frame_result
        elif isinstance(message, AsrStartListening):
            # Handle blocking
            await self.start_listening(message)
        elif isinstance(message, AsrStopListening):
            # hermes/asr/stopListening
            async for stop_result in self.stop_listening(message):
                yield stop_result
        else:
            _LOGGER.warning("Unexpected message: %s", message)