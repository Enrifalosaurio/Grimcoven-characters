"""Tests de US-010: Imagen Docker de la aplicacion web.

Cada test indica el criterio de aceptacion (CA<n>) que cubre.

Hay dos grupos:
- Tests de contenido (pyproject.toml, Dockerfile, .dockerignore): se ejecutan siempre.
- Tests de Docker (marcados con ``@pytest.mark.docker``): construyen la imagen una sola
  vez por sesion y arrancan contenedores. Si no hay ejecutable ``docker`` en el PATH o el
  daemon esta parado, se saltan con un motivo que menciona Docker.

Los nombres de imagen y contenedores se derivan de ``FACTORY_STORY_ID`` (o ``test``) y el
puerto de ``FACTORY_PORT`` (o uno libre) para no colisionar con otras historias.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app

# ---------------------------------------------------------------------------
# Constantes y utilidades
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parents[1]
RUTA_PYPROJECT = RAIZ / "pyproject.toml"
RUTA_DOCKERFILE = RAIZ / "Dockerfile"
RUTA_DOCKERIGNORE = RAIZ / ".dockerignore"

ID_HISTORIA = (os.environ.get("FACTORY_STORY_ID") or "test").strip().lower()
PREFIJO_CONTENEDOR = f"grimcoven-{ID_HISTORIA}"
NOMBRE_IMAGEN = f"grimcoven-equipos:{ID_HISTORIA}"

COMANDO_UVICORN = "uvicorn grimcoven_equipos.app:app --host 0.0.0.0 --port 8000"
TAMANO_MAXIMO_BYTES = 300 * 1000 * 1000  # 300 MB
TIMEOUT_BUILD_S = 900
TIMEOUT_ARRANQUE_S = 30


def _docker(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    """Ejecuta ``docker <args>`` y devuelve el resultado (sin lanzar si falla)."""
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def comprobar_docker() -> tuple[bool, str]:
    """Indica si Docker es utilizable y, si no, el motivo (que siempre menciona Docker)."""
    if shutil.which("docker") is None:
        return False, "Docker no disponible: no hay ejecutable 'docker' en el PATH"
    try:
        resultado = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Docker no disponible: el daemon no responde ({exc})"
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout).strip().splitlines()
        motivo = detalle[0] if detalle else f"codigo {resultado.returncode}"
        return False, f"Docker no disponible: el daemon esta parado ({motivo})"
    return True, ""


@functools.cache
def _estado_docker() -> tuple[bool, str]:
    """Version cacheada de ``comprobar_docker`` (una consulta por sesion)."""
    return comprobar_docker()


@pytest.fixture(autouse=True)
def _saltar_sin_docker(request: pytest.FixtureRequest) -> None:
    """Salta los tests marcados con ``docker`` si Docker no esta disponible."""
    if request.node.get_closest_marker("docker") is None:
        return
    disponible, motivo = _estado_docker()
    if not disponible:
        pytest.skip(motivo)


def _puerto_host() -> int:
    """Puerto del host: ``FACTORY_PORT`` o uno libre elegido por el sistema."""
    valor = os.environ.get("FACTORY_PORT")
    if valor:
        return int(valor)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(url: str, timeout: float = 5) -> tuple[int, dict[str, str], bytes]:
    """GET HTTP sencillo con urllib; devuelve (estado, cabeceras en minuscula, cuerpo)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            cabeceras = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, cabeceras, resp.read()
    except urllib.error.HTTPError as exc:
        cabeceras = {k.lower(): v for k, v in exc.headers.items()}
        return exc.code, cabeceras, exc.read()


def _contenedores_con_prefijo(prefijo: str) -> list[str]:
    """Nombres de contenedores (incluidos los parados) cuyo nombre contiene ``prefijo``."""
    resultado = _docker("ps", "-a", "--filter", f"name={prefijo}", "--format", "{{.Names}}")
    return [linea for linea in resultado.stdout.splitlines() if linea.strip()]


@contextlib.contextmanager
def contenedor(nombre: str, *args_run: str) -> Iterator[str]:
    """Arranca ``docker run -d --name <nombre> <args_run>`` y lo elimina siempre al salir.

    El teardown usa ``docker rm -f`` aunque el bloque ``with`` lance una excepcion
    (por ejemplo, un assert que falla a mitad de test).
    """
    _docker("rm", "-f", nombre)
    try:
        resultado = _docker("run", "-d", "--name", nombre, *args_run)
        if resultado.returncode != 0:
            pytest.fail(f"docker run fallo para {nombre}:\n{resultado.stderr}")
        yield nombre
    finally:
        _docker("rm", "-f", nombre)


# ----- Parseo del Dockerfile -----


def _instrucciones_dockerfile(texto: str) -> list[tuple[str, str]]:
    """Devuelve las instrucciones del Dockerfile como (INSTRUCCION, argumentos).

    Une las lineas continuadas con ``\\`` y descarta comentarios y lineas vacias.
    """
    instrucciones: list[tuple[str, str]] = []
    acumulado = ""
    for linea_bruta in texto.splitlines():
        linea = linea_bruta.strip()
        if not acumulado and (not linea or linea.startswith("#")):
            continue
        if acumulado and linea.startswith("#"):
            continue
        if linea.endswith("\\"):
            acumulado += linea[:-1].strip() + " "
            continue
        acumulado += linea
        partes = acumulado.strip().split(None, 1)
        instrucciones.append((partes[0].upper(), partes[1] if len(partes) > 1 else ""))
        acumulado = ""
    if acumulado.strip():
        partes = acumulado.strip().split(None, 1)
        instrucciones.append((partes[0].upper(), partes[1] if len(partes) > 1 else ""))
    return instrucciones


def _tokens_comando(argumentos: str) -> list[str]:
    """Convierte los argumentos de CMD/ENTRYPOINT (forma exec JSON o shell) en tokens."""
    argumentos = argumentos.strip()
    if argumentos.startswith("["):
        valor = json.loads(argumentos)
        assert isinstance(valor, list), "CMD en forma exec debe ser una lista JSON"
        return [str(token) for token in valor]
    return shlex.split(argumentos)


def _imagen_del_from(argumentos: str) -> str:
    """Extrae la referencia de imagen de un FROM (ignora --platform y ``AS etapa``)."""
    tokens = [t for t in argumentos.split() if not t.startswith("--")]
    return tokens[0]


# ----- Parseo de requisitos de pyproject -----


def _version(texto: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", texto))


def _version_minima(dependencias: list[str], paquete: str) -> tuple[int, ...] | None:
    """Version minima (``>=``) declarada para ``paquete`` o ``None`` si no la hay."""
    patron = re.compile(
        rf"^{re.escape(paquete)}(\[[^\]]*\])?\s*(?P<espec>[^;]*)", re.IGNORECASE
    )
    for dep in dependencias:
        coincidencia = patron.match(dep.strip())
        if coincidencia is None:
            continue
        resto = dep.strip()[len(paquete):]
        # Evita falsos positivos tipo "uvicorn-worker" o "fastapi-users".
        if resto and resto[0] not in "[ <>=!~;":
            continue
        minima = re.search(r">=\s*([0-9][0-9.]*)", coincidencia.group("espec"))
        return _version(minima.group(1)) if minima else None
    return None


# ----- Parseo de .dockerignore -----


def _entradas_dockerignore(texto: str) -> set[str]:
    """Entradas normalizadas: sin comentarios, sin ``/`` inicial/final ni ``**/``."""
    entradas: set[str] = set()
    for linea_bruta in texto.splitlines():
        linea = linea_bruta.strip()
        if not linea or linea.startswith("#") or linea.startswith("!"):
            continue
        while linea.startswith("**/"):
            linea = linea[3:]
        entradas.add(linea.strip("/"))
    return entradas


# ---------------------------------------------------------------------------
# Fixtures de contenido
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with RUTA_PYPROJECT.open("rb") as fichero:
        return tomllib.load(fichero)


@pytest.fixture(scope="module")
def dockerfile() -> list[tuple[str, str]]:
    """Instrucciones del Dockerfile (lista vacia si falta: los tests fallan con detalle)."""
    if not RUTA_DOCKERFILE.is_file():
        return []
    return _instrucciones_dockerfile(RUTA_DOCKERFILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dockerignore() -> set[str]:
    """Entradas de .dockerignore (conjunto vacio si falta: los tests fallan con detalle)."""
    if not RUTA_DOCKERIGNORE.is_file():
        return set()
    return _entradas_dockerignore(RUTA_DOCKERIGNORE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# CA1: pyproject.toml declara uvicorn con version minima
# ---------------------------------------------------------------------------


def test_ca1_pyproject_declara_uvicorn_con_version_minima(pyproject: dict) -> None:
    """CA1: [project].dependencies incluye uvicorn con version minima (>=0.30)."""
    dependencias = pyproject["project"]["dependencies"]
    minima = _version_minima(dependencias, "uvicorn")
    assert minima is not None, f"uvicorn sin version minima en {dependencias}"
    assert minima >= (0, 30), f"uvicorn debe ser >=0.30, declarado {minima}"


@pytest.mark.parametrize(
    ("paquete", "minima"),
    [("fastapi", (0, 115)), ("jinja2", (3, 1, 6)), ("pydantic", (2, 7))],
)
def test_ca1_pyproject_conserva_dependencias_existentes(
    pyproject: dict, paquete: str, minima: tuple[int, ...]
) -> None:
    """CA1: fastapi>=0.115, jinja2>=3.1.6 y pydantic>=2.7 siguen presentes."""
    declarada = _version_minima(pyproject["project"]["dependencies"], paquete)
    assert declarada is not None, f"{paquete} debe seguir con version minima declarada"
    assert declarada >= minima, f"{paquete} debe ser >={minima}, declarado {declarada}"


def test_ca1_helper_version_minima_ignora_paquetes_con_prefijo() -> None:
    """CA1 (limite): 'uvicorn-worker>=1' no cuenta como uvicorn; 'uvicorn[standard]' si."""
    assert _version_minima(["uvicorn-worker>=1.0"], "uvicorn") is None
    assert _version_minima(["uvicorn[standard]>=0.30"], "uvicorn") == (0, 30)
    assert _version_minima(["uvicorn"], "uvicorn") is None


# ---------------------------------------------------------------------------
# CA3: contenido del Dockerfile
# ---------------------------------------------------------------------------


def test_ca3_existe_dockerfile_en_la_raiz() -> None:
    """CA3: hay un Dockerfile en la raiz del repositorio."""
    assert RUTA_DOCKERFILE.is_file(), "falta el Dockerfile en la raiz del repositorio"


def test_ca3_primer_from_usa_python_312_slim(dockerfile: list[tuple[str, str]]) -> None:
    """CA3: el primer FROM usa python:3.12-slim (version menor fija, nunca latest)."""
    froms = [args for instr, args in dockerfile if instr == "FROM"]
    assert froms, "el Dockerfile no tiene ninguna instruccion FROM"
    imagen = _imagen_del_from(froms[0])
    assert re.fullmatch(r"python:3\.12-slim(@sha256:[0-9a-f]{64})?", imagen), (
        f"el primer FROM debe ser python:3.12-slim (opcionalmente fijado por digest), es {imagen}"
    )


def test_ca3_ningun_from_usa_latest(dockerfile: list[tuple[str, str]]) -> None:
    """CA3 (limite): ninguna etapa usa la etiqueta 'latest' ni una imagen sin etiqueta."""
    etapas: set[str] = set()
    for instr, args in dockerfile:
        if instr != "FROM":
            continue
        partes = args.split()
        imagen = _imagen_del_from(args)
        if imagen.lower() not in etapas:  # FROM <etapa anterior> no es una imagen externa
            assert ":latest" not in imagen, f"FROM no debe usar latest: {imagen}"
            assert ":" in imagen or "@" in imagen, f"FROM sin etiqueta fija: {imagen}"
        if len(partes) >= 3 and partes[-2].upper() == "AS":
            etapas.add(partes[-1].lower())


def test_ca3_expone_puerto_8000(dockerfile: list[tuple[str, str]]) -> None:
    """CA3: el Dockerfile contiene EXPOSE 8000."""
    expuestos = [args.split() for instr, args in dockerfile if instr == "EXPOSE"]
    assert any("8000" in p or "8000/tcp" in p for p in expuestos), (
        f"falta EXPOSE 8000 (EXPOSE encontrados: {expuestos})"
    )


def test_ca3_usuario_no_root(dockerfile: list[tuple[str, str]]) -> None:
    """CA3: hay una instruccion USER y la ultima no es root (ni uid 0)."""
    usuarios = [args.strip() for instr, args in dockerfile if instr == "USER"]
    assert usuarios, "el Dockerfile no tiene ninguna instruccion USER"
    usuario_final = usuarios[-1].split(":")[0]
    assert usuario_final not in {"root", "0"}, f"la ultima USER es root: {usuarios[-1]}"


def test_ca3_cmd_arranca_uvicorn_sin_reload(dockerfile: list[tuple[str, str]]) -> None:
    """CA3: el CMD arranca uvicorn grimcoven_equipos.app:app en 0.0.0.0:8000 sin --reload."""
    cmds = [args for instr, args in dockerfile if instr == "CMD"]
    assert cmds, "el Dockerfile no tiene ninguna instruccion CMD"
    tokens = _tokens_comando(cmds[-1])
    comando = " ".join(tokens)
    assert COMANDO_UVICORN in comando, f"el CMD debe contener '{COMANDO_UVICORN}', es '{comando}'"
    assert "--reload" not in tokens, "el CMD no debe usar --reload"


def test_ca3_helper_parsea_lineas_continuadas_y_forma_shell() -> None:
    """CA3 (limite): el parser une lineas con '\\', ignora comentarios y acepta forma shell."""
    texto = (
        "# comentario\n"
        "FROM --platform=linux/amd64 python:3.12-slim AS base\n"
        "RUN pip install \\\n"
        "    fastapi\n"
        "CMD uvicorn grimcoven_equipos.app:app --host 0.0.0.0 --port 8000\n"
    )
    instrucciones = _instrucciones_dockerfile(texto)
    assert [i for i, _ in instrucciones] == ["FROM", "RUN", "CMD"]
    assert _imagen_del_from(instrucciones[0][1]) == "python:3.12-slim"
    assert instrucciones[1][1] == "pip install fastapi"
    assert " ".join(_tokens_comando(instrucciones[2][1])) == COMANDO_UVICORN


# ---------------------------------------------------------------------------
# CA9 (parte de contenido): .dockerignore
# ---------------------------------------------------------------------------


def test_ca9_existe_dockerignore_en_la_raiz() -> None:
    """CA9: hay un .dockerignore en la raiz del repositorio."""
    assert RUTA_DOCKERIGNORE.is_file(), "falta el .dockerignore en la raiz del repositorio"


@pytest.mark.parametrize(
    "entrada",
    [".git", ".venv", ".factory", "Resources", "tests", "__pycache__", ".pytest_cache",
     ".ruff_cache"],
)
def test_ca9_dockerignore_excluye_entrada(dockerignore: set[str], entrada: str) -> None:
    """CA9: .dockerignore excluye .git, .venv, .factory, Resources, tests y las caches."""
    assert entrada in dockerignore, f".dockerignore debe excluir {entrada}: {sorted(dockerignore)}"


def test_ca9_helper_normaliza_entradas_dockerignore() -> None:
    """CA9 (limite): '/.git/', '**/__pycache__' y comentarios se normalizan."""
    texto = "# comentario\n/.git/\n**/__pycache__\n\n!README.md\ntests/\n"
    assert _entradas_dockerignore(texto) == {".git", "__pycache__", "tests"}


# ---------------------------------------------------------------------------
# CA11: marcador docker registrado y salto sin Docker
# ---------------------------------------------------------------------------


def test_ca11_marcador_docker_registrado_en_pyproject(pyproject: dict) -> None:
    """CA11: [tool.pytest.ini_options].markers registra el marcador 'docker'."""
    marcadores = pyproject["tool"]["pytest"]["ini_options"].get("markers", [])
    nombres = [m.split(":", 1)[0].strip() for m in marcadores]
    assert "docker" in nombres, f"el marcador 'docker' no esta registrado: {marcadores}"


def test_ca11_sin_ejecutable_docker_se_salta_con_motivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CA11: sin 'docker' en el PATH, la comprobacion falla con un motivo que cita Docker."""
    monkeypatch.setattr(shutil, "which", lambda _nombre: None)
    disponible, motivo = comprobar_docker()
    assert disponible is False
    assert "Docker" in motivo


def test_ca11_daemon_parado_se_salta_con_motivo(monkeypatch: pytest.MonkeyPatch) -> None:
    """CA11: con el daemon parado ('docker info' falla), el motivo cita Docker."""
    monkeypatch.setattr(shutil, "which", lambda _nombre: "/usr/bin/docker")

    def _info_falla(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["docker", "info"],
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon. Is the docker daemon running?",
        )

    monkeypatch.setattr(subprocess, "run", _info_falla)
    disponible, motivo = comprobar_docker()
    assert disponible is False
    assert "Docker" in motivo


def test_ca11_tests_de_docker_estan_marcados(request: pytest.FixtureRequest) -> None:
    """CA11: todos los tests que usan la imagen llevan el marcador 'docker'."""
    sin_marcar = [
        item.name
        for item in request.session.items
        if item.module is not None
        and item.module.__name__ == __name__
        and "imagen" in getattr(item, "fixturenames", ())
        and item.get_closest_marker("docker") is None
    ]
    assert not sin_marcar, f"tests que usan la imagen sin @pytest.mark.docker: {sin_marcar}"


# ---------------------------------------------------------------------------
# Fixtures de Docker (scope de sesion: la imagen se construye una sola vez)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def resultado_build() -> Iterator[subprocess.CompletedProcess[str]]:
    """Construye la imagen una vez por sesion y limpia contenedores huerfanos al final."""
    disponible, motivo = _estado_docker()
    if not disponible:
        pytest.skip(motivo)
    resultado = subprocess.run(
        ["docker", "build", "-t", NOMBRE_IMAGEN, str(RAIZ)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_BUILD_S,
        check=False,
    )
    yield resultado
    # Red de seguridad: ningun contenedor de esta historia sobrevive a la sesion.
    for nombre in _contenedores_con_prefijo(PREFIJO_CONTENEDOR):
        _docker("rm", "-f", nombre)


@pytest.fixture(scope="session")
def imagen(resultado_build: subprocess.CompletedProcess[str]) -> str:
    """Nombre de la imagen construida; falla si el build no termino con exito."""
    if resultado_build.returncode != 0:
        pytest.fail(
            f"docker build fallo (codigo {resultado_build.returncode}):\n"
            f"{resultado_build.stderr[-4000:]}"
        )
    return NOMBRE_IMAGEN


@pytest.fixture(scope="session")
def url_base(imagen: str) -> Iterator[str]:
    """Contenedor de la app publicado en el puerto del host, listo para recibir peticiones."""
    puerto = _puerto_host()
    nombre = f"{PREFIJO_CONTENEDOR}-web"
    with contenedor(nombre, "-p", f"{puerto}:8000", imagen):
        base = f"http://127.0.0.1:{puerto}"
        limite = time.monotonic() + TIMEOUT_ARRANQUE_S
        ultimo_error: object = None
        while time.monotonic() < limite:
            try:
                estado, _, _ = _get(f"{base}/api/cazadores", timeout=2)
                if estado == 200:
                    break
                ultimo_error = f"HTTP {estado}"
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                ultimo_error = exc
            time.sleep(1)
        else:
            logs = _docker("logs", nombre).stderr[-4000:]
            pytest.fail(
                f"la app no respondio en {TIMEOUT_ARRANQUE_S} s ({ultimo_error}).\nLogs:\n{logs}"
            )
        yield base


# ---------------------------------------------------------------------------
# CA2: docker build termina con codigo 0
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca2_docker_build_termina_con_codigo_0(
    resultado_build: subprocess.CompletedProcess[str],
) -> None:
    """CA2: 'docker build -t grimcoven-equipos:<id> .' termina con codigo 0."""
    assert resultado_build.returncode == 0, resultado_build.stderr[-4000:]


# ---------------------------------------------------------------------------
# CA4: el proceso no corre como root
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca4_usuario_de_la_imagen_no_es_root(imagen: str) -> None:
    """CA4: 'docker run --rm --entrypoint id <imagen> -u' devuelve un uid distinto de 0."""
    resultado = _docker("run", "--rm", "--entrypoint", "id", imagen, "-u")
    assert resultado.returncode == 0, resultado.stderr
    salida = resultado.stdout.strip()
    assert salida.isdigit(), f"'id -u' debe devolver un entero, devolvio {salida!r}"
    assert int(salida) != 0, "el contenedor corre como root (uid 0)"


# ---------------------------------------------------------------------------
# CA5: la API responde con los 8 cazadores
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca5_api_cazadores_devuelve_8(url_base: str) -> None:
    """CA5: GET /api/cazadores responde 200 con una lista JSON de exactamente 8 cazadores."""
    estado, cabeceras, cuerpo = _get(f"{url_base}/api/cazadores")
    assert estado == 200
    assert cabeceras.get("content-type", "").startswith("application/json")
    datos = json.loads(cuerpo)
    assert isinstance(datos, list)
    assert len(datos) == 8


# ---------------------------------------------------------------------------
# CA6: pagina de inicio y CSS estan en la imagen
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca6_pagina_inicio_es_html(url_base: str) -> None:
    """CA6: GET / responde 200, text/html y contiene 'Grimcoven Equipos'."""
    estado, cabeceras, cuerpo = _get(f"{url_base}/")
    assert estado == 200
    assert cabeceras.get("content-type", "").startswith("text/html")
    assert "Grimcoven Equipos" in cuerpo.decode("utf-8")


@pytest.mark.docker
def test_ca6_css_tema_es_text_css(url_base: str) -> None:
    """CA6: GET /static/css/tema.css responde 200 con content-type text/css."""
    estado, cabeceras, cuerpo = _get(f"{url_base}/static/css/tema.css")
    assert estado == 200
    assert cabeceras.get("content-type", "").startswith("text/css")
    assert cuerpo.strip(), "el CSS servido no debe estar vacio"


# ---------------------------------------------------------------------------
# CA7: los datos de la imagen son los del repositorio
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca7_equipo_aleatorio_coincide_con_testclient(url_base: str) -> None:
    """CA7: con tamano=3&semilla=42 el contenedor y TestClient devuelven los mismos ids."""
    ruta = "/api/equipos/aleatorio?tamano=3&semilla=42"
    estado, _, cuerpo = _get(f"{url_base}{ruta}")
    assert estado == 200
    ids_contenedor = [c["id"] for c in json.loads(cuerpo)["cazadores"]]

    respuesta_local = TestClient(create_app()).get(ruta)
    assert respuesta_local.status_code == 200
    ids_locales = [c["id"] for c in respuesta_local.json()["cazadores"]]

    assert len(ids_contenedor) == 3
    assert ids_contenedor == ids_locales


# ---------------------------------------------------------------------------
# CA8: con datos malformados el contenedor termina con error
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca8_datos_malformados_el_contenedor_termina_con_error(
    imagen: str, tmp_path: Path
) -> None:
    """CA8: con cazadores.json malformado montado, el contenedor sale solo con codigo != 0."""
    fichero_malo = tmp_path / "cazadores.json"
    fichero_malo.write_text('[{"id": "roto", ', encoding="utf-8")
    nombre = f"{PREFIJO_CONTENEDOR}-datos-malos"
    with contenedor(nombre, "-v", f"{fichero_malo}:/app/data/cazadores.json:ro", imagen):
        try:
            espera = _docker("wait", nombre, timeout=TIMEOUT_ARRANQUE_S)
        except subprocess.TimeoutExpired:
            pytest.fail(f"el contenedor sigue vivo tras {TIMEOUT_ARRANQUE_S} s con datos invalidos")
        assert espera.returncode == 0, espera.stderr
        codigo = int(espera.stdout.strip())
        assert codigo != 0, "el contenedor termino con codigo 0 pese a los datos invalidos"


# ---------------------------------------------------------------------------
# CA9 (parte de imagen): ficheros excluidos no estan en /app
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca9_imagen_no_contiene_ficheros_excluidos(imagen: str) -> None:
    """CA9: /app/.git, /app/.venv, /app/.factory, /app/Resources y /app/tests no existen."""
    rutas = ["/app/.git", "/app/.venv", "/app/.factory", "/app/Resources", "/app/tests"]
    codigo = (
        "import json, os; "
        f"print(json.dumps([r for r in {rutas!r} if os.path.exists(r)]))"
    )
    resultado = _docker("run", "--rm", "--entrypoint", "python", imagen, "-c", codigo)
    assert resultado.returncode == 0, resultado.stderr
    presentes = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert presentes == [], f"la imagen contiene rutas excluidas: {presentes}"


@pytest.mark.docker
def test_ca9_imagen_contiene_datos_en_app_data(imagen: str) -> None:
    """CA9 (limite): los datos de ejecucion si estan en /app/data (los usa el volumen de CA8)."""
    codigo = (
        "import os; "
        "print(os.path.isfile('/app/data/cazadores.json') "
        "and os.path.isfile('/app/data/griefbound.json'))"
    )
    resultado = _docker("run", "--rm", "--entrypoint", "python", imagen, "-c", codigo)
    assert resultado.returncode == 0, resultado.stderr
    assert resultado.stdout.strip() == "True"


# ---------------------------------------------------------------------------
# CA10: tamano de la imagen
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca10_imagen_menor_de_300_mb(imagen: str) -> None:
    """CA10: 'docker image inspect --format {{.Size}}' es menor de 300 MB."""
    resultado = _docker("image", "inspect", "--format", "{{.Size}}", imagen)
    assert resultado.returncode == 0, resultado.stderr
    tamano = int(resultado.stdout.strip())
    assert tamano < TAMANO_MAXIMO_BYTES, f"la imagen ocupa {tamano / 1e6:.1f} MB (>= 300 MB)"


# ---------------------------------------------------------------------------
# CA12: los contenedores se eliminan aunque el test falle a mitad
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_ca12_contenedor_se_elimina_aunque_falle_el_test(imagen: str) -> None:
    """CA12: si el bloque falla a mitad, el teardown hace 'docker rm -f' del contenedor."""
    nombre = f"{PREFIJO_CONTENEDOR}-limpieza"
    with pytest.raises(RuntimeError, match="fallo simulado"):
        with contenedor(nombre, "--entrypoint", "python", imagen, "-c",
                        "import time; time.sleep(60)"):
            assert _contenedores_con_prefijo(nombre) == [nombre]
            raise RuntimeError("fallo simulado a mitad de test")
    assert _contenedores_con_prefijo(nombre) == [], (
        f"quedan contenedores tras el teardown: {_contenedores_con_prefijo(nombre)}"
    )
