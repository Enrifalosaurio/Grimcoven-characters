"""Tests de US-013: configuracion de Playwright en pyproject.toml y en el workflow de CI.

Cada test indica el criterio de aceptacion (CA<n>) que cubre. El workflow se comprueba con
regex para no anadir un parser de YAML a las dependencias.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
RUTA_PYPROJECT = RAIZ / "pyproject.toml"
RUTA_WORKFLOW = RAIZ / ".github" / "workflows" / "factory-ci.yml"

# Lo que hay antes de ``jobs:`` y el job 'ci' tal y como estaban antes de US-013.
PREAMBULO_ORIGINAL = """\
name: Factory CI

on:
  push:
    branches: [main, "factory/**"]
  pull_request:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: factory-ci-${{ github.ref }}
  cancel-in-progress: true

"""

JOB_CI_ORIGINAL = """\
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar dependencias
        run: |
          python -m pip install --upgrade pip
          pip install pytest ruff
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi
          if [ -f pyproject.toml ]; then pip install -e ".[dev]" || pip install -e . || true; fi

      - name: Lint
        run: ruff check .

      - name: Tests
        run: |
          # pytest devuelve 5 si no hay tests aún; se tolera
          pytest || [ $? -eq 5 ]
"""


@pytest.fixture(scope="module")
def pyproject() -> dict:
    return tomllib.loads(RUTA_PYPROJECT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def workflow() -> str:
    return RUTA_WORKFLOW.read_text(encoding="utf-8")


def _bloque_job(workflow: str, nombre: str) -> str | None:
    """Devuelve el cuerpo de un job (lineas con 4 o mas espacios o vacias), o None si no esta."""
    patron = rf"^  {re.escape(nombre)}:[ \t]*\n((?:[ \t]*\n|    .*\n)*)"
    coincidencia = re.search(patron, workflow + "\n", re.MULTILINE)
    return coincidencia.group(1) if coincidencia else None


@pytest.fixture(scope="module")
def job_e2e(workflow: str) -> str:
    """Cuerpo del job 'e2e' sin lineas de comentario (un paso comentado no cuenta)."""
    bloque = _bloque_job(workflow, "e2e")
    assert bloque is not None, "No existe el job 'e2e' en factory-ci.yml"
    return "\n".join(linea for linea in bloque.splitlines() if not linea.lstrip().startswith("#"))


def _posicion_comando(job: str, patron_comando: str) -> int:
    """Posicion de un comando que ocupa una linea entera (sin ``|| true`` ni similares)."""
    patron = rf"^\s*(?:(?:-\s+)?run:\s*)?{patron_comando}\s*$"
    coincidencia = re.search(patron, job, re.MULTILINE)
    assert coincidencia is not None, f"Falta un paso con /{patron_comando}/ en:\n{job}"
    return coincidencia.start()


# ---------------------------------------------------------------------------
# CA1: pyproject.toml
# ---------------------------------------------------------------------------


def test_ca1_playwright_en_dependencias_dev(pyproject: dict) -> None:
    assert "playwright>=1.48" in pyproject["project"]["optional-dependencies"]["dev"]


def test_ca1_playwright_no_esta_en_dependencias_de_produccion(pyproject: dict) -> None:
    """Pasa ya en la fase roja: protege que Playwright no entre en la imagen Docker."""
    dependencias = pyproject["project"]["dependencies"]
    assert not [d for d in dependencias if "playwright" in d.lower()]


def test_ca1_marcador_e2e_registrado(pyproject: dict) -> None:
    marcadores = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert [m for m in marcadores if re.match(r"e2e\s*:", m)]


def test_ca1_el_marcador_docker_se_conserva(pyproject: dict) -> None:
    """Pasa ya en la fase roja: protege el marcador existente al editar la lista."""
    marcadores = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert [m for m in marcadores if re.match(r"docker\s*:", m)]


# ---------------------------------------------------------------------------
# CA6: job 'e2e'
# ---------------------------------------------------------------------------


def test_ca6_job_e2e_corre_en_ubuntu_latest(job_e2e: str) -> None:
    assert re.search(r"^\s+runs-on:\s*ubuntu-latest\s*$", job_e2e, re.MULTILINE)


def test_ca6_job_e2e_prepara_checkout_y_python_312(job_e2e: str) -> None:
    assert re.search(r"uses:\s*actions/checkout@", job_e2e)
    assert re.search(r"uses:\s*actions/setup-python@", job_e2e)
    assert re.search(r"^\s+python-version:\s*[\"']?3\.12[\"']?\s*$", job_e2e, re.MULTILINE)


def test_ca6_job_e2e_ejecuta_los_comandos_en_orden(job_e2e: str) -> None:
    """Instala el proyecto, despues Chromium y por ultimo lanza los tests."""
    instalar = _posicion_comando(job_e2e, r'(?:python -m )?pip install -e "\.\[dev\]"')
    chromium = _posicion_comando(job_e2e, r"python -m playwright install --with-deps chromium")
    tests = _posicion_comando(job_e2e, r"(?:python -m )?pytest -m e2e(?:\s+-\S+)*")
    assert instalar < chromium < tests


def test_ca6_job_e2e_exige_playwright(job_e2e: str) -> None:
    assert re.search(r"^\s+GRIMCOVEN_REQUIRE_E2E:\s*[\"']?1[\"']?\s*$", job_e2e, re.MULTILINE)


def test_ca6_job_e2e_no_tolera_fallos(job_e2e: str) -> None:
    """Un fallo del job debe verse: nada de continue-on-error ni tolerar codigos de salida."""
    assert "continue-on-error" not in job_e2e
    assert "|| true" not in job_e2e
    assert "$?" not in job_e2e


# ---------------------------------------------------------------------------
# CA7: lo existente en el workflow no cambia
# ---------------------------------------------------------------------------


def test_ca7_disparadores_y_permisos_no_cambian(workflow: str) -> None:
    """Pasa ya en la fase roja: protege lo existente frente a la edicion del workflow."""
    preambulo, separador, _ = workflow.partition("jobs:\n")
    assert separador
    assert preambulo == PREAMBULO_ORIGINAL


def test_ca7_job_ci_no_cambia(workflow: str) -> None:
    """Pasa ya en la fase roja: protege lo existente frente a la edicion del workflow.

    US-012 cambia, de forma legitima, ``pytest`` por ``pytest -m "not docker"`` en este job;
    se normaliza para que el orden de merge de ambas historias no rompa este test.
    """
    bloque = _bloque_job(workflow, "ci")
    assert bloque is not None
    bloque = bloque.replace('pytest -m "not docker" ||', "pytest ||")
    assert bloque.rstrip() == JOB_CI_ORIGINAL.rstrip()


def test_ca7_el_workflow_no_concede_permisos_de_escritura(workflow: str) -> None:
    """Ni a nivel global ni en el job 'e2e', que hereda 'contents: read'."""
    assert not re.search(r":\s*write\b", workflow)
    bloque = _bloque_job(workflow, "e2e")
    assert bloque is not None, "No existe el job 'e2e' en factory-ci.yml"
    assert "permissions:" not in bloque
