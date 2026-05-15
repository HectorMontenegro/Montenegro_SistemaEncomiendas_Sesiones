# ──1: Imagen base
FROM python:3.12-slim

# ──2: Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# ──3: Directorio de trabajo
WORKDIR /app
# ──4: Instalar dependencias
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
# ──5: Copiar el código fuente
COPY . .
#6: Exponer puerto ASGI
EXPOSE 8001
# ──7: Comando de inicio
CMD ["daphne", "-b", "0.0.0.0", "-p", "8001", "config.asgi:application"]
