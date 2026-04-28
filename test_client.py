"""
Test client untuk voice proxy server.
Bisa dijalankan TANPA ESP32 — rekam suara dari mic laptop, kirim ke server, putar hasilnya.

Cara pakai:
    python test_client.py --mode http --server https://... --key RAHASIA
    python test_client.py --mode ws   --server https://... --key RAHASIA
"""

import argparse
import wave
import io
import sys
import time


def record_audio(duration: int = 5, sample_rate: int = 16000) -> bytes:
    """Rekam audio dari mic selama N detik, return WAV bytes."""
    try:
        import pyaudio
    except ImportError:
        print("ERROR: pip install pyaudio")
        sys.exit(1)

    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK = 1024

    p = pyaudio.PyAudio()
    
    # Coba beberapa sample rate jika 16000 gagal
    supported_rates = [sample_rate, 44100, 48000, 22050]
    stream = None
    final_rate = sample_rate

    for rate in supported_rates:
        try:
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=rate,
                input=True,
                frames_per_buffer=CHUNK
            )
            final_rate = rate
            break
        except Exception:
            continue

    if stream is None:
        print("❌ ERROR: Tidak ada sample rate yang didukung oleh mic Anda.")
        p.terminate()
        sys.exit(1)

    if final_rate != sample_rate:
        print(f"⚠️  Hardware tidak mendukung {sample_rate}Hz, beralih ke {final_rate}Hz")

    print(f"\n🎤 Berbicara sekarang... ({duration} detik)")

    frames = []
    for _ in range(0, int(final_rate / CHUNK * duration)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    print("✅ Rekaman selesai!")

    # Buat WAV bytes
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(final_rate)
        wf.writeframes(b''.join(frames))
    wav_buffer.seek(0)
    return wav_buffer.read()


def play_audio(audio_bytes: bytes):
    """Putar audio bytes (WAV atau MP3)."""
    import subprocess
    import tempfile
    import os

    # Deteksi format
    if audio_bytes[:4] == b'RIFF':
        ext = ".wav"
    else:
        ext = ".mp3"

    tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
    tmp.write(audio_bytes)
    tmp.close()

    print(f"🔊 Memutar audio ({ext})...")

    # Coba beberapa player
    players = ["aplay", "ffplay -nodisp -autoexit", "mpv --no-video"]
    if ext == ".mp3":
        players = ["mpv --no-video", "ffplay -nodisp -autoexit"]

    for player in players:
        try:
            subprocess.run(player.split() + [tmp.name],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            break
        except FileNotFoundError:
            continue

    os.unlink(tmp.name)


def test_http(server_url: str, audio_bytes: bytes, key: str = None):
    """Test via HTTP POST endpoint."""
    import requests

    print(f"\n📡 Mengirim ke {server_url}/api/voice/json ...")
    t0 = time.time()

    headers = {}
    if key:
        headers["X-Device-Key"] = key

    try:
        resp = requests.post(
            f"{server_url}/api/voice/json",
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            headers=headers
        )

        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"❌ Error {resp.status_code}: {resp.text}")
            return

        data = resp.json()
        print(f"\n{'='*50}")
        print(f"📝 Transcript : {data['transcript']}")
        print(f"🤖 Respons    : {data['response_text']}")
        print(f"⏱️  STT        : {data['timings']['stt_ms']}ms")
        print(f"⏱️  LLM        : {data['timings']['llm_ms']}ms")
        print(f"⏱️  TTS        : {data['timings']['tts_ms']}ms")
        print(f"⏱️  Total      : {int(elapsed * 1000)}ms")
        print(f"{'='*50}")

        # Sekarang minta audio-nya
        print("\n📡 Mengambil audio response...")
        resp2 = requests.post(
            f"{server_url}/api/voice",
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            headers=headers
        )
        if resp2.status_code == 200:
            play_audio(resp2.content)
    except Exception as e:
        print(f"❌ HTTP Request failed: {e}")


def test_websocket(server_url: str, audio_bytes: bytes, key: str = None):
    """Test via WebSocket (simulasi ESP32)."""
    try:
        import websocket
    except ImportError:
        print("ERROR: pip install websocket-client")
        sys.exit(1)

    ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/voice"

    print(f"\n📡 Connecting WebSocket: {ws_url}")

    headers = []
    if key:
        headers.append(f"X-Device-Key: {key}")

    try:
        ws = websocket.create_connection(ws_url, header=headers)
        print("✅ Connected!")

        # Kirim audio sebagai raw PCM (tanpa WAV header, simulasi ESP32)
        if audio_bytes[:4] == b'RIFF':
            pcm_data = audio_bytes[44:]
        else:
            pcm_data = audio_bytes

        print(f"📤 Sending {len(pcm_data)} bytes PCM...")
        ws.send_binary(pcm_data)

        # Terima response
        for _ in range(3):  # Expect: transcript JSON, response JSON, audio bytes
            result = ws.recv()
            if isinstance(result, str):
                import json
                data = json.loads(result)
                if data.get("type") == "transcript":
                    print(f"📝 Transcript: {data['text']}")
                elif data.get("type") == "response":
                    print(f"🤖 Respons: {data['text']}")
                    if "timings" in data:
                        print(f"⏱️  Timings: {data['timings']}")
                elif data.get("type") == "error":
                    print(f"❌ Error: {data['message']}")
                    break
            else:
                print(f"🔊 Received audio: {len(result)} bytes")
                play_audio(result)

        ws.close()
        print("🔌 Disconnected")
    except Exception as e:
        print(f"❌ WebSocket failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test client untuk Voice Proxy Server")
    parser.add_argument("--mode", choices=["http", "ws", "file"], default="http",
                        help="Mode testing: http (POST), ws (WebSocket), file (kirim file)")
    parser.add_argument("--server", default="http://localhost:8000",
                        help="URL server (default: http://localhost:8000)")
    parser.add_argument("--input", help="Path ke file WAV (untuk mode file)")
    parser.add_argument("--duration", type=int, default=5,
                        help="Durasi rekaman mic dalam detik (default: 5)")
    parser.add_argument("--key", help="Device Secret Key (untuk autentikasi)")
    args = parser.parse_args()

    # Dapatkan audio
    if args.input:
        print(f"📂 Membaca file: {args.input}")
        with open(args.input, "rb") as f:
            audio_bytes = f.read()
    else:
        audio_bytes = record_audio(duration=args.duration)

    # Jalankan test
    if args.mode == "http" or args.mode == "file":
        test_http(args.server, audio_bytes, key=args.key)
    elif args.mode == "ws":
        test_websocket(args.server, audio_bytes, key=args.key)


if __name__ == "__main__":
    main()
