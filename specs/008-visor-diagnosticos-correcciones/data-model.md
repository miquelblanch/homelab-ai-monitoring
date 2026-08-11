# Data Model — Visor de Diagnósticos en Alarmas

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Sin base de datos ni fichero nuevo. Todo se calcula en memoria en cada
petición a `/api/data`, leyendo `diagnostico.db` de solo lectura
(research.md §1) y el `down_since` que `get_active_alarms()` ya lee de
`docker_monitor_state.json` — nada se persiste desde este feature.

## Alarma de contenedor caído, ampliada

Producida por `get_active_alarms()` (feature 006), con un campo nuevo
opcional.

| Campo | Tipo | Obligatorio | Significado |
|---|---|---|---|
| `origen`, `tipo`, `nivel`, `componente`, `mensaje`, `explicacion`, `remediacion`, `antiguedad_s`, `agrupada`, `cantidad` | — | Ya existentes (feature 006) | Sin cambios |
| `diagnostico` | object \| `null` | No | **Nuevo**. `null` cuando `origen != "contenedores"`, cuando la alarma está agrupada (`agrupada=true` — feature 006 FR-013, sin `componente` individual que emparejar), o cuando ningún episodio de `diagnostico.db` corresponde a la caída actual (research.md §3) |

## `diagnostico` (cuando no es `null`)

| Campo | Tipo | Significado |
|---|---|---|
| `episodio_fecha` | string (ISO 8601, UTC) | `creado_en` del episodio emparejado — ya UTC explícito en origen (corregido 2026-08-11, research.md §4), servido tal cual — la fecha que FR-004/SC-005 exigen mostrar siempre |
| `diagnostico_fecha` | string (ISO 8601, UTC) | `creado_en` del intento de diagnóstico mostrado (el más reciente de ese episodio, FR-005) |
| `conclusion_tipo` | string | `causa_probable` o `no_diagnosticable`, tal cual `diagnosticos.conclusion_tipo` (007) |
| `conclusion_texto` | string | Tal cual `diagnosticos.conclusion_texto` (007) |
| `hipotesis` | array de objetos | Cada una con `descripcion`, `comprobacion`, `desenlace` — tal cual `hipotesis` (007), sin transformar (spec.md FR-003, SC-002) |

## Gasto diario de diagnóstico

Campo nuevo de nivel superior en `/api/data`, junto a `alarms`.

| Campo | Tipo | Significado |
|---|---|---|
| `gasto_diagnostico` | object | `{"coste_eur_acumulado": number, "limite_eur": number}` — tal cual la fila de `gasto_diario` (007) para el día natural en curso; `{"coste_eur_acumulado": 0.0, "limite_eur": <default>}` si no hay fila para hoy (spec.md User Story 3, escenario 2) |

## Relación con `diagnostico.db` (lectura, no FK real)

Ningún campo nuevo aquí referencia un `id` de `diagnostico.db`
directamente — el emparejamiento (research.md §2-§3) se recalcula en
cada petición a partir de `componente` + `down_since`, no se persiste
ninguna relación. Si `diagnostico.db` cambia entre dos peticiones (por
ejemplo, Miquel diagnostica el episodio en vivo por CLI mientras el
dashboard está abierto), la siguiente petición a `/api/data` ya refleja
el cambio sin ninguna acción adicional — mismo comportamiento "siempre
en vivo" que el resto de `app.py`.

## Nota: alarmas agrupadas (feature 006, FR-013)

Cuando `ALARM_GROUP_THRESHOLD` agrupa muchas alarmas del mismo
`(origen, tipo)` en una sola entrada con `agrupada=true`, esa entrada
no tiene un `componente` individual con el que emparejar un episodio
(su `componente` es una descripción del grupo, p. ej. "12 contenedores
caídos"). `diagnostico` es `null` en ese caso — mostrar el diagnóstico
de un solo contenedor del grupo sería engañoso sobre cuál. Caso límite,
no cubierto por ningún Acceptance Scenario del spec porque hoy no hay
volumen de contenedores caídos simultáneos que dispare el umbral de
agrupación.
