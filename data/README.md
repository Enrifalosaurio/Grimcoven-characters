# Datos del catálogo de Grimcoven

Este directorio contiene el catálogo que usa la aplicación para generar equipos:

- `cazadores.json`: los 8 cazadores (6 del juego base y 2 de la expansión Hunters).
- `griefbound.json`: los 8 Griefbound (6 base y 2 de Forgotten Entities) y los 8 Pretenders
  (uno por cazador).

Ambos ficheros son una lista de objetos en la raíz y se cargan y validan con
`grimcoven_equipos.catalogo.cargar_cazadores()` y `cargar_griefbound()`.

## Campos

### Cazador

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto | Identificador único (`kebab-case`). |
| `nombre` | texto | Nombre en el reglamento. |
| `expansion` | `base` \| `hunters` | |
| `complejidad` | texto | Valoración del reglamento (`Baja`, `Baja-Media`, `Media`, `Media-Alta`, `Alta`). |
| `roles` | lista no vacía de `tanque`, `dano`, `apoyo`, `control` | **Inferencia** a partir de la descripción del cazador. |
| `contrarresta` | lista de amenazas (puede estar vacía) | **Inferencia**. |
| `vida` | entero o `null` | `null` cuando el dato falta en las fuentes. |
| `movimiento` | entero o `null` | `null` cuando el dato falta en las fuentes. |
| `fuente` | `{fichero, pagina}` | Fichero de `Resources/` y página impresa (coincide con la del PDF). |

### Griefbound

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto | Identificador único. Los pretenders usan `pretender-<id del cazador>`. |
| `nombre` | texto | |
| `tipo` | `griefbound` \| `pretender` | |
| `expansion` | `base` \| `hunters` \| `forgotten-entities` | |
| `amenazas` | lista de texto | **Inferencia** a partir de la tabla de Rapid Hunt. |
| `cazador_origen` | texto | Solo en pretenders: id de un cazador existente. |
| `fuente` | `{fichero, pagina}` | Igual que en los cazadores. |

## Fuentes

- R = `GC_Rulebook_280x280mm_bleed3mm [36 pages]_[lowres]_compressed.pdf`
- H = `EN_Hunters Expansion.pdf`
- F = `EN_Forgotten Entities.pdf`

Cazadores: Duality y Gunslinger en R p27, Keeper y Technomancer en R p28, Mannequin y Death
Jester en R p29, Clockwork Giant en H p2 y Twins en H p3. La vida y el movimiento de Gunslinger
(13 / 2) salen de su loseta en R p10 y los de Technomancer (12 / 2) de su loseta en R p26.

Griefbound: los 6 base en R p30 (tabla de Rapid Hunt; también R p35), Chimera y Striga en F p1
(Rapid Hunt en F p2). Pretenders: Duality, Gunslinger y Keeper en R p31; Technomancer, Mannequin
y Death Jester en R p32; Clockwork Giant y Twins en H p4.

## Inferencias (a validar por el usuario)

Los siguientes campos **no aparecen literalmente en los reglamentos**; son inferencias:

- **`roles`**: deducidos de la descripción de cada cazador (p. ej. Duality es "agile short
  range damage-dealer, tank or healer" → `dano`, `tanque`, `apoyo`).
- **`amenazas`**: deducidas del efecto de cada Griefbound en la tabla de Rapid Hunt:
  Convergence "gains 3 Burns" → `quemadura`; Graveyard Dragon "2 Curses" → `maldicion`;
  Devourer "2 Hunger" → `hambre`; Tormentor "takes wounds" → `heridas`; Swarm Mistress
  "Swarm tiles" → `enjambre`; Undead General "Banner cards" → `estandartes`; Chimera "Place
  defense on each Head token" → `defensa`; Striga "Obsession track" (F p1) → `obsesion`.
- **`contrarresta`**: deducido de las habilidades descritas (p. ej. Technomancer puede
  "discard or exchange Status tokens" → `quemadura`, `maldicion`; Keeper tiene "multitarget
  attacks, big self-heal Actions or reversing the effects of Hunger" → `hambre`, `enjambre`,
  `heridas`).

Las debilidades reales de cada Griefbound están en los **Hunt Books**, que no están en
`Resources/`; por eso `amenazas` y `contrarresta` deben considerarse provisionales.

## Datos que faltan en las fuentes

- **Hunt Books**: no están en `Resources/`; faltan las debilidades reales de cada Griefbound.
- **Vida y movimiento**: falta el dato de 6 cazadores (Duality, Keeper, Mannequin, Death
  Jester, Clockwork Giant y Twins); en los PDF solo aparecen las losetas de Technomancer y
  Gunslinger. Por eso esos campos valen `null`.
- **Contrarresta sin cubrir**: ningún cazador contrarresta `estandartes`, `defensa` ni
  `obsesion`.
- **Pretenders**: no tienen amenazas (`amenazas: []`).
- **Striga**: el icono de su Rapid Hunt en F p2 no se lee.

Para completar estos datos, guarda la información (por ejemplo, de internet) en `Resources/`
y actualiza los JSON citando la nueva fuente.
