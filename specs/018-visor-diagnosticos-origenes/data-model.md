# Data Model — Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de
`specs/008-visor-diagnosticos-correcciones/data-model.md` — no lo
sustituye. Solo se documentan aquí los campos y funciones que cambian.

## Campo `diagnostico` en `alarms.items[]`

**Sin cambio de forma** respecto a 008 — mismo objeto
`{episodio_fecha, diagnostico_fecha, conclusion_tipo, conclusion_texto,
hipotesis}` o `null`. Lo que cambia es **para qué orígenes puede dejar
de ser `null`**: antes, solo `origen == "contenedores"`; con este
feature, cualquiera de los 10 salvo la rama de Crons de Hermes dentro
de `agentes` (research.md §4) y cualquier alarma agrupada (sin
cambios, ya era `null`).

## Función `get_diagnostico_para_origen()` (reemplaza a `get_diagnostico_para_alarma()`)

| Parámetro | Tipo | Notas |
|---|---|---|
| `origen` | `str` | Uno de `"contenedor"`, `"ha"`, `"disco"`, `"backup"`, `"relay"`, `"host_externo"`, `"hub_beszel"`, `"agente"`, `"latido"`, `"inventario"` — el valor real de `episodios.origen`, no la clave de alarma del dashboard (que en varios casos difiere: `"contenedores"`→`"contenedor"`, `"discos"`→`"disco"`, `"hosts_externos"`→`"host_externo"`, `"beszel_hub"`→`"hub_beszel"`, `"monitores"`→`"latido"`). |
| `identidad` | `str \| None` | El valor real de `episodios.componente` para ese origen (research.md §3) — `None` para `backup`/`hub_beszel`, que no tienen identidad estable. |
| `down_since` | `str \| None` | Ancla ISO de la alarma, si existe — solo `contenedor` y `ha` la pasan hoy. |

**Retorno**: mismo objeto que 008 (`episodio_fecha`,
`diagnostico_fecha`, `conclusion_tipo`, `conclusion_texto`,
`hipotesis`) o `None`.

**Comportamiento por combinación de parámetros** (research.md §3):

| `identidad` | `down_since` | Consulta |
|---|---|---|
| `None` | — (ignorado) | `WHERE origen = ?`, el más reciente |
| no `None` | `None` | `WHERE componente = ? AND origen = ?`, el más reciente |
| no `None` | no `None` | Igual que 008: distancia al rango `[ventana_inicio, ventana_fin]` con tolerancia `_DIAGNOSTICO_TOLERANCIA_S` (30 min), filtrado también por `origen = ?` |

## Puntos de llamada en `get_active_alarms()` (identidad real pasada, no siempre la etiqueta de pantalla)

| Rama | `origen` pasado | `identidad` pasada | `down_since` pasado |
|---|---|---|---|
| `contenedores` | `"contenedor"` | `c["name"]` | `c.get("down_since")` |
| `ha` | `"ha"` | `cid` | `chk.get("down_since")` |
| `discos` | `"disco"` | `d["label"]` | ninguno |
| `backup` | `"backup"` | `None` | ninguno |
| `monitores` | `"latido"` | `m["job"]` | ninguno |
| `relays` | `"relay"` | `r["name"]` | ninguno |
| `hosts_externos` | `"host_externo"` | `HOSTS_EXTERNOS_CANONICO[h["name"]]` | ninguno |
| `beszel_hub` | `"hub_beszel"` | `None` | ninguno |
| `agentes` (LaunchAgents) | `"agente"` | `a["label"]` (completo, no `a["short"]`) | ninguno |
| `agentes` (Crons) | — | — | Sin llamada — `diagnostico` fijo a `None` (research.md §4) |
| `inventario` | `"inventario"` | `b.get("componente", "")` | ninguno |

## Constante nueva (`app.py`)

| Constante | Valor | Uso |
|---|---|---|
| `HOSTS_EXTERNOS_CANONICO` | `{"Host de Uptime Kuma": "UptimeKuma", "Host de AdGuard Home (DNS primario)": "AdGuardHome"}` — copia literal de `evidencia.py::HOSTS_EXTERNOS` (014) | Traduce el nombre de pantalla de `EXTERNAL_HOSTS` al nombre canónico que usa `diagnostico.db` para `origen="host_externo"`. |

## Esquema SQLite

**Sin cambios** — `diagnostico.db` no se toca desde este productor
(solo lectura, FR-011).
