"""
Custom ElevenLabs TTS using HTTP API instead of WebSocket.
This bypasses Railway's websocket issues with ElevenLabs.
"""

import asyncio
import aiohttp
from livekit.agents import tts


class ElevenLabsHTTP(tts.TTS):
    """ElevenLabs TTS using REST API instead of WebSocket streaming."""

    def __init__(
        self,
        api_key: str,
        voice_id: str = "EXAVITQu4vr4xnSDxMaL",  # Sarah
        model: str = "eleven_multilingual_v2",
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
        )
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model

    def synthesize(self, text: str, *, conn_options=None, **kwargs) -> "ChunkedStream":
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            api_key=self._api_key,
            voice_id=self._voice_id,
            model=self._model,
        )


class ChunkedStream(tts.ChunkedStream):
    """Stream audio chunks from ElevenLabs HTTP API."""

    def __init__(
        self,
        *,
        tts: ElevenLabsHTTP,
        input_text: str,
        conn_options,
        api_key: str,
        voice_id: str,
        model: str,
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model

    async def _run(self, output_emitter=None) -> None:
        """Fetch audio from ElevenLabs HTTP API and push frames."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"

        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        payload = {
            "text": self._input_text,
            "model_id": self._model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"ElevenLabs API error {response.status}: {error_text}")

                    # Read audio data
                    audio_data = await response.read()

                    if not audio_data:
                        raise Exception("No audio data received from ElevenLabs")

                    # Convert MP3 to PCM using ffmpeg
                    pcm_data = await self._convert_mp3_to_pcm(audio_data)

                    # Push audio frames in chunks
                    chunk_size = 960  # 20ms at 24kHz mono (24000 * 0.02 * 2 bytes)
                    for i in range(0, len(pcm_data), chunk_size):
                        chunk = pcm_data[i : i + chunk_size]
                        if len(chunk) < chunk_size:
                            chunk = chunk + b"\x00" * (chunk_size - len(chunk))

                        frame = tts.SynthesizedAudio(
                            frame=tts.AudioFrame(
                                data=chunk,
                                sample_rate=24000,
                                num_channels=1,
                                samples_per_channel=len(chunk) // 2,
                            ),
                            request_id="",
                        )
                        self._event_ch.send_nowait(frame)

        except Exception as e:
            raise tts.APIError(f"ElevenLabs HTTP TTS failed: {e}")

    async def _convert_mp3_to_pcm(self, mp3_data: bytes) -> bytes:
        """Convert MP3 to PCM using ffmpeg."""
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i", "pipe:0",
            "-f", "s16le",
            "-ar", "24000",
            "-ac", "1",
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=mp3_data)

        if process.returncode != 0:
            raise Exception(f"ffmpeg conversion failed: {stderr.decode()}")

        return stdout
