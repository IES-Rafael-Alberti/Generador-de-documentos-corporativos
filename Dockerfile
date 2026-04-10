# Imagen base oficial de Playwright — incluye Chromium y todas las dependencias del sistema
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar proyecto
COPY . .

ENTRYPOINT ["python", "scripts/md_to_pdf.py"]
