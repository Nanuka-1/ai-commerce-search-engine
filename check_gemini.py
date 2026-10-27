"""Проверка ключа Gemini: ключ читается из .env и сервис отвечает. В базу ничего не пишет."""
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

if not key:
    print("❌ GEMINI_API_KEY не найден в .env — проверьте строку и сохранение файла")
else:
    print(f"✅ Ключ найден: {key[:4]}... (длина {len(key)})")
    client = genai.Client(api_key=key)
    result = client.models.embed_content(model="gemini-embedding-001", contents=["running shoes"])
    vector = result.embeddings[0].values
    print(f"✅ Gemini ответил: смысловая точка из {len(vector)} чисел, первые три: {vector[:3]}")