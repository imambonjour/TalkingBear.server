from google import genai
from config import GEMINI_API_KEY
import logging

logger = logging.getLogger(__name__)

# Inisialisasi client
client = genai.Client(api_key=GEMINI_API_KEY)

# System instruction untuk konteks boneka beruang
SYSTEM_PROMPT = (
    "Kamu adalah boneka beruang pintar yang bisa berbicara. namamu Iggy"
    "Jawab dengan bahasa Indonesia yang ramah dan singkat (maksimal 2-3 kalimat). "
    "Gunakan bahasa yang mudah dipahami."
)


async def get_gemini_response(text: str) -> str:
    """
    Kirim teks ke Gemini API dan dapatkan respons menggunakan SDK google-genai terbaru.
    
    Args:
        text: Teks input dari user (hasil STT)
    
    Returns:
        Teks respons dari Gemini
    """
    try:
        # Menggunakan model gemini-2.0-flash
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{SYSTEM_PROMPT}\n\nUser berkata: {text}"
        )
        
        # Ambil teks dari response
        result = response.text
        logger.info(f"Gemini response: {result}")
        return result
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise
