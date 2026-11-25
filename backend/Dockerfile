FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# Compose may override this with APP_UID and APP_GID so mounted secret files stay readable.
RUN useradd --system --uid 10001 --no-create-home app
USER 10001

EXPOSE 8000
CMD ["uvicorn", "--factory", "app.entrypoint:create_production_app", "--host", "0.0.0.0", "--port", "8000"]
