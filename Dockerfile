# ---------- 1. Основа: маленький Linux + Python 3.13 ----------
# slim — облегчённая версия (~120 МБ вместо ~1 ГБ у полной)
FROM python:3.13-slim

# ---------- 2. Настройки Python ----------
# не писать .pyc-файлы (лишний мусор) и сразу печатать логи (не копить в буфере)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------- 3. Папка приложения внутри коробки ----------
WORKDIR /app

# ---------- 4. Пользователь без прав администратора ----------
# если программу взломают, взломщик не получит права root
RUN useradd --create-home --uid 1000 app

# ---------- 5. Сначала только список библиотек ----------
# этот слой меняется редко → Docker берёт его из кэша, и пересборка после правки кода занимает секунды
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---------- 6. Потом наш код (меняется часто — поэтому выше в «торте») ----------
COPY --chown=app:app app/ ./app/
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app ingestion/ ./ingestion/

# папка /app принадлежит пользователю app (сюда пишется запасная SQLite без DATABASE_URL)
RUN chown app:app /app
USER app

# ---------- 7. Порт и проверка здоровья ----------
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# ---------- 8. Команда запуска сервера ----------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]