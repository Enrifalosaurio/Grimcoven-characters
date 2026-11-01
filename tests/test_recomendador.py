"""Tests de US-004: API del recomendador de equipos contra un Griefbound.

Cada test indica el criterio de aceptación (CA<n>) que cubre.
Los tests de lógica pura usan fixtures con un catálogo sintético;
los tests con datos reales del juego se prueban sobre el endpoint HTTP.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from grimcoven_equipos.app import create_app
from grimcoven_equipos.catalogo import Catalogo, Cazador, Fuente, Griefbound
from grimcoven_equipos.equipos.recomendador import (
    PESO_AMENAZA,
    PESO_ROL,
    ROLES_ESENCIALES,
    recomendar_equipos,
)

# ---------------------------------------------------------------------------
# Fixtures: catálogo sintético para tests de lógica pura
# ---------------------------------------------------------------------------

_FUENTE = Fuente(fichero="test.pdf", pagina=1)


def _cazador(
    id_: str,
    roles: list[str],
    contrarresta: list[str] | None = None,
) -> Cazador:
    """Helper para crear cazadores de test."""
    return Cazador(
        id=id_,
        nombre=id_.title(),
        expansion="base",
        complejidad="Media",
        roles=roles,
        contrarresta=contrarresta or [],
        vida=None,
        movimiento=None,
        fuente=_FUENTE,
    )


def _griefbound(
    id_: str,
    amenazas: list[str],
    tipo: str = "griefbound",
    cazador_origen: str | None = None,
) -> Griefbound:
    """Helper para crear griefbound de test."""
    return Griefbound(
        id=id_,
        nombre=id_.title(),
        tipo=tipo,
        expansion="base",
        amenazas=amenazas,
        fuente=_FUENTE,
        cazador_origen=cazador_origen,
    )


@pytest.fixture()
def cazadores_sinteticos() -> list[Cazador]:
    """Catálogo con 6 cazadores sintéticos de roles y contrarresta variados."""
    return [
        _cazador("alfa", ["tanque", "dano"], ["fuego"]),
        _cazador("beta", ["apoyo", "dano"], ["fuego", "hielo"]),
        _cazador("gamma", ["tanque"], ["hielo"]),
        _cazador("delta", ["dano", "control"], ["veneno"]),
        _cazador("epsilon", ["apoyo"], []),
        _cazador("zeta", ["tanque", "apoyo", "dano"], ["fuego"]),
    ]


@pytest.fixture()
def griefbound_fuego() -> Griefbound:
    """Griefbound con una amenaza: fuego."""
    return _griefbound("boss-fuego", ["fuego"])


@pytest.fixture()
def griefbound_dos_amenazas() -> Griefbound:
    """Griefbound con dos amenazas: fuego e hielo."""
    return _griefbound("boss-doble", ["fuego", "hielo"])


@pytest.fixture()
def griefbound_sin_contrarresta() -> Griefbound:
    """Griefbound cuyas amenazas no son contrarrestadas por nadie."""
    return _griefbound("boss-raro", ["oscuridad"])


# ---------------------------------------------------------------------------
# Fixtures: app con catálogo real para tests de endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app_real():
    """App con el catálogo real de data/."""
    return create_app()


@pytest.fixture(scope="module")
def client(app_real) -> TestClient:
    """Cliente HTTP para la app real."""
    return TestClient(app_real)


# ===========================================================================
# CA1: Fórmula de puntuación
# puntuacion = 10 * amenazas_cubiertas + 5 * roles_esenciales_cubiertos
# ===========================================================================


class TestCA1Formula:
    """CA1: la puntuación se calcula correctamente según la fórmula."""

    def test_constantes_definidas(self) -> None:
        """CA1: las constantes PESO_AMENAZA, PESO_ROL y ROLES_ESENCIALES existen."""
        assert PESO_AMENAZA == 10
        assert PESO_ROL == 5
        assert ROLES_ESENCIALES == frozenset({"tanque", "dano", "apoyo"})

    def test_puntuacion_basica(
        self, cazadores_sinteticos: list[Cazador], griefbound_fuego: Griefbound
    ) -> None:
        """CA1: un equipo de 2 que cubre 1 amenaza y 3 roles da 10+15=25."""
        # alfa (tanque, dano, contra fuego) + beta (apoyo, dano, contra fuego,hielo)
        # amenazas cubiertas del boss-fuego: fuego (1)
        # roles esenciales: tanque, dano, apoyo (3)
        # puntuacion = 10*1 + 5*3 = 25
        resultado = recomendar_equipos(
            griefbound_fuego, cazadores_sinteticos, tamano=2, top=10
        )
        # Buscar el equipo [alfa, beta]
        equipo_ab = next(
            (e for e in resultado if e["cazadores"] == ["alfa", "beta"]), None
        )
        assert equipo_ab is not None, "El equipo [alfa, beta] debe estar en los resultados"
        assert equipo_ab["puntuacion"] == 25

    def test_puntuacion_sin_amenazas(
        self, cazadores_sinteticos: list[Cazador], griefbound_sin_contrarresta: Griefbound
    ) -> None:
        """CA1: si nadie contrarresta ninguna amenaza, puntuacion = 5 * roles."""
        resultado = recomendar_equipos(
            griefbound_sin_contrarresta, cazadores_sinteticos, tamano=2, top=10
        )
        # El equipo [alfa, beta] cubre tanque+dano+apoyo pero 0 amenazas
        equipo_ab = next(
            (e for e in resultado if e["cazadores"] == ["alfa", "beta"]), None
        )
        assert equipo_ab is not None
        assert equipo_ab["puntuacion"] == 15  # 10*0 + 5*3

    def test_puntuacion_dos_amenazas(
        self, cazadores_sinteticos: list[Cazador], griefbound_dos_amenazas: Griefbound
    ) -> None:
        """CA1: con 2 amenazas cubiertas y 3 roles => 10*2 + 5*3 = 35."""
        # alfa contrarresta fuego, beta contrarresta fuego+hielo
        # amenazas del boss-doble: fuego, hielo => ambas cubiertas
        resultado = recomendar_equipos(
            griefbound_dos_amenazas, cazadores_sinteticos, tamano=2, top=10
        )
        equipo_ab = next(
            (e for e in resultado if e["cazadores"] == ["alfa", "beta"]), None
        )
        assert equipo_ab is not None
        assert equipo_ab["puntuacion"] == 35  # 10*2 + 5*3

    def test_rol_control_no_puntua(
        self, cazadores_sinteticos: list[Cazador], griefbound_sin_contrarresta: Griefbound
    ) -> None:
        """CA1: el rol 'control' no cuenta como rol esencial."""
        # delta tiene roles [dano, control]; solo 'dano' puntua
        # delta + epsilon (apoyo) = roles esenciales: dano, apoyo => 2
        # C(6,2)=15 combinaciones; el equipo buscado queda en la parte baja,
        # asi que pedimos todas (top=15).
        resultado = recomendar_equipos(
            griefbound_sin_contrarresta, cazadores_sinteticos, tamano=2, top=15
        )
        equipo_de = next(
            (e for e in resultado if e["cazadores"] == ["delta", "epsilon"]), None
        )
        assert equipo_de is not None
        assert equipo_de["puntuacion"] == 10  # 10*0 + 5*2 (dano + apoyo)


# ===========================================================================
# CA2: Desempate lexicográfico e ids ordenados alfabéticamente
# ===========================================================================


class TestCA2Desempate:
    """CA2: equipos empatados se desempatan por orden lexicográfico de ids."""

    def test_ids_dentro_de_equipo_ordenados(
        self, cazadores_sinteticos: list[Cazador], griefbound_fuego: Griefbound
    ) -> None:
        """CA2: los ids de cada equipo se devuelven ordenados alfabéticamente."""
        resultado = recomendar_equipos(
            griefbound_fuego, cazadores_sinteticos, tamano=2, top=10
        )
        for equipo in resultado:
            ids = equipo["cazadores"]
            assert ids == sorted(ids), (
                f"Los ids {ids} deben estar ordenados alfabéticamente"
            )

    def test_desempate_lexicografico(self) -> None:
        """CA2: entre equipos con la misma puntuación, gana el lexicográficamente menor."""
        # Crear cazadores que generen empate perfecto
        c1 = _cazador("aaa", ["tanque", "dano"])
        c2 = _cazador("bbb", ["apoyo", "dano"])
        c3 = _cazador("ccc", ["tanque", "dano"])
        c4 = _cazador("ddd", ["apoyo", "dano"])
        gb = _griefbound("jefe", ["nada"])  # nadie contrarresta => solo roles

        resultado = recomendar_equipos(gb, [c1, c2, c3, c4], tamano=2, top=4)
        # [aaa, bbb] y [ccc, ddd] ambos cubren tanque+dano+apoyo => 15 puntos
        # [aaa, ddd] y [bbb, ccc] tambien cubren los 3 roles => 15 puntos
        # Deben estar ordenados: [aaa, bbb] < [aaa, ccc] < [aaa, ddd] < [bbb, ccc] ...
        puntuaciones = [e["puntuacion"] for e in resultado]
        for i in range(len(resultado) - 1):
            p_actual = puntuaciones[i]
            p_siguiente = puntuaciones[i + 1]
            if p_actual == p_siguiente:
                assert resultado[i]["cazadores"] < resultado[i + 1]["cazadores"], (
                    f"Empate: {resultado[i]['cazadores']} debe ir antes que "
                    f"{resultado[i + 1]['cazadores']}"
                )


# ===========================================================================
# CA3: Convergence con datos reales (endpoint)
# ===========================================================================


class TestCA3Convergence:
    """CA3: GET /api/equipos/recomendados?griefbound=convergence&tamano=2."""

    def test_convergence_tamano_2(self, client: TestClient) -> None:
        """CA3: convergence tamano=2 devuelve los 3 equipos esperados con puntuacion=25."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "convergence", "tamano": 2},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["griefbound"] == "convergence"
        assert body["tamano"] == 2
        assert len(body["equipos"]) == 3

        equipos_ids = [e["cazadores"] for e in body["equipos"]]
        assert equipos_ids == [
            ["clockwork-giant", "technomancer"],
            ["duality", "technomancer"],
            ["keeper", "technomancer"],
        ]

        for equipo in body["equipos"]:
            assert equipo["puntuacion"] == 25
            assert equipo["desglose"]["amenazas_cubiertas"] == ["quemadura"]
            assert sorted(equipo["desglose"]["roles_cubiertos"]) == [
                "apoyo",
                "dano",
                "tanque",
            ]


# ===========================================================================
# CA4: Devourer con datos reales (endpoint)
# ===========================================================================


class TestCA4Devourer:
    """CA4: devourer tamano=2 devuelve los 3 equipos esperados."""

    def test_devourer_tamano_2(self, client: TestClient) -> None:
        """CA4: devourer tamano=2 -> 3 equipos con puntuacion=25."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "devourer", "tamano": 2},
        )
        assert resp.status_code == 200
        body = resp.json()

        equipos_ids = [e["cazadores"] for e in body["equipos"]]
        assert equipos_ids == [
            ["death-jester", "keeper"],
            ["duality", "keeper"],
            ["keeper", "mannequin"],
        ]

        for equipo in body["equipos"]:
            assert equipo["puntuacion"] == 25
            # Hallazgo QA: verificar tambien el desglose (amenazas y roles)
            assert equipo["desglose"]["amenazas_cubiertas"] == ["hambre"]
            assert sorted(equipo["desglose"]["roles_cubiertos"]) == [
                "apoyo",
                "dano",
                "tanque",
            ]


# ===========================================================================
# CA5: Undead-general (sin contrarresta)
# ===========================================================================


class TestCA5UndeadGeneral:
    """CA5: undead-general tamano=2 devuelve equipos con amenazas_cubiertas=[]."""

    def test_undead_general_tamano_2(self, client: TestClient) -> None:
        """CA5: undead-general tamano=2 -> 3 equipos con puntuacion=15."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "undead-general", "tamano": 2},
        )
        assert resp.status_code == 200
        body = resp.json()

        equipos_ids = [e["cazadores"] for e in body["equipos"]]
        assert equipos_ids == [
            ["clockwork-giant", "death-jester"],
            ["clockwork-giant", "duality"],
            ["clockwork-giant", "mannequin"],
        ]

        for equipo in body["equipos"]:
            assert equipo["puntuacion"] == 15
            assert equipo["desglose"]["amenazas_cubiertas"] == []


# ===========================================================================
# CA6: Pretender-keeper excluye a keeper
# ===========================================================================


class TestCA6PretenderExclusion:
    """CA6: pretender-keeper tamano=3 no contiene a keeper."""

    def test_pretender_keeper_excluye_keeper(self, client: TestClient) -> None:
        """CA6: ningún equipo contra pretender-keeper incluye a keeper."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "pretender-keeper", "tamano": 3},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert len(body["equipos"]) == 3
        for equipo in body["equipos"]:
            assert "keeper" not in equipo["cazadores"], (
                f"keeper no debe estar en {equipo['cazadores']} al cazar pretender-keeper"
            )

    def test_pretender_exclusion_logica_pura(self) -> None:
        """CA6: la lógica pura también excluye al cazador_origen del pretender."""
        c_keeper = _cazador("keeper", ["tanque", "dano"], ["fuego"])
        c_alfa = _cazador("alfa", ["apoyo", "dano"])
        c_beta = _cazador("beta", ["tanque"])
        c_gamma = _cazador("gamma", ["apoyo"])
        gb = _griefbound("pretender-keeper", ["fuego"], tipo="pretender", cazador_origen="keeper")

        resultado = recomendar_equipos(gb, [c_keeper, c_alfa, c_beta, c_gamma], tamano=2, top=3)
        for equipo in resultado:
            assert "keeper" not in equipo["cazadores"]


# ===========================================================================
# CA7: Invariantes generales (3 equipos, sin repetidos, orden por puntuación)
# ===========================================================================


class TestCA7Invariantes:
    """CA7: siempre 3 equipos distintos, sin repetidos, ordenados por puntuación."""

    @pytest.mark.parametrize(
        "griefbound_id,tamano",
        [
            ("convergence", 2),
            ("convergence", 3),
            ("devourer", 2),
            ("undead-general", 2),
            ("undead-general", 4),
            ("tormentor", 3),
            ("swarm-mistress", 5),
            ("pretender-keeper", 3),
        ],
    )
    def test_invariantes_generales(
        self, client: TestClient, griefbound_id: str, tamano: int
    ) -> None:
        """CA7: para cualquier griefbound y tamano válido, se cumplen las invariantes."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": griefbound_id, "tamano": tamano},
        )
        assert resp.status_code == 200
        body = resp.json()
        equipos = body["equipos"]

        # Exactamente 3 equipos
        assert len(equipos) == 3

        # Sin cazadores repetidos dentro de un equipo
        for equipo in equipos:
            ids = equipo["cazadores"]
            assert len(set(ids)) == len(ids), f"Ids repetidos en {ids}"

        # Ordenados por puntuación de mayor a menor
        puntuaciones = [e["puntuacion"] for e in equipos]
        assert puntuaciones == sorted(puntuaciones, reverse=True)

        # Equipos distintos entre sí
        equipos_como_tuplas = [tuple(e["cazadores"]) for e in equipos]
        assert len(set(equipos_como_tuplas)) == 3, "Los 3 equipos deben ser distintos"


# ===========================================================================
# CA8: Griefbound no encontrado -> 404
# ===========================================================================


class TestCA8GriefboundNoEncontrado:
    """CA8: griefbound=foo devuelve 404."""

    def test_griefbound_inexistente(self, client: TestClient) -> None:
        """CA8: griefbound=foo&tamano=3 -> 404 con detail esperado."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "foo", "tamano": 3},
        )
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Griefbound no encontrado: foo"


# ===========================================================================
# CA9: Validación de parámetros -> 422
# ===========================================================================


class TestCA9Validacion:
    """CA9: tamano fuera de rango o parámetros ausentes -> 422."""

    @pytest.mark.parametrize(
        "params,descripcion",
        [
            pytest.param(
                {"griefbound": "convergence", "tamano": 1},
                "tamano=1 (bajo el límite)",
                id="tamano-1",
            ),
            pytest.param(
                {"griefbound": "convergence", "tamano": 6},
                "tamano=6 (sobre el límite)",
                id="tamano-6",
            ),
            pytest.param(
                {"griefbound": "convergence"},
                "sin tamano",
                id="sin-tamano",
            ),
            pytest.param(
                {"tamano": 3},
                "sin griefbound",
                id="sin-griefbound",
            ),
            pytest.param(
                {},
                "sin ningún parámetro",
                id="sin-params",
            ),
        ],
    )
    def test_parametros_invalidos(
        self, client: TestClient, params: dict, descripcion: str
    ) -> None:
        """CA9: parámetros inválidos devuelven 422."""
        resp = client.get("/api/equipos/recomendados", params=params)
        assert resp.status_code == 422, (
            f"Esperaba 422 para {descripcion}, obtuve {resp.status_code}"
        )


# ===========================================================================
# CA10: Forma de la respuesta
# ===========================================================================


class TestCA10FormaRespuesta:
    """CA10: la respuesta tiene la estructura esperada."""

    def test_estructura_respuesta(self, client: TestClient) -> None:
        """CA10: la respuesta contiene griefbound, tamano, equipos con desglose."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "convergence", "tamano": 2},
        )
        assert resp.status_code == 200
        body = resp.json()

        # Campos de nivel superior
        assert "griefbound" in body
        assert isinstance(body["griefbound"], str)
        assert "tamano" in body
        assert isinstance(body["tamano"], int)
        assert "equipos" in body
        assert isinstance(body["equipos"], list)

        # Estructura de cada equipo
        for equipo in body["equipos"]:
            assert "cazadores" in equipo
            assert isinstance(equipo["cazadores"], list)
            assert all(isinstance(id_, str) for id_ in equipo["cazadores"])

            assert "puntuacion" in equipo
            assert isinstance(equipo["puntuacion"], int)

            assert "desglose" in equipo
            desglose = equipo["desglose"]
            assert "amenazas_cubiertas" in desglose
            assert isinstance(desglose["amenazas_cubiertas"], list)
            assert "roles_cubiertos" in desglose
            assert isinstance(desglose["roles_cubiertos"], list)


# ===========================================================================
# Casos límite adicionales
# ===========================================================================


class TestValueErrorComo409:
    """Hallazgo MAJOR: recomendar_equipos envuelto en try/except ValueError -> 409."""

    def test_recomendar_pocos_cazadores_lanza_value_error(self) -> None:
        """Si tamano > cazadores disponibles, recomendar_equipos lanza ValueError."""
        c1 = _cazador("solo", ["tanque"], ["fuego"])
        gb = _griefbound("jefe", ["fuego"])
        with pytest.raises(ValueError, match="cazadores disponibles"):
            recomendar_equipos(gb, [c1], tamano=2)

    def test_pretender_pocos_cazadores_lanza_value_error(self) -> None:
        """Si un pretender excluye al cazador_origen y quedan menos de tamano."""
        c_keeper = _cazador("keeper", ["tanque", "dano"], ["fuego"])
        c_alfa = _cazador("alfa", ["apoyo"])
        gb = _griefbound(
            "pretender-keeper", ["fuego"], tipo="pretender", cazador_origen="keeper"
        )
        # Solo queda 1 cazador (alfa) pero pedimos tamano=2
        with pytest.raises(ValueError, match="cazadores disponibles"):
            recomendar_equipos(gb, [c_keeper, c_alfa], tamano=2)

    def test_endpoint_devuelve_409_si_pocos_cazadores(self) -> None:
        """CA-extra: el endpoint devuelve 409 cuando no hay suficientes cazadores."""
        c1 = _cazador("unico", ["tanque"], ["fuego"])
        gb = _griefbound("jefe-solo", ["fuego"])
        cat = Catalogo(cazadores=(c1,), griefbound=(gb,))
        mini_app = create_app(catalogo=cat)
        mini_client = TestClient(mini_app)

        resp = mini_client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "jefe-solo", "tamano": 2},
        )
        assert resp.status_code == 409
        assert "cazadores disponibles" in resp.json()["detail"]


class TestCasosLimite:
    """Casos límite no cubiertos directamente por los CAs."""

    def test_top_por_defecto_es_3(
        self, cazadores_sinteticos: list[Cazador], griefbound_fuego: Griefbound
    ) -> None:
        """El parámetro top por defecto es 3."""
        resultado = recomendar_equipos(
            griefbound_fuego, cazadores_sinteticos, tamano=2
        )
        assert len(resultado) == 3

    def test_amenazas_duplicadas_no_cuentan_doble(self) -> None:
        """Si dos cazadores contrarrestan la misma amenaza, solo cuenta una vez."""
        c1 = _cazador("x", ["tanque"], ["fuego"])
        c2 = _cazador("y", ["dano"], ["fuego"])
        gb = _griefbound("jefe-f", ["fuego"])

        resultado = recomendar_equipos(gb, [c1, c2], tamano=2, top=1)
        assert len(resultado) == 1
        # fuego cubierta 1 vez (no 2), roles: tanque+dano => 10*1 + 5*2 = 20
        assert resultado[0]["puntuacion"] == 20

    def test_desglose_amenazas_ordenadas(
        self, client: TestClient
    ) -> None:
        """Las amenazas cubiertas en el desglose deben ser una lista ordenada."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "convergence", "tamano": 2},
        )
        body = resp.json()
        for equipo in body["equipos"]:
            amenazas = equipo["desglose"]["amenazas_cubiertas"]
            assert amenazas == sorted(amenazas)

    def test_desglose_roles_ordenados(
        self, client: TestClient
    ) -> None:
        """Los roles cubiertos en el desglose deben ser una lista ordenada."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "convergence", "tamano": 2},
        )
        body = resp.json()
        for equipo in body["equipos"]:
            roles = equipo["desglose"]["roles_cubiertos"]
            assert roles == sorted(roles)

    def test_equipo_tamano_5(self, client: TestClient) -> None:
        """Caso límite: tamano=5 (máximo) funciona correctamente."""
        resp = client.get(
            "/api/equipos/recomendados",
            params={"griefbound": "convergence", "tamano": 5},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["equipos"]) == 3
        for equipo in body["equipos"]:
            assert len(equipo["cazadores"]) == 5
