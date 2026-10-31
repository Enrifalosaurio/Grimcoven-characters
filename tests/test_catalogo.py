"""Tests de US-001: catálogo de cazadores y Griefbound de Grimcoven.

Cada test indica el criterio de aceptación (CA<n>) que cubre, en el orden de la historia.
Formato de los JSON: una lista de objetos en la raíz.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

from grimcoven_equipos.catalogo import cargar_cazadores, cargar_griefbound

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data"
RESOURCES = RAIZ / "Resources"

FICHERO_R = "GC_Rulebook_280x280mm_bleed3mm [36 pages]_[lowres]_compressed.pdf"
FICHERO_H = "EN_Hunters Expansion.pdf"
FICHERO_F = "EN_Forgotten Entities.pdf"

IDS_CAZADORES = [
    "duality",
    "gunslinger",
    "keeper",
    "technomancer",
    "mannequin",
    "death-jester",
    "clockwork-giant",
    "twins",
]
IDS_GRIEFBOUND = [
    "undead-general",
    "swarm-mistress",
    "convergence",
    "tormentor",
    "graveyard-dragon",
    "devourer",
    "chimera",
    "striga",
]
ROLES_VALIDOS = {"tanque", "dano", "apoyo", "control"}


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def cazadores() -> dict[str, Any]:
    return {c.id: c for c in cargar_cazadores()}


@pytest.fixture(scope="module")
def griefbound() -> dict[str, Any]:
    return {g.id: g for g in cargar_griefbound()}


@pytest.fixture(scope="module")
def cazadores_json() -> list[dict[str, Any]]:
    return json.loads((DATA / "cazadores.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def griefbound_json() -> list[dict[str, Any]]:
    return json.loads((DATA / "griefbound.json").read_text(encoding="utf-8"))


def _cazador(id_: str = "duality", **cambios: Any) -> dict[str, Any]:
    """Cazador válido mínimo para construir JSON de prueba."""
    base: dict[str, Any] = {
        "id": id_,
        "nombre": id_.title(),
        "expansion": "base",
        "complejidad": "Media",
        "roles": ["dano"],
        "contrarresta": [],
        "vida": None,
        "movimiento": None,
        "fuente": {"fichero": FICHERO_R, "pagina": 27},
    }
    base.update(cambios)
    return base


def _griefbound(id_: str = "convergence", **cambios: Any) -> dict[str, Any]:
    """Griefbound válido mínimo para construir JSON de prueba."""
    base: dict[str, Any] = {
        "id": id_,
        "nombre": id_.title(),
        "tipo": "griefbound",
        "expansion": "base",
        "amenazas": ["quemadura"],
        "fuente": {"fichero": FICHERO_R, "pagina": 30},
    }
    base.update(cambios)
    return base


def _escribir(tmp_path: Path, nombre: str, datos: list[dict[str, Any]]) -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


# --------------------------------------------------------------------------- CA1


def _nombres_dependencias(especificaciones: list[str]) -> set[str]:
    return {re.split(r"[\s<>=!~\[;]", e, maxsplit=1)[0].lower() for e in especificaciones}


def test_ca1_pyproject_declara_dependencias() -> None:
    pyproject = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    proyecto = pyproject["project"]
    assert {"fastapi", "jinja2", "pydantic"} <= _nombres_dependencias(proyecto["dependencies"])
    dev = proyecto["optional-dependencies"]["dev"]
    assert {"pytest", "httpx", "ruff"} <= _nombres_dependencias(dev)


def test_ca1_paquete_en_src() -> None:
    import grimcoven_equipos

    assert (RAIZ / "src" / "grimcoven_equipos" / "__init__.py").is_file()
    assert Path(grimcoven_equipos.__file__).resolve().parent == (
        RAIZ / "src" / "grimcoven_equipos"
    )


# --------------------------------------------------------------------------- CA2


def test_ca2_carga_exactamente_8_cazadores() -> None:
    lista = cargar_cazadores()
    assert len(lista) == 8
    assert sorted(c.id for c in lista) == sorted(IDS_CAZADORES)


# --------------------------------------------------------------------------- CA3


def test_ca3_json_de_cazadores_tiene_todos_los_campos(cazadores_json) -> None:
    campos = {
        "id",
        "nombre",
        "expansion",
        "complejidad",
        "roles",
        "contrarresta",
        "vida",
        "movimiento",
        "fuente",
    }
    for entrada in cazadores_json:
        assert campos <= set(entrada), entrada.get("id")
        assert set(entrada["fuente"]) >= {"fichero", "pagina"}, entrada["id"]


def test_ca3_cada_cazador_es_valido(cazadores) -> None:
    for c in cazadores.values():
        assert isinstance(c.nombre, str) and c.nombre.strip(), c.id
        assert c.expansion in {"base", "hunters"}, c.id
        assert isinstance(c.complejidad, str) and c.complejidad, c.id
        assert len(c.roles) > 0, c.id
        assert set(c.roles) <= ROLES_VALIDOS, c.id
        assert isinstance(c.contrarresta, list), c.id
        assert c.vida is None or (isinstance(c.vida, int) and not isinstance(c.vida, bool))
        assert c.movimiento is None or (
            isinstance(c.movimiento, int) and not isinstance(c.movimiento, bool)
        )
        assert isinstance(c.fuente.fichero, str)
        assert isinstance(c.fuente.pagina, int)


def test_ca3_expansion_de_cada_cazador(cazadores) -> None:
    for id_ in IDS_CAZADORES[:6]:
        assert cazadores[id_].expansion == "base", id_
    assert cazadores["clockwork-giant"].expansion == "hunters"
    assert cazadores["twins"].expansion == "hunters"


def test_ca3_fuentes_de_cazadores_segun_notas(cazadores) -> None:
    esperado = {
        "duality": (FICHERO_R, 27),
        "gunslinger": (FICHERO_R, 27),
        "keeper": (FICHERO_R, 28),
        "technomancer": (FICHERO_R, 28),
        "mannequin": (FICHERO_R, 29),
        "death-jester": (FICHERO_R, 29),
        "clockwork-giant": (FICHERO_H, 2),
        "twins": (FICHERO_H, 3),
    }
    for id_, (fichero, pagina) in esperado.items():
        fuente = cazadores[id_].fuente
        assert (fuente.fichero, fuente.pagina) == (fichero, pagina), id_


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"roles": []}, id="roles-vacios"),
        pytest.param({"expansion": "forgotten-entities"}, id="expansion-invalida"),
        pytest.param({"vida": "doce"}, id="vida-no-entera"),
        pytest.param({"fuente": {"fichero": FICHERO_R, "pagina": 0}}, id="pagina-0"),
        pytest.param({"fuente": {"fichero": FICHERO_R}}, id="fuente-sin-pagina"),
    ],
)
def test_ca3_cazador_invalido_lanza_value_error(tmp_path, cambios) -> None:
    ruta = _escribir(tmp_path, "cazadores.json", [_cazador("duality", **cambios)])
    with pytest.raises(ValueError):
        cargar_cazadores(ruta)


def test_ca3_cazador_sin_campo_obligatorio_lanza_value_error(tmp_path) -> None:
    entrada = _cazador("duality")
    del entrada["complejidad"]
    ruta = _escribir(tmp_path, "cazadores.json", [entrada])
    with pytest.raises(ValueError):
        cargar_cazadores(ruta)


def test_ca3_carga_json_valido_desde_ruta(tmp_path) -> None:
    ruta = _escribir(
        tmp_path,
        "cazadores.json",
        [_cazador("duality"), _cazador("keeper", vida=10, movimiento=3)],
    )
    lista = cargar_cazadores(ruta)
    assert [c.id for c in lista] == ["duality", "keeper"]
    assert lista[1].vida == 10 and lista[1].movimiento == 3


# --------------------------------------------------------------------------- CA4


def test_ca4_complejidad(cazadores) -> None:
    esperado = {
        "duality": "Media",
        "gunslinger": "Baja",
        "keeper": "Baja-Media",
        "technomancer": "Media-Alta",
        "mannequin": "Alta",
        "death-jester": "Media-Alta",
        "clockwork-giant": "Media",
        "twins": "Alta",
    }
    assert {id_: c.complejidad for id_, c in cazadores.items()} == esperado


# --------------------------------------------------------------------------- CA5


def test_ca5_roles(cazadores) -> None:
    esperado = {
        "duality": {"dano", "tanque", "apoyo"},
        "gunslinger": {"dano", "control"},
        "keeper": {"dano", "tanque"},
        "technomancer": {"dano", "apoyo"},
        "mannequin": {"apoyo", "dano", "tanque", "control"},
        "death-jester": {"dano", "apoyo"},
        "clockwork-giant": {"tanque", "dano"},
        "twins": {"apoyo", "dano"},
    }
    assert {id_: set(c.roles) for id_, c in cazadores.items()} == esperado


# --------------------------------------------------------------------------- CA6


def test_ca6_vida_y_movimiento(cazadores) -> None:
    assert (cazadores["technomancer"].vida, cazadores["technomancer"].movimiento) == (12, 2)
    assert (cazadores["gunslinger"].vida, cazadores["gunslinger"].movimiento) == (13, 2)
    for id_ in set(IDS_CAZADORES) - {"technomancer", "gunslinger"}:
        assert cazadores[id_].vida is None, id_
        assert cazadores[id_].movimiento is None, id_


def test_ca6_vida_y_movimiento_null_en_json(cazadores_json) -> None:
    for entrada in cazadores_json:
        if entrada["id"] not in {"technomancer", "gunslinger"}:
            assert entrada["vida"] is None and entrada["movimiento"] is None, entrada["id"]


# --------------------------------------------------------------------------- CA7


def test_ca7_carga_16_griefbound() -> None:
    lista = cargar_griefbound()
    assert len(lista) == 16
    griefbound = sorted(g.id for g in lista if g.tipo == "griefbound")
    pretenders = sorted(g.id for g in lista if g.tipo == "pretender")
    assert griefbound == sorted(IDS_GRIEFBOUND)
    assert pretenders == sorted(f"pretender-{id_}" for id_ in IDS_CAZADORES)


# --------------------------------------------------------------------------- CA8


def test_ca8_json_de_griefbound_tiene_todos_los_campos(griefbound_json) -> None:
    campos = {"id", "nombre", "tipo", "expansion", "amenazas", "fuente"}
    for entrada in griefbound_json:
        assert campos <= set(entrada), entrada.get("id")
        assert set(entrada["fuente"]) >= {"fichero", "pagina"}, entrada["id"]
        if entrada["tipo"] == "pretender":
            assert "cazador_origen" in entrada, entrada["id"]


def test_ca8_cada_griefbound_es_valido(griefbound, cazadores) -> None:
    for g in griefbound.values():
        assert isinstance(g.nombre, str) and g.nombre.strip(), g.id
        assert g.tipo in {"griefbound", "pretender"}, g.id
        assert g.expansion in {"base", "hunters", "forgotten-entities"}, g.id
        assert isinstance(g.amenazas, list), g.id
        assert isinstance(g.fuente.fichero, str)
        assert isinstance(g.fuente.pagina, int)
        if g.tipo == "pretender":
            assert g.cazador_origen in cazadores, g.id
            assert g.id == f"pretender-{g.cazador_origen}"


def test_ca8_expansion_y_fuente_de_griefbound(griefbound) -> None:
    for id_ in ["undead-general", "swarm-mistress", "convergence", "tormentor",
                "graveyard-dragon", "devourer"]:
        assert griefbound[id_].expansion == "base", id_
        assert griefbound[id_].fuente.fichero == FICHERO_R, id_
        assert griefbound[id_].fuente.pagina in {30, 35}, id_
    for id_ in ["chimera", "striga"]:
        assert griefbound[id_].expansion == "forgotten-entities", id_
        assert griefbound[id_].fuente.fichero == FICHERO_F, id_
        assert griefbound[id_].fuente.pagina in {1, 2}, id_
    for id_ in IDS_CAZADORES[:6]:
        p = griefbound[f"pretender-{id_}"]
        assert p.expansion == "base", p.id
        assert p.fuente.fichero == FICHERO_R, p.id
        assert p.fuente.pagina in {31, 32}, p.id
    for id_ in ["clockwork-giant", "twins"]:
        p = griefbound[f"pretender-{id_}"]
        assert p.expansion == "hunters", p.id
        assert (p.fuente.fichero, p.fuente.pagina) == (FICHERO_H, 4), p.id


@pytest.mark.parametrize(
    "cambios",
    [
        pytest.param({"tipo": "jefe"}, id="tipo-invalido"),
        pytest.param({"expansion": "personal-stories"}, id="expansion-invalida"),
        pytest.param({"amenazas": "quemadura"}, id="amenazas-no-lista"),
        pytest.param({"fuente": {"fichero": FICHERO_R, "pagina": -3}}, id="pagina-negativa"),
    ],
)
def test_ca8_griefbound_invalido_lanza_value_error(tmp_path, cambios) -> None:
    ruta = _escribir(tmp_path, "griefbound.json", [_griefbound("convergence", **cambios)])
    with pytest.raises(ValueError):
        cargar_griefbound(ruta)


def test_ca8_pretender_sin_cazador_origen_lanza_value_error(tmp_path) -> None:
    entrada = _griefbound("pretender-keeper", tipo="pretender", amenazas=[])
    ruta = _escribir(tmp_path, "griefbound.json", [entrada])
    with pytest.raises(ValueError):
        cargar_griefbound(ruta)


def test_ca8_griefbound_duplicado_lanza_value_error(tmp_path) -> None:
    ruta = _escribir(
        tmp_path, "griefbound.json", [_griefbound("tormentor"), _griefbound("tormentor")]
    )
    with pytest.raises(ValueError, match="id duplicado"):
        cargar_griefbound(ruta)


# --------------------------------------------------------------------------- CA9


def test_ca9_amenazas(griefbound) -> None:
    esperado = {
        "convergence": ["quemadura"],
        "graveyard-dragon": ["maldicion"],
        "devourer": ["hambre"],
        "tormentor": ["heridas"],
        "swarm-mistress": ["enjambre"],
        "undead-general": ["estandartes"],
        "chimera": ["defensa"],
        "striga": ["obsesion"],
    }
    for id_, amenazas in esperado.items():
        assert list(griefbound[id_].amenazas) == amenazas, id_
    for id_ in IDS_CAZADORES:
        assert list(griefbound[f"pretender-{id_}"].amenazas) == [], id_


# --------------------------------------------------------------------------- CA10


def test_ca10_contrarresta(cazadores) -> None:
    esperado = {
        "technomancer": {"quemadura", "maldicion"},
        "keeper": {"hambre", "enjambre", "heridas"},
        "gunslinger": {"enjambre"},
        "clockwork-giant": {"heridas"},
        "duality": {"heridas"},
        "mannequin": set(),
        "death-jester": set(),
        "twins": set(),
    }
    assert {id_: set(c.contrarresta) for id_, c in cazadores.items()} == esperado
    for c in cazadores.values():
        assert len(c.contrarresta) == len(set(c.contrarresta)), c.id


def test_ca10_contrarresta_usa_amenazas_existentes(cazadores, griefbound) -> None:
    amenazas = {a for g in griefbound.values() for a in g.amenazas}
    for c in cazadores.values():
        assert set(c.contrarresta) <= amenazas, c.id


# --------------------------------------------------------------------------- CA11


def test_ca11_fuentes_apuntan_a_ficheros_de_resources(cazadores, griefbound) -> None:
    existentes = {p.name for p in RESOURCES.iterdir() if p.is_file()}
    for entrada in [*cazadores.values(), *griefbound.values()]:
        assert entrada.fuente.fichero in existentes, entrada.id
        assert isinstance(entrada.fuente.pagina, int) and entrada.fuente.pagina >= 1, entrada.id


def test_ca11_fuentes_en_json_crudo(cazadores_json, griefbound_json) -> None:
    for entrada in [*cazadores_json, *griefbound_json]:
        fuente = entrada["fuente"]
        assert (RESOURCES / fuente["fichero"]).is_file(), entrada["id"]
        assert type(fuente["pagina"]) is int and fuente["pagina"] >= 1, entrada["id"]


# --------------------------------------------------------------------------- CA12


def test_ca12_rol_invalido_lanza_value_error_con_id_y_rol(tmp_path) -> None:
    datos = [_cazador("duality"), _cazador("keeper", roles=["dano", "mago"])]
    ruta = _escribir(tmp_path, "cazadores.json", datos)
    with pytest.raises(ValueError) as excinfo:
        cargar_cazadores(ruta)
    mensaje = str(excinfo.value)
    assert "keeper" in mensaje
    assert "mago" in mensaje


# --------------------------------------------------------------------------- CA13


def test_ca13_id_duplicado_lanza_value_error(tmp_path) -> None:
    datos = [_cazador("twins"), _cazador("keeper"), _cazador("twins")]
    ruta = _escribir(tmp_path, "cazadores.json", datos)
    with pytest.raises(ValueError) as excinfo:
        cargar_cazadores(ruta)
    mensaje = str(excinfo.value)
    assert "id duplicado" in mensaje
    assert "twins" in mensaje


# --------------------------------------------------------------------------- CA14


def test_ca14_pretender_con_cazador_origen_inexistente(tmp_path) -> None:
    datos = [
        _griefbound("convergence"),
        _griefbound(
            "pretender-inexistente",
            tipo="pretender",
            amenazas=[],
            cazador_origen="inexistente",
            fuente={"fichero": FICHERO_R, "pagina": 31},
        ),
    ]
    ruta = _escribir(tmp_path, "griefbound.json", datos)
    with pytest.raises(ValueError, match="inexistente"):
        cargar_griefbound(ruta)


def test_ca14_cazador_origen_se_valida_contra_ruta_de_cazadores(tmp_path) -> None:
    ruta_cazadores = _escribir(tmp_path, "cazadores.json", [_cazador("duality")])
    pretender = _griefbound(
        "pretender-keeper",
        tipo="pretender",
        amenazas=[],
        cazador_origen="keeper",
        fuente={"fichero": FICHERO_R, "pagina": 31},
    )
    ruta = _escribir(tmp_path, "griefbound.json", [pretender])
    with pytest.raises(ValueError, match="keeper"):
        cargar_griefbound(ruta, ruta_cazadores=ruta_cazadores)


def test_ca14_pretender_valido_con_ruta_de_cazadores(tmp_path) -> None:
    ruta_cazadores = _escribir(tmp_path, "cazadores.json", [_cazador("keeper")])
    pretender = _griefbound(
        "pretender-keeper",
        tipo="pretender",
        amenazas=[],
        cazador_origen="keeper",
        fuente={"fichero": FICHERO_R, "pagina": 31},
    )
    ruta = _escribir(tmp_path, "griefbound.json", [pretender])
    (g,) = cargar_griefbound(ruta, ruta_cazadores=ruta_cazadores)
    assert g.cazador_origen == "keeper"


# --------------------------------------------------------------------------- CA15


def test_ca15_readme_documenta_inferencias_y_datos_que_faltan() -> None:
    readme = DATA / "README.md"
    assert readme.is_file()
    texto = readme.read_text(encoding="utf-8").lower()
    assert "infer" in texto
    for campo in ["roles", "contrarresta", "amenazas"]:
        assert campo in texto, campo
    assert "falta" in texto
    for dato in ["vida", "movimiento", "hunt book"]:
        assert dato in texto, dato
