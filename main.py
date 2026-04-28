from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.responses import Response
from handlers.stt import transcribe_audio
from handlers.llm import get_llm_response
from handlers.tts import text_to_speech
from middleware.auth import validate_device_key
from utils.audio import pcm_to_wav, mp3_to_wav, is_wav
from config import SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH
import asyncio
import logging
import time
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice Proxy Server",
    description="Proxy server untuk ESP32 voice assistant: STT → Gemini → TTS",
    version="1.0.0"
)


# ─────────────────────────────────────────────
#  Pipeline utama (dipakai oleh WebSocket & HTTP)
# ─────────────────────────────────────────────

async def process_voice_pipeline(audio_bytes: bytes, output_format: str = "mp3") -> dict:
    """
    Pipeline lengkap: Audio → STT → Gemini → TTS → Audio
    
    Args:
        audio_bytes: Audio input (WAV atau raw PCM)
        output_format: "mp3" atau "wav" untuk output audio
    
    Returns:
        dict dengan keys: transcript, response_text, audio_bytes, timings
    """
    timings = {}

    # 1. Konversi PCM → WAV jika belum WAV
    if not is_wav(audio_bytes):
        logger.info("Input is raw PCM, converting to WAV...")
        audio_bytes = pcm_to_wav(audio_bytes, SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH)

    # 2. STT — jalankan di thread pool supaya tidak block event loop
    t0 = time.time()
    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)
    except Exception as e:
        raise RuntimeError(f"STT gagal: {e}")
    timings["stt_ms"] = int((time.time() - t0) * 1000)

    # 3. Gemini LLM
    t0 = time.time()
    try:
        response_text = await get_llm_response(transcript)
    except Exception as e:
        raise RuntimeError(f"Gemini gagal: {e}")
    timings["llm_ms"] = int((time.time() - t0) * 1000)

    # 4. TTS — jalankan di thread pool
    t0 = time.time()
    try:
        mp3_bytes = await asyncio.to_thread(text_to_speech, response_text)
    except Exception as e:
        raise RuntimeError(f"TTS gagal: {e}")
    timings["tts_ms"] = int((time.time() - t0) * 1000)

    # 5. Konversi MP3 → WAV jika diminta (untuk ESP32 yang tidak bisa decode MP3)
    if output_format == "wav":
        t0 = time.time()
        out_audio = await asyncio.to_thread(mp3_to_wav, mp3_bytes, SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH)
        timings["convert_ms"] = int((time.time() - t0) * 1000)
    else:
        out_audio = mp3_bytes

    logger.info(f"Pipeline done — STT: {timings['stt_ms']}ms, LLM: {timings['llm_ms']}ms, TTS: {timings['tts_ms']}ms")

    return {
        "transcript": transcript,
        "response_text": response_text,
        "audio_bytes": out_audio,
        "timings": timings
    }


# ─────────────────────────────────────────────
#  Endpoint 1: WebSocket (untuk ESP32)
# ─────────────────────────────────────────────

@app.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()

    if not await validate_device_key(websocket):
        return

    client = websocket.client
    logger.info(f"Client connected: {client}")

    try:
        while True:
            # Terima audio dari client
            pcm_data = await websocket.receive_bytes()
            logger.info(f"Received: {len(pcm_data)} bytes from {client}")

            try:
                result = await process_voice_pipeline(pcm_data, output_format="wav")

                # Kirim transcript & respons teks
                await websocket.send_json({
                    "type": "transcript",
                    "text": result["transcript"]
                })
                await websocket.send_json({
                    "type": "response",
                    "text": result["response_text"],
                    "timings": result["timings"]
                })

                # Kirim audio WAV balik ke ESP32
                await websocket.send_bytes(result["audio_bytes"])
                logger.info(f"Sent {len(result['audio_bytes'])} bytes audio to {client}")

            except RuntimeError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except:
            pass


# ─────────────────────────────────────────────
#  Endpoint 2: HTTP POST (untuk testing tanpa ESP32)
# ─────────────────────────────────────────────

@app.post("/api/voice")
async def voice_http(file: UploadFile = File(...)):
    """
    Upload file audio (WAV/PCM) dan dapatkan respons audio + teks.
    
    Test dengan curl:
        curl -X POST http://localhost:8000/api/voice \
             -F "file=@test_audio.wav" \
             --output response.mp3
    
    Atau tambahkan ?format=wav untuk output WAV:
        curl -X POST "http://localhost:8000/api/voice?format=wav" \
             -F "file=@test_audio.wav" \
             --output response.wav
    """
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="File audio kosong")

    logger.info(f"HTTP upload: {file.filename}, {len(audio_bytes)} bytes")

    try:
        result = await process_voice_pipeline(audio_bytes, output_format="mp3")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Return audio MP3 dengan header tambahan berisi teks
    return Response(
        content=result["audio_bytes"],
        media_type="audio/mpeg",
        headers={
            "X-Transcript": result["transcript"],
            "X-Response-Text": result["response_text"],
            "X-Timing-STT-Ms": str(result["timings"]["stt_ms"]),
            "X-Timing-LLM-Ms": str(result["timings"]["llm_ms"]),
            "X-Timing-TTS-Ms": str(result["timings"]["tts_ms"]),
        }
    )


@app.post("/api/voice/json")
async def voice_http_json(file: UploadFile = File(...)):
    """
    Sama seperti /api/voice tapi return JSON (tanpa audio).
    Berguna untuk debugging pipeline STT + LLM tanpa perlu TTS.
    
    Test dengan curl:
        curl -X POST http://localhost:8000/api/voice/json \
             -F "file=@test_audio.wav"
    """
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="File audio kosong")

    logger.info(f"HTTP JSON upload: {file.filename}, {len(audio_bytes)} bytes")

    try:
        result = await process_voice_pipeline(audio_bytes, output_format="mp3")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "transcript": result["transcript"],
        "response_text": result["response_text"],
        "timings": result["timings"],
        "audio_size_bytes": len(result["audio_bytes"])
    }


# ─────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "voice-proxy"}


@app.get("/")
def root():
    return {
        "service": "Voice Proxy Server",
        "endpoints": {
            "websocket": "/ws/voice — WebSocket untuk ESP32 (kirim PCM, terima WAV)",
            "http_audio": "POST /api/voice — Upload WAV, terima MP3 response",
            "http_json": "POST /api/voice/json — Upload WAV, terima JSON (debug)",
            "health": "GET /health",
            "docs": "GET /docs — Swagger UI (interactive API docs)",
        }
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
