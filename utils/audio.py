import wave
import io
from pydub import AudioSegment


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000,
               channels: int = 1, sample_width: int = 2) -> bytes:
    """Konversi raw PCM bytes menjadi WAV bytes (untuk STT)."""
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer.read()


def mp3_to_wav(mp3_data: bytes, sample_rate: int = 16000,
               channels: int = 1, sample_width: int = 2) -> bytes:
    """Konversi MP3 bytes (output gTTS) menjadi WAV PCM bytes (untuk ESP32 speaker)."""
    mp3_buffer = io.BytesIO(mp3_data)
    audio = AudioSegment.from_mp3(mp3_buffer)

    # Resample dan konversi ke mono jika perlu
    audio = audio.set_frame_rate(sample_rate)
    audio = audio.set_channels(channels)
    audio = audio.set_sample_width(sample_width)

    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format="wav")
    wav_buffer.seek(0)
    return wav_buffer.read()


def is_wav(data: bytes) -> bool:
    """Cek apakah data sudah berformat WAV (ada RIFF header)."""
    return data[:4] == b'RIFF'
