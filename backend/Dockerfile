FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

WORKDIR /app

# Copy dependency file first for better layer caching
COPY pyproject.toml .

# Install dependencies (without dev extras for production layer)
# Using --system to install into the global Python environment inside the container
RUN uv pip install --system -e "."

# Copy application source
COPY . .

# Непривилегированный пользователь. Тот же образ идёт в бой: prod-compose
# переопределяет команду и убирает монтирование, но не Dockerfile. От root
# внутри контейнера до root на хосте — одна ошибка в среде выполнения,
# и её цена не стоит сэкономленной строки.
#
# uid задан числом, а не оставлен на усмотрение системы: под ним же будут
# файлы в примонтированных томах, и «какой там uid раздался» — плохой ответ
# на вопрос, кому они принадлежат.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
