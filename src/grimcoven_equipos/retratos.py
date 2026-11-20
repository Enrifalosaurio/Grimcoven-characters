"""Retratos SVG ilustrativos de los cazadores de Grimcoven.

Genera siluetas genericas basadas en el id del cazador, sin usar imagenes
oficiales del juego. Cada cazador obtiene una silueta unica y deterministica
derivada del hash de su id.
"""

from __future__ import annotations

import hashlib
import html as html_mod

from grimcoven_equipos.catalogo import Cazador


def _hash_int(texto: str) -> int:
    """Devuelve un entero determinista a partir de un texto."""
    return int(hashlib.sha256(texto.encode()).hexdigest(), 16)


def retrato_svg(cazador: Cazador) -> str:
    """Devuelve un SVG ilustrativo para el cazador dado.

    El resultado es deterministico (misma entrada, misma salida) y unico
    por ``cazador.id``. Genera una silueta abstracta sin imagenes oficiales.
    """
    h = _hash_int(cazador.id)
    nombre_seguro = html_mod.escape(cazador.nombre, quote=True)

    # Derivar parametros visuales del hash
    hue = h % 360
    cabeza_y = 30 + (h >> 8) % 10
    cabeza_r = 12 + (h >> 16) % 5
    hombro_w = 28 + (h >> 24) % 12
    torso_h = 30 + (h >> 32) % 15
    base_color = f"hsl({hue}, 25%, 45%)"
    accent_color = f"hsl({(hue + 120) % 360}, 30%, 55%)"

    # Coordenadas del torso
    cx = 60
    hombro_y = cabeza_y + cabeza_r + 4
    torso_bottom = hombro_y + torso_h

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"'
        f' role="img"'
        f' aria-label="Retrato ilustrativo: {nombre_seguro}"'
        f' width="120" height="120">'
        f'<rect width="120" height="120" fill="var(--char-2, #211E25)" rx="4"/>'
        f'<circle cx="{cx}" cy="{cabeza_y}" r="{cabeza_r}" fill="{base_color}" opacity=".7"/>'
        f'<path d="M{cx - hombro_w // 2} {hombro_y}'
        f' Q{cx} {hombro_y - 4} {cx + hombro_w // 2} {hombro_y}'
        f' L{cx + hombro_w // 2 + 4} {torso_bottom}'
        f' Q{cx} {torso_bottom + 6} {cx - hombro_w // 2 - 4} {torso_bottom}Z"'
        f' fill="{base_color}" opacity=".5"/>'
        f'<circle cx="{cx}" cy="{cabeza_y - 2}" r="2" fill="{accent_color}" opacity=".6"/>'
        f'<text x="{cx}" y="112" text-anchor="middle"'
        f' font-size="8" fill="var(--ash-text, #A89FAC)"'
        f' font-family="var(--f-head)">'
        f'Ilustrativo</text>'
        f'</svg>'
    )
    return svg
