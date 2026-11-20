"""Conftest raiz: re-exporta los fixtures e2e para que los tests marcados con
@pytest.mark.e2e ubicados fuera de tests/e2e/ puedan usar servidor_e2e,
navegador_e2e y pagina_e2e sin duplicar la logica de arranque.

Los fixtures viven en tests/e2e/conftest.py (US-013); aqui solo se importan
para ampliar su alcance al directorio tests/.
"""

from e2e.conftest import (  # noqa: F401
    _comprobar_navegador_antes_de_nada,
    navegador_e2e,
    pagina_e2e,
    servidor_e2e,
)
