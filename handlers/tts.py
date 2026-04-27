from gtts import gTTS
import io
import logging

logger = logging.getLogger(__name__)


def text_to_speech(text: str, lang: str = "id") -> bytes:
    """
    Konversi teks ke audio MP3 menggunakan gTTS (Google Translate TTS).
    
    Args:
        text: Teks yang akan diucapkan
        lang: Kode bahasa (default: Indonesia)
    
    Returns:
        Audio bytes dalam format MP3
    """
    try:
        tts = gTTS(text=text, lang=lang)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        mp3_bytes = audio_buffer.read()
        logger.info(f"TTS generated: {len(mp3_bytes)} bytes MP3")
        return mp3_bytes
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        raise
