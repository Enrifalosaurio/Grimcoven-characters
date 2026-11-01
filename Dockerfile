# Imagen de ejecucion de Grimcoven Equipos (FastAPI servida con uvicorn).
#
# Se conserva la estructura del repositorio bajo /app (src/ y data/) porque
# catalogo.py localiza los datos con Path(__file__).parents[2] / "data" y las
# plantillas y estaticos viven junto al paquete. Solo se instalan las
# dependencias de [project].dependencies; el paquete se importa via PYTHONPATH.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Dependencias primero (capa cacheable): se leen de pyproject.toml para no duplicarlas.
COPY pyproject.toml ./
RUN python -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; open('/tmp/requisitos.txt', 'w').write('\n'.join(deps))" \
    && pip install -r /tmp/requisitos.txt \
    && rm /tmp/requisitos.txt

# Codigo y datos de ejecucion (propiedad de root, solo lectura para el usuario de la app).
COPY src/ ./src/
COPY data/ ./data/

# Usuario sin privilegios.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "grimcoven_equipos.app:app", "--host", "0.0.0.0", "--port", "8000"]
