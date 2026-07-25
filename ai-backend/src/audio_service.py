# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Audio service module for voice input.
Provides Whisper (STT) transcription using the OpenAI API.
"""

import io
import logging

from openai import AsyncOpenAI

from src.utils import safe_load_api_key

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create the OpenAI async client."""
    global _openai_client
    if _openai_client is None:
        api_key = safe_load_api_key("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _openai_client = AsyncOpenAI(api_key=api_key.get_secret_value())
    return _openai_client


async def transcribe_audio(
    audio_bytes: bytes,
    language: str = "de",
) -> str:
    """
    Transcribe audio using OpenAI Whisper.

    Args:
        audio_bytes: Raw binary audio data (webm)
        language: language code for transcription. For now, we assume german but as soon as we support proper i18n
                    in the frontend we will handle it based on the users preferences.

    Returns:
        Transcribed text
    """
    client = get_openai_client()

    # Create a file-like object with a name (OpenAI needs the filename extension)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.webm"  # WebM format from browser MediaRecorder

    logger.info(
        f"Transcribing audio ({len(audio_bytes)} bytes) with language={language}"
    )

    response = await client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=audio_file,
        language=language,
    )

    logger.info(
        f"Transcription complete: {response.text} {len(response.text)} characters"
    )
    return response.text
