from openai import OpenAI
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
import logging

logger = logging.getLogger(__name__)

# Inisialisasi client OpenAI-compatible untuk OpenRouter
client = None
if OPENROUTER_API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

# System instruction untuk konteks boneka beruang
SYSTEM_PROMPT = (
    "Kamu adalah boneka beruang pintar yang bisa berbicara. namamu Iggy. "
    "Jawab dengan bahasa Indonesia yang ramah dan singkat (maksimal 2-3 kalimat). "
    "Gunakan bahasa yang mudah dipahami."
)


async def get_llm_response(text: str) -> str:
    """
    Kirim teks ke OpenRouter API dan dapatkan respons.
    
    Args:
        text: Teks input dari user (hasil STT)
    
    Returns:
        Teks respons dari LLM
    """
    if not client:
        return "Maaf, sistem otak saya belum terhubung ke internet."

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            extra_headers={
                "HTTP-Referer": "https://github.com/talking-bear", # Opsional untuk OpenRouter rankings
                "X-Title": "Talking Bear Voice Proxy",
            }
        )
        
        result = response.choices[0].message.content
        logger.info(f"OpenRouter response: {result}")
        return result
    except Exception as e:
        logger.error(f"OpenRouter API error: {e}")
        return f"Waduh, sepertinya aku lagi pusing. (Error: {str(e)})"
