"""Tests de US-013: fixtures de ``tests/e2e/conftest.py`` y test de humo sin navegador real.

Cada test indica el criterio de aceptacion (CA<n>) que cubre. Se ejecuta un pytest anidado
para observar lo mismo que un desarrollador (salidas, codigo de retorno, puerto tras el
teardown) con un entorno controlado, sea cual sea lo instalado en la maquina:

- "sin Playwright": un plugin deja ``playwright`` como no importable.
- "sin Chromium" y "con navegador": un doble de ``playwright`` en ``PYTHONPATH`` tiene prioridad
  sobre el paquete real. Su ``goto`` pide la pagina de verdad al servidor del fixture y toma el
  titulo del HTML; el resto (consola, errores de JS) lo decide ``FALSO_PLAYWRIGHT_MODO``.

El navegador real se ejercita en ``tests/e2e/test_humo.py`` (job 'e2e' de la CI).
"""

from __future__ import annotations

import ast
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RAIZ = Path(__file__).resolve().parents[1]
DIR_E2E = RAIZ / "tests" / "e2e"
RUTA_CONFTEST = DIR_E2E / "conftest.py"
PUERTO_CA2 = 40123
TIMEOUT_PYTEST_S = 120

VARIABLES_AISLADAS = (
    "FACTORY_PORT",
    "GRIMCOVEN_REQUIRE_E2E",
    "PLAYWRIGHT_BROWSERS_PATH",
    "PYTEST_ADDOPTS",
)

# ---------------------------------------------------------------------------
# Dobles y sondas que se escriben en tmp_path para el pytest anidado
# ---------------------------------------------------------------------------

BLOQUEO_PLAYWRIGHT = '''\
"""Plugin de pytest: hace que ``import playwright`` falle aunque este instalado."""
import sys

sys.modules["playwright"] = None
sys.modules["playwright.sync_api"] = None
'''

BLOQUEO_UVICORN = '''\
"""Plugin de pytest: hace que ``import uvicorn`` falle aunque este instalado."""
import sys

sys.modules["uvicorn"] = None
'''

FALSO_SYNC_API = '''\
"""Doble de ``playwright.sync_api`` controlado por FALSO_PLAYWRIGHT_MODO."""
import os
import re
import sys
import urllib.request

MODO = os.environ["FALSO_PLAYWRIGHT_MODO"]
RUTA_REGISTRO = os.environ["FALSO_PLAYWRIGHT_REGISTRO"]


def _anotar(evento):
    with open(RUTA_REGISTRO, "a", encoding="utf-8") as registro:
        registro.write(evento + "\\n")


class Error(Exception):
    pass


class TimeoutError(Error):
    pass


class ConsoleMessage:
    def __init__(self, tipo, texto):
        self.type = tipo
        self.text = texto


class Response:
    status = 200
    ok = True


class Page:
    def __init__(self):
        self._manejadores = {}
        self._titulo = ""

    def on(self, evento, manejador):
        self._manejadores.setdefault(evento, []).append(manejador)

    def _emitir(self, evento, valor):
        for manejador in self._manejadores.get(evento, []):
            manejador(valor)

    def set_default_timeout(self, _milisegundos):
        pass

    def goto(self, url, **_opciones):
        _anotar("goto " + url)
        with urllib.request.urlopen(url, timeout=10) as respuesta:
            html = respuesta.read().decode("utf-8")
        self._titulo = re.search(r"<title>(.*?)</title>", html, re.DOTALL).group(1).strip()
        if MODO == "titulo_incorrecto":
            self._titulo = "Otra aplicacion"
        elif MODO == "consola_error":
            self._emitir("console", ConsoleMessage("error", "fallo de consola"))
        elif MODO == "consola_sin_errores":
            self._emitir("console", ConsoleMessage("log", "traza"))
            self._emitir("console", ConsoleMessage("warning", "aviso"))
        elif MODO == "pageerror":
            self._emitir("pageerror", Error("excepcion de JS"))
        return Response()

    def title(self):
        return self._titulo

    def close(self):
        pass


class BrowserContext:
    def new_page(self):
        return Page()

    def set_default_timeout(self, _milisegundos):
        pass

    def close(self):
        pass


class Browser:
    def new_context(self, **_opciones):
        return BrowserContext()

    def new_page(self, **_opciones):
        return Page()

    def close(self):
        _anotar("browser.close")


class BrowserType:
    @property
    def executable_path(self):
        return "/no/existe/chromium" if MODO == "sin_chromium" else sys.executable

    def launch(self, **opciones):
        _anotar("launch headless=" + str(opciones.get("headless", True)))
        if MODO == "sin_chromium":
            raise Error("BrowserType.launch: Executable doesn't exist at /no/existe/chromium")
        return Browser()


class Playwright:
    chromium = BrowserType()

    def stop(self):
        _anotar("playwright.stop")


class PlaywrightContextManager:
    def __enter__(self):
        return self.start()

    def __exit__(self, *_excinfo):
        Playwright().stop()

    def start(self):
        return Playwright()


def sync_playwright():
    return PlaywrightContextManager()
'''

SONDA_TEST = '''\
"""Pide /api/cazadores al servidor del fixture y anota el resultado."""
import json
import os
import urllib.request
from pathlib import Path


def test_sonda(servidor_e2e):
    url = servidor_e2e.rstrip("/") + "/api/cazadores"
    with urllib.request.urlopen(url, timeout=10) as respuesta:
        estado = respuesta.status
        cazadores = json.loads(respuesta.read().decode("utf-8"))
    resultado = {"url_base": servidor_e2e, "estado": estado, "num_cazadores": len(cazadores)}
    Path(os.environ["SONDA_RESULTADO"]).write_text(json.dumps(resultado), encoding="utf-8")
'''

SONDA_PLUGIN = '''\
"""Plugin de pytest: al acabar la sesion (fixtures ya cerrados) mira si el puerto esta libre."""
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit


def pytest_sessionfinish(session):
    ruta = Path(os.environ["SONDA_RESULTADO"])
    if not ruta.exists():
        return
    resultado = json.loads(ruta.read_text(encoding="utf-8"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        # En POSIX, SO_REUSEADDR ignora TIME_WAIT pero no un servidor que siga escuchando.
        if os.name != "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", urlsplit(resultado["url_base"]).port))
            resultado["puerto_libre_tras_teardown"] = True
        except OSError:
            resultado["puerto_libre_tras_teardown"] = False
    ruta.write_text(json.dumps(resultado), encoding="utf-8")
'''


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _entorno(rutas_python: list[Path], **variables: str) -> dict[str, str]:
    """Entorno del pytest anidado: aislado de la historia y con ``rutas_python`` por delante."""
    entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES_AISLADAS}
    heredado = [entorno["PYTHONPATH"]] if entorno.get("PYTHONPATH") else []
    entorno["PYTHONPATH"] = os.pathsep.join([*(str(r) for r in rutas_python), *heredado])
    entorno["PYTHONDONTWRITEBYTECODE"] = "1"
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno.update(variables)
    return entorno


def _pytest(args: list[str], cwd: Path, entorno: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args],
        cwd=cwd,
        env=entorno,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_PYTEST_S,
        check=False,
    )


def _resumen(resultado: subprocess.CompletedProcess) -> str:
    """Ultima linea no vacia de la salida de pytest (``== 1 passed in 0.1s ==``)."""
    return resultado.stdout.strip().splitlines()[-1]


def _ejecutar_e2e(
    tmp_path: Path,
    modo: str,
    *,
    requerir: str | None = None,
    args: tuple[str, ...] = ("-m", "e2e"),
    sin_uvicorn: bool = False,
) -> subprocess.CompletedProcess:
    """Ejecuta ``pytest -m e2e`` en la raiz del proyecto con el entorno de Playwright de ``modo``.

    ``modo`` es ``sin_playwright`` o un valor de FALSO_PLAYWRIGHT_MODO.
    """
    variables = {
        "FALSO_PLAYWRIGHT_MODO": modo,
        "FALSO_PLAYWRIGHT_REGISTRO": str(tmp_path / "registro.txt"),
    }
    if requerir is not None:
        variables["GRIMCOVEN_REQUIRE_E2E"] = requerir

    dobles = tmp_path / "dobles"
    if modo == "sin_playwright":
        dobles.mkdir()
        (dobles / "bloqueo_playwright.py").write_text(BLOQUEO_PLAYWRIGHT, encoding="utf-8")
        plugins = ["-p", "bloqueo_playwright"]
    else:
        paquete = dobles / "playwright"
        paquete.mkdir(parents=True)
        (paquete / "__init__.py").write_text("", encoding="utf-8")
        (paquete / "sync_api.py").write_text(FALSO_SYNC_API, encoding="utf-8")
        plugins = []

    if sin_uvicorn:
        (dobles / "bloqueo_uvicorn.py").write_text(BLOQUEO_UVICORN, encoding="utf-8")
        plugins += ["-p", "bloqueo_uvicorn"]

    return _pytest(
        [*plugins, "-rs", "--tb=short", *args],
        cwd=RAIZ,
        entorno=_entorno([dobles], **variables),
    )


def _registro(tmp_path: Path) -> list[str]:
    ruta = tmp_path / "registro.txt"
    return ruta.read_text(encoding="utf-8").splitlines() if ruta.exists() else []


def _sonda_servidor(tmp_path: Path, **variables: str) -> tuple[subprocess.CompletedProcess, dict]:
    """Usa el fixture ``servidor_e2e`` real desde un test externo al proyecto.

    Carga ``tests/e2e/conftest.py`` como plugin para poder observar el puerto despues del
    teardown del fixture y antes de que termine el proceso (al terminar se liberaria igual).
    Devuelve la salida de pytest y lo que anoto la sonda (vacio si no llego a anotar nada).
    """
    directorio = tmp_path / f"sonda_{len(list(tmp_path.iterdir()))}"
    directorio.mkdir()
    (directorio / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (directorio / "test_sonda.py").write_text(SONDA_TEST, encoding="utf-8")
    (directorio / "sonda_plugin.py").write_text(SONDA_PLUGIN, encoding="utf-8")
    ruta_resultado = directorio / "resultado.json"

    salida = _pytest(
        ["-p", "conftest", "-p", "sonda_plugin", "--tb=short", "test_sonda.py"],
        cwd=directorio,
        entorno=_entorno(
            [directorio, DIR_E2E, RAIZ / "src"],
            SONDA_RESULTADO=str(ruta_resultado),
            **variables,
        ),
    )
    hay_datos = ruta_resultado.exists()
    return salida, json.loads(ruta_resultado.read_text(encoding="utf-8")) if hay_datos else {}


def _comprobar_servidor_correcto(salida: subprocess.CompletedProcess, datos: dict) -> None:
    assert salida.returncode == 0, salida.stdout
    assert datos["estado"] == 200
    assert datos["num_cazadores"] > 0
    assert datos["puerto_libre_tras_teardown"] is True, "El puerto sigue ocupado tras el teardown"


# ---------------------------------------------------------------------------
# CA2: fixture de servidor
# ---------------------------------------------------------------------------


def test_ca2_servidor_usa_factory_port_y_libera_el_puerto(tmp_path: Path) -> None:
    salida, datos = _sonda_servidor(tmp_path, FACTORY_PORT=str(PUERTO_CA2))

    _comprobar_servidor_correcto(salida, datos)
    assert datos["url_base"].rstrip("/") == f"http://127.0.0.1:{PUERTO_CA2}"


def test_ca2_sin_factory_port_el_sistema_elige_el_puerto(tmp_path: Path) -> None:
    """Dos arranques dan puertos distintos: descarta un puerto por defecto fijo."""
    salida_1, datos_1 = _sonda_servidor(tmp_path)
    salida_2, datos_2 = _sonda_servidor(tmp_path)

    _comprobar_servidor_correcto(salida_1, datos_1)
    _comprobar_servidor_correcto(salida_2, datos_2)
    partes_1 = urlsplit(datos_1["url_base"])
    partes_2 = urlsplit(datos_2["url_base"])
    assert partes_1.hostname == partes_2.hostname == "127.0.0.1"
    assert partes_1.port != partes_2.port


def test_ca2_factory_port_vacio_equivale_a_no_definido(tmp_path: Path) -> None:
    salida, datos = _sonda_servidor(tmp_path, FACTORY_PORT="")

    _comprobar_servidor_correcto(salida, datos)
    assert urlsplit(datos["url_base"]).port


def test_ca2_puerto_ocupado_falla_y_lo_indica(tmp_path: Path) -> None:
    """Caso limite: si FACTORY_PORT esta ocupado no se cuelga ni responde otro servidor."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupante:
        ocupante.bind(("127.0.0.1", 0))
        ocupante.listen()
        puerto = ocupante.getsockname()[1]
        salida, _ = _sonda_servidor(tmp_path, FACTORY_PORT=str(puerto))

    assert salida.returncode == 1, salida.stdout
    assert re.search(r"\b1 error\b", _resumen(salida)), salida.stdout
    assert str(puerto) in salida.stdout


def _simbolos_de_codigo(fuente: str) -> set[str]:
    """Nombres, atributos y cadenas del codigo, sin docstrings ni comentarios."""
    arbol = ast.parse(fuente)
    docstrings = {
        id(nodo.body[0].value)
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and nodo.body
        and isinstance(nodo.body[0], ast.Expr)
        and isinstance(nodo.body[0].value, ast.Constant)
    }
    simbolos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            simbolos.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            simbolos.add(nodo.attr)
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if id(nodo) not in docstrings:
                simbolos.add(nodo.value)
    return simbolos


def test_ca2_fixture_usa_create_app_solo_en_loopback() -> None:
    """Lo que la sonda no distingue desde fuera: usa la factoria y escucha solo en loopback."""
    simbolos = _simbolos_de_codigo(RUTA_CONFTEST.read_text(encoding="utf-8"))
    assert "create_app" in simbolos or "grimcoven_equipos.app:create_app" in simbolos
    assert "127.0.0.1" in simbolos
    assert "0.0.0.0" not in simbolos


# ---------------------------------------------------------------------------
# CA3: test de humo (doble de Playwright contra el servidor real)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("requerir", [None, "1"], ids=["opcional", "obligatorio"])
def test_ca3_humo_pasa_con_navegador_y_portada_correcta(
    tmp_path: Path, requerir: str | None
) -> None:
    resultado = _ejecutar_e2e(tmp_path, "ok", requerir=requerir)

    assert resultado.returncode == 0, resultado.stdout
    resumen = _resumen(resultado)
    assert re.search(r"\b\d+ passed\b", resumen), resultado.stdout
    assert "skipped" not in resumen


def test_ca3_humo_abre_la_raiz_y_libera_el_navegador(tmp_path: Path) -> None:
    resultado = _ejecutar_e2e(tmp_path, "ok")
    assert resultado.returncode == 0, resultado.stdout

    eventos = _registro(tmp_path)
    visitas = [e.removeprefix("goto ") for e in eventos if e.startswith("goto ")]
    assert visitas, f"No se abrio ninguna pagina: {eventos}"
    assert urlsplit(visitas[0]).path in ("", "/")
    assert urlsplit(visitas[0]).hostname == "127.0.0.1"
    # La CI no tiene pantalla: el navegador debe ir sin interfaz grafica.
    assert "launch headless=True" in eventos
    assert "browser.close" in eventos
    assert "playwright.stop" in eventos


@pytest.mark.parametrize("modo", ["titulo_incorrecto", "consola_error", "pageerror"])
def test_ca3_humo_detecta_titulo_y_errores_de_js(tmp_path: Path, modo: str) -> None:
    resultado = _ejecutar_e2e(tmp_path, modo)

    assert resultado.returncode == 1, resultado.stdout
    assert re.search(r"\b1 failed\b", _resumen(resultado)), resultado.stdout


def test_ca3_humo_ignora_los_mensajes_de_consola_que_no_son_error(tmp_path: Path) -> None:
    resultado = _ejecutar_e2e(tmp_path, "consola_sin_errores")

    assert resultado.returncode == 0, resultado.stdout
    assert re.search(r"\b\d+ passed\b", _resumen(resultado)), resultado.stdout


# ---------------------------------------------------------------------------
# CA4: sin Playwright o sin Chromium, los tests se saltan
# ---------------------------------------------------------------------------


def _comprobar_saltados(resultado: subprocess.CompletedProcess) -> None:
    assert resultado.returncode == 0, resultado.stdout
    resumen = _resumen(resultado)
    assert re.search(r"\b\d+ skipped\b", resumen), resultado.stdout
    assert not re.search(r"\b(passed|failed|errors?)\b", resumen), resultado.stdout
    assert re.search(r"^SKIPPED \[\d+\].*Playwright", resultado.stdout, re.MULTILINE), (
        resultado.stdout
    )


@pytest.mark.parametrize("modo", ["sin_playwright", "sin_chromium"])
def test_ca4_sin_navegador_los_tests_se_saltan(tmp_path: Path, modo: str) -> None:
    _comprobar_saltados(_ejecutar_e2e(tmp_path, modo))


@pytest.mark.parametrize("valor", ["", "0"])
def test_ca4_require_vacio_o_cero_no_obliga(tmp_path: Path, valor: str) -> None:
    _comprobar_saltados(_ejecutar_e2e(tmp_path, "sin_chromium", requerir=valor))


@pytest.mark.parametrize("modo", ["sin_playwright", "sin_chromium"])
def test_ca4_sin_marcador_tambien_se_saltan_como_en_el_job_ci(tmp_path: Path, modo: str) -> None:
    """El job 'ci' lanza pytest sin ``-m``, sin Chromium: no debe romperse por los e2e."""
    _comprobar_saltados(_ejecutar_e2e(tmp_path, modo, args=("tests/e2e",)))


@pytest.mark.parametrize("modo", ["sin_playwright", "sin_chromium"])
def test_ca4_se_saltan_antes_de_arrancar_el_servidor(tmp_path: Path, modo: str) -> None:
    """Caso limite: sin navegador se decide antes de tocar el servidor (ni hace falta uvicorn)."""
    _comprobar_saltados(_ejecutar_e2e(tmp_path, modo, sin_uvicorn=True))


# ---------------------------------------------------------------------------
# CA5: con GRIMCOVEN_REQUIRE_E2E=1, los tests fallan
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modo", ["sin_playwright", "sin_chromium"])
def test_ca5_require_e2e_hace_fallar_los_tests(tmp_path: Path, modo: str) -> None:
    resultado = _ejecutar_e2e(tmp_path, modo, requerir="1")

    assert resultado.returncode == 1, resultado.stdout
    resumen = _resumen(resultado)
    assert re.search(r"\b\d+ (failed|errors?)\b", resumen), resultado.stdout
    assert "skipped" not in resumen, resultado.stdout
    assert re.search(
        r"Playwright.*obligatori|obligatori.*Playwright", resultado.stdout, re.IGNORECASE
    ), resultado.stdout


@pytest.mark.parametrize("modo", ["sin_playwright", "sin_chromium"])
def test_ca5_el_mensaje_de_playwright_no_depende_del_servidor(tmp_path: Path, modo: str) -> None:
    """Caso limite: sin navegador ni uvicorn, el motivo del fallo sigue siendo Playwright."""
    resultado = _ejecutar_e2e(tmp_path, modo, requerir="1", sin_uvicorn=True)

    assert resultado.returncode == 1, resultado.stdout
    assert re.search(r"Playwright es obligatorio", resultado.stdout), resultado.stdout
