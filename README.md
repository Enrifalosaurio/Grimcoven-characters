# Grimcoven Equipos

Generador de equipos de cazadores para el juego de mesa **Grimcoven**. A partir de un catálogo
de cazadores y Griefbound (extraído de los reglamentos en `Resources/`), la aplicación:

- genera **equipos aleatorios** de 2 a 5 cazadores (reproducibles con una semilla), y
- **recomienda los mejores equipos** contra un Griefbound concreto, según las amenazas que
  contrarrestan y los roles que cubren.

Es una aplicación web en **FastAPI** con una API JSON bajo `/api` y páginas HTML (Jinja2) con un
tema visual de fantasía oscura.

## Requisitos

- Python 3.11 o superior

## Instalación

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

(en Linux/macOS: `source .venv/bin/activate`)

```bash
pip install -e ".[dev]"
```

## Ejecución

`uvicorn` se instala con las dependencias del proyecto. Arranca la app en modo desarrollo:

```bash
uvicorn grimcoven_equipos.app:app --reload
```

- Página de inicio: <http://127.0.0.1:8000/>
- Documentación interactiva de la API: <http://127.0.0.1:8000/docs>

El catálogo se carga y valida una sola vez al arrancar; si los JSON de `data/` no son válidos,
la aplicación no arranca.

## Docker

La imagen sirve la aplicación con uvicorn en el puerto 8000, como usuario sin privilegios y sin
`--reload`. Incluye `src/` y `data/` bajo `/app`. No incluye `Resources/`, los tests ni los
ficheros de desarrollo (ver `.dockerignore`).

```bash
docker build -t grimcoven-equipos .
docker run --rm -p 8000:8000 grimcoven-equipos
```

Para probar otro catálogo, monta los JSON sobre `/app/data/` (por ejemplo,
`-v ./mis-cazadores.json:/app/data/cazadores.json:ro`). Si los datos no son válidos, el
contenedor termina con un código de salida distinto de 0.

Los tests que construyen la imagen y arrancan contenedores llevan el marcador `docker`. Se
saltan solos si no hay Docker disponible. Para ejecutarlos aparte: `pytest -m docker`.

## Páginas web

| Ruta | Descripción |
|---|---|
| `/` | Página de inicio con enlaces al selector aleatorio y al recomendador. |
| `/aleatorio?tamano=N[&semilla=S]` | Formulario para elegir el tamaño del equipo (2–5); muestra el equipo generado como cartas de cazador. |
| `/recomendador?griefbound=ID&tamano=N` | Formulario con los Griefbound y Pretenders agrupados; muestra los 3 mejores equipos con su puntuación, amenazas y roles cubiertos. |

Sin parámetros, ambas páginas muestran solo el formulario. Los errores (tamaño fuera de rango o
no numérico, Griefbound inexistente) se muestran en la propia página en lugar de devolver un
error JSON. El recomendador incluye un aviso de que los datos son inferidos del reglamento.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/cazadores` | Lista de cazadores ordenada por id. |
| GET | `/api/cazadores/{id}` | Un cazador (404 si no existe). |
| GET | `/api/griefbound?tipo=griefbound\|pretender` | Lista de Griefbound, con filtro opcional por tipo. |
| GET | `/api/griefbound/{id}` | Un Griefbound (404 si no existe). |
| GET | `/api/equipos/aleatorio?tamano=N[&semilla=S]` | Equipo aleatorio de `N` cazadores sin repetir (2–5). |
| GET | `/api/equipos/recomendados?griefbound=ID&tamano=N` | Los 3 mejores equipos de `N` cazadores contra un Griefbound. |

Ejemplos:

```bash
curl "http://127.0.0.1:8000/api/equipos/aleatorio?tamano=3&semilla=42"
```

```bash
curl "http://127.0.0.1:8000/api/equipos/recomendados?griefbound=convergence&tamano=3"
```

### Cómo puntúa el recomendador

Se evalúan todas las combinaciones posibles de `tamano` cazadores:

- **+10** por cada amenaza del Griefbound que algún miembro del equipo contrarresta.
- **+5** por cada rol esencial cubierto (`tanque`, `dano`, `apoyo`; `control` no puntúa).

Los empates se resuelven por orden alfabético de los ids. Si el Griefbound es un *Pretender*, se
excluye al cazador del que procede. Cada equipo devuelve un desglose con las amenazas y roles
cubiertos.

## Datos

El catálogo está en [`data/`](data/):

- [`cazadores.json`](data/cazadores.json): 8 cazadores (6 del juego base y 2 de la expansión
  Hunters).
- [`griefbound.json`](data/griefbound.json): 8 Griefbound (6 base y 2 de Forgotten Entities) y
  8 Pretenders.

Cada entrada cita su fuente (fichero de `Resources/` y página). Los campos `roles`, `amenazas` y
`contrarresta` son **inferencias** a partir de los reglamentos y deben considerarse provisionales:
las debilidades reales están en los Hunt Books, que no están disponibles. Consulta
[`data/README.md`](data/README.md) para el detalle de campos, fuentes, inferencias y datos que
faltan.

## Estructura del proyecto

```
src/grimcoven_equipos/
├── app.py              # Fábrica create_app() y app ASGI
├── catalogo.py         # Modelos (Pydantic), carga y validación del catálogo
├── paginas.py          # Páginas HTML (/, /aleatorio, /recomendador)
├── api/                # Routers de la API (catálogo y equipos)
├── equipos/            # Lógica pura: selector aleatorio y recomendador
├── templates/          # Plantillas Jinja2
└── static/css/         # Tema visual
data/                   # Catálogo JSON
Resources/              # Reglamentos en PDF (fuentes del catálogo)
tests/                  # Tests de pytest
Dockerfile              # Imagen de ejecución (uvicorn, puerto 8000)
```

## Desarrollo

```bash
pytest
```

```bash
ruff check .
```

La CI de GitHub Actions ([`.github/workflows/factory-ci.yml`](.github/workflows/factory-ci.yml))
ejecuta lint y tests en cada push a `main` o `factory/**` y en cada pull request.

### AI Factory

El proyecto se desarrolla con **AI Factory**: las historias de usuario viven en
`.factory/backlog/` y se gestionan con los comandos `/ai-factory:*` (por ejemplo
`/ai-factory:factory-status` o `/ai-factory:factory-board`). Cada historia se desarrolla en su
propia rama `factory/US-XXX`. El contexto para los agentes está en `.factory/context.md`.

## Estado

Todas las historias del backlog (US-001 a US-009) están terminadas: catálogo, API de consulta,
selector aleatorio, recomendador, tema visual, página de inicio y las páginas web `/aleatorio` y
`/recomendador`.

Pendiente: validar las inferencias del catálogo (`roles`, `amenazas`, `contrarresta`) con los
Hunt Books cuando estén disponibles.
