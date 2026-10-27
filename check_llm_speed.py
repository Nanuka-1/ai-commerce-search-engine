"""
15.10: замер скорости Gemini БЕЗ нашего сервера, поиска и базы — только модель.
Сравниваем: (1) крошечный запрос «ответь OK» и (2) наше «понимание» (длинная инструкция + JSON).
Печатаем время и токены (prompt / ответ / «размышления») — так видно, что тормозит: сама модель или наш запрос.
~9 обращений к LLM. Запуск из корня проекта: python check_llm_speed.py
"""
import time

from app.services import llm_client
from app.services.llm_understanding_service import build_understanding_prompt

RUNS = 3
PAUSE_SECONDS = 4.5          # лимит free: 15 запросов в минуту


def call(model: str, system: str | None, prompt: str):
    from google.genai import types

    started = time.perf_counter()
    result = llm_client._get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=llm_client.TEMPERATURE,
            max_output_tokens=llm_client.MAX_OUTPUT_TOKENS,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    ms = round((time.perf_counter() - started) * 1000)
    usage = result.usage_metadata
    tokens = (f"prompt={getattr(usage, 'prompt_token_count', None)} "
              f"ответ={getattr(usage, 'candidates_token_count', None)} "
              f"размышления={getattr(usage, 'thoughts_token_count', None)}")
    return ms, tokens


def main():
    model = llm_client.configured_models()[0]
    system, prompt = build_understanding_prompt("კაცის სარბენი 42, 200 ლარამდე?")
    cases = [("крошечный запрос", None, "Reply with one word: OK"),
             ("наше понимание", system, prompt)]
    print(f"Модель: {model}   (все модели цепочки: {llm_client.configured_models()})")
    first = True
    for name, case_system, case_prompt in cases:
        for run in range(1, RUNS + 1):
            if not first:
                time.sleep(PAUSE_SECONDS)
            first = False
            try:
                ms, tokens = call(model, case_system, case_prompt)
                print(f"{name:18} #{run}: {ms:>6} мс   {tokens}")
            except Exception as error:
                print(f"{name:18} #{run}: ОШИБКА {str(error)[:150]}")

    # 15.10 (замер 2): тот же запрос, но ТЕМ ЖЕ путём, что в сервере — llm_client.generate_text (с http_options)
    for run in range(1, RUNS + 1):
        time.sleep(PAUSE_SECONDS)
        started = time.perf_counter()
        response = llm_client.generate_text(system, prompt)
        ms = round((time.perf_counter() - started) * 1000)
        print(f"{'как в сервере':18} #{run}: {ms:>6} мс   модель={response['model']} ошибки={response['errors']}")


if __name__ == "__main__":
    main()