import speech_recognition as sr
import io
import logging

logger = logging.getLogger(__name__)

recognizer = sr.Recognizer()


def transcribe_audio(wav_bytes: bytes, language: str = "id-ID") -> str:
    """
    Transkripsi audio WAV ke teks menggunakan Google STT (gratis).
    
    Args:
        wav_bytes: Audio dalam format WAV
        language: Kode bahasa (default: Indonesia)
    
    Returns:
        Teks hasil transkripsi
    
    Raises:
        sr.UnknownValueError: Jika audio tidak bisa dikenali
        sr.RequestError: Jika gagal menghubungi Google STT
    """
    audio_file = io.BytesIO(wav_bytes)
    with sr.AudioFile(audio_file) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio, language=language)
        logger.info(f"STT result: {text}")
        return text
    except sr.UnknownValueError:
        logger.warning("Google STT tidak bisa mengenali audio")
        raise
    except sr.RequestError as e:
        logger.error(f"Google STT request error: {e}")
        raise
