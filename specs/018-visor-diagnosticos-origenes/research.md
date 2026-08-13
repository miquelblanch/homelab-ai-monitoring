# Research — Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Feature**: [spec.md](./spec.md)

## §1 — El bug real: `WHERE contenedor = ?` contra un esquema que ya no lo tiene

**Hallazgo**, comprobado antes de escribir el spec
(`BRIEFING.md`, "Feature 018 — material de partida"):
`get_diagnostico_para_alarma()` (`app.py`, feature 008, 2026-08-11)
consulta `SELECT ... FROM episodios WHERE contenedor = ?`. El feature
009, implementado el mismo día pero después, migra el esquema:

```python
# store.py::_migrar_episodios_contenedor_a_componente
conn.execute("ALTER TABLE episodios RENAME COLUMN contenedor TO componente")
conn.execute("ALTER TABLE episodios ADD COLUMN origen TEXT NOT NULL DEFAULT 'contenedor'")
```

Comprobado contra la base real:

```
$ sqlite3 diagnostico.db "SELECT id FROM episodios WHERE contenedor = 'beszel';"
Error: in prepare, no such column: contenedor
```

`_diagnostico_db_query()` atrapa la excepción y devuelve `None` — a
propósito, para que un origen roto no tumbe `/api/data` (FR-008 de
008). Consecuencia real: la pestaña "Alarmas" lleva **desde el
2026-08-11 sin mostrar ningún diagnóstico**, ni siquiera el de
contenedor, sin que ningún error visible lo delatara — indistinguible
de "todavía no hay diagnóstico". Violación activa del Principio XII
(NO NEGOCIABLE).

**Decisión**: la consulta pasa a `WHERE componente = ? AND origen =
?`, con `origen` fijo por llamada — no un parámetro adivinado, sino
explícito en cada punto de `get_active_alarms()` que invoca al
emparejador (§3).

## §2 — El frontend ya es agnóstico al origen: sin cambios de JS

**Comprobado** leyendo `app.py` (líneas ~2728-2790): `diagnosticoHtml(a)`
se invoca incondicionalmente para cada tarjeta de alarma en
`renderAlarmas()`, y su única condición es `if (!d) return ""` — no
distingue `a.origen`. El contrato ya definido por 008
(`api-diagnostico.md`, garantía 1: "`diagnostico` siempre presente,
`None` cuando no aplica") es exactamente lo que necesita este feature
para los 9 orígenes nuevos, sin tocar una sola línea de JS/CSS.

## §3 — Una función única, generalizada, sustituye a `get_diagnostico_para_alarma()`

**Hallazgo real, comprobado uno a uno leyendo `get_active_alarms()`
antes de diseñar**: los 10 orígenes de alarma no comparten ni la
identidad de emparejamiento ni la disponibilidad de un ancla temporal.

| Alarma (`add(...)`) | Origen de `diagnostico.db` | Identidad real para emparejar (`componente`) | `down_since`/ancla en la alarma |
|---|---|---|---|
| `contenedores` | `contenedor` | `c["name"]` | Sí (`down_since`) |
| `ha` | `ha` | `cid` — **no** `label` (la alarma muestra `label`, pero `diagnostico.db` guarda `cid`, feature 010) | Sí (`chk["down_since"]`) |
| `discos` | `disco` | `d["label"]` | No — la alarma no pasa `antiguedad_s` |
| `backup` | `backup` | Ninguna — `componente` es el momento ISO del propio diagnóstico (data-model.md de 011) | No — episodio más reciente de ese origen, sin filtro de nombre |
| `monitores` | `latido` | `m["job"]` — **no** `label` (feature 017) | No — `latido` no tiene modo diferido, solo "el último episodio vivo de este job" |
| `relays` | `relay` | `r["name"]` | No — **y solo empareja si ese relay se diagnosticó en vivo por nombre**: en diferido, `relay_agregado` nunca identifica cuál relay concreto (research.md de 012) |
| `hosts_externos` | `host_externo` | Nombre canónico (`HOSTS_EXTERNOS` de `evidencia.py`: "Host de Uptime Kuma" → "UptimeKuma") — **no** el nombre de pantalla | No |
| `beszel_hub` | `hub_beszel` | Ninguna — mismo caso que `backup` (data-model.md de 015) | No — episodio más reciente de ese origen |
| `agentes` (LaunchAgents) | `agente` | `a["label"]` completo — **no** `a["short"]` (lo que se ve en pantalla) | No — sin modo diferido |
| `agentes` (Crons de Hermes) | ninguno | — | **Fuera de alcance real**: `get_crons()` es un mecanismo sin origen en `diagnostico.py` |
| `inventario` | `inventario` | `b.get("componente", "")` | No |

**Decisión**: una única función,
`get_diagnostico_para_origen(origen: str, identidad: str | None,
down_since: str | None = None) -> dict | None`:

- Si `identidad` es `None` (backup, hub_beszel): `SELECT ... FROM
  episodios WHERE origen = ? ORDER BY creado_en DESC LIMIT 1` — el más
  reciente de ese origen, sin más filtro.
- Si `identidad` no es `None` y `down_since` es `None` (disco, relay,
  host externo, agente, latido, inventario): `SELECT ... FROM
  episodios WHERE componente = ? AND origen = ? ORDER BY creado_en
  DESC LIMIT 1` — el más reciente de ese componente y origen, sin
  ventana.
- Si ambos están presentes (contenedor, HA): mismo algoritmo de
  distancia-al-rango-de-ventana con tolerancia de 30 min que ya validó
  008 (`_DIAGNOSTICO_TOLERANCIA_S`), sin cambios — solo se añade el
  filtro `origen = ?` a la consulta que trae los candidatos.

Resto de la función (consulta de `diagnosticos`/`hipotesis` a partir
del episodio elegido, normalización de fechas) no cambia respecto a
008 — se reutiliza tal cual.

## §4 — Crons de Hermes y alarmas agrupadas: nunca llevan diagnóstico

**Crons de Hermes**: `get_crons()` es un mecanismo de estado
completamente distinto (jobs de Hermes, no LaunchAgents del sistema) y
ningún origen de `diagnostico.py` lo cubre — ni siquiera `agente`
(016), que solo generalizó LaunchAgents. Se documenta como fuera de
alcance explícito (FR-006/FR-012), no como un origen sin emparejar por
descuido — igual que 016 dejó fuera `get_monitor_heartbeats()`
explícitamente hasta que 017 lo cerró.

**Alarmas agrupadas** (`agrupada: True`, feature 006 FR-013): ya
llevan `"diagnostico": None` fijo en el código actual (línea ~1214) —
sin cambios, se documenta como comportamiento ya correcto que este
feature no debe romper (FR-007, generalización del FR-012 de 008).

## §5 — Sin control de versiones: copia de seguridad antes de tocar `app.py`

**Riesgo real, distinto de cualquier feature de `src/diagnostico/`**:
`homelab-dashboard/scripts/app.py` no vive bajo git — no hay `git
diff` que revisar antes de aplicar, ni `git revert` si algo sale mal.
**Decisión**: copiar `app.py` a un fichero con marca de tiempo antes
de editar (`app.py.bak-<YYYYMMDD-HHMMSS>`, en el mismo directorio, no
versionado igual que el original) — mismo criterio operativo que
"antes de un comando que pueda descartar trabajo, guarda una copia" ya
exigido por las reglas generales de la sesión, aplicado aquí a un
fichero sin red de seguridad de git. Tras el cambio: `docker compose
up -d --build` en `docker/homelab-dashboard/` y verificación de
`docker ps` + `/api/data` antes de dar el feature por terminado
(quickstart.md).
