"""Fixtures de los tests de navegador (US-013).

- ``servidor_e2e``: arranca ``create_app()`` en 127.0.0.1, en ``FACTORY_PORT`` o, si no esta
  definido o esta vacio, en un puerto libre elegido por el sistema. Entrega la URL base
  (``http://127.0.0.1:<puerto>``) y libera el puerto en el teardown.
- ``pagina_e2e``: entrega una ``Page`` de Chromium (Playwright, sin interfaz grafica). Sin
  Playwright o sin Chromium, salta el test con un motivo que menciona Playwright; con
  ``GRIMCOVEN_REQUIRE_E2E=1`` lo hace fallar con un mensaje de que Playwright es obligatorio.

Playwright y uvicorn se importan dentro de los fixtures: un fallo de importacion aqui arriba
romperia la recogida de toda la suite, no solo la de los tests e2e.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any, NoReturn

import pytest

HOST = "127.0.0.1"
TIMEOUT_SERVIDOR_S = 15


def _navegador_no_disponible(motivo: str) -> NoReturn:
    """Salta el test, o lo hace fallar si la CI exige el navegador."""
    if os.environ.get("GRIMCOVEN_REQUIRE_E2E") == "1":
        pytest.fail(f"Playwright es obligatorio (GRIMCOVEN_REQUIRE_E2E=1): {motivo}", pytrace=False)
    pytest.skip(f"Playwright o Chromium no disponibles: {motivo}")


@pytest.fixture(scope="session")
def navegador_e2e() -> Iterator[Any]:
    """Chromium sin interfaz grafica, compartido por toda la sesion."""
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as error:
        _navegador_no_disponible(str(error))

    with sync_playwright() as playwright:
        try:
            navegador = playwright.chromium.launch(headless=True)
        except Error as error:
            # El resto del mensaje de Playwright es un recuadro con instrucciones de instalacion.
            _navegador_no_disponible(str(error).splitlines()[0])
        yield navegador
        navegador.close()


@pytest.fixture(autouse=True)
def _comprobar_navegador_antes_de_nada(request: pytest.FixtureRequest) -> None:
    """Los tests e2e deciden si se saltan antes de arrancar el servidor.

    Por eso ``servidor_e2e`` tiene alcance de funcion: pytest prepara antes los fixtures de mayor
    alcance, y uno de sesion se arrancaria (o fallaria, sin uvicorn) antes de llegar aqui.
    """
    if request.node.get_closest_marker("e2e"):
        request.getfixturevalue("navegador_e2e")


@pytest.fixture
def pagina_e2e(navegador_e2e: Any) -> Iterator[Any]:
    """Pagina en un contexto propio, para que los tests no compartan cookies ni almacenamiento."""
    contexto = navegador_e2e.new_context()
    yield contexto.new_page()
    contexto.close()


def _socket_del_servidor(puerto: int) -> socket.socket:
    """Reserva el puerto aqui para que un puerto ocupado sea un error claro.

    uvicorn activa SO_REUSEADDR al abrir su propio socket: en Windows eso le dejaria compartir
    un puerto ya ocupado, y responderia otro servidor. En POSIX si hace falta para no chocar con
    las conexiones en TIME_WAIT de una ejecucion anterior, y no permite robar un puerto en uso.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name != "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, puerto))
    except OSError as error:
        sock.close()
        pytest.fail(f"No se puede usar el puerto {puerto} de {HOST}: {error}", pytrace=False)
    return sock


@pytest.fixture
def servidor_e2e() -> Iterator[str]:
    """Sirve la aplicacion real en un hilo y entrega su URL base."""
    import uvicorn

    from grimcoven_equipos.app import create_app

    sock = _socket_del_servidor(int(os.environ.get("FACTORY_PORT") or 0))
    puerto = sock.getsockname()[1]
    config = uvicorn.Config(
        create_app(), log_level="warning", timeout_graceful_shutdown=TIMEOUT_SERVIDOR_S
    )
    servidor = uvicorn.Server(config)
    hilo = threading.Thread(target=servidor.run, kwargs={"sockets": [sock]}, daemon=True)
    hilo.start()

    limite = time.monotonic() + TIMEOUT_SERVIDOR_S
    while not servidor.started:
        if not hilo.is_alive() or time.monotonic() > limite:
            servidor.should_exit = True
            sock.close()
            pytest.fail(f"El servidor no arranco en {HOST}:{puerto}", pytrace=False)
        time.sleep(0.05)

    yield f"http://{HOST}:{puerto}"

    servidor.should_exit = True
    hilo.join(TIMEOUT_SERVIDOR_S * 2)
    sock.close()
    assert not hilo.is_alive(), f"El servidor de {HOST}:{puerto} no se detuvo"
