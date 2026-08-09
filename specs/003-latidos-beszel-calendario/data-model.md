# Data Model — Latido Propio: Recordatorios de Nextcloud y Beszel (Hub)

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Este feature no introduce ninguna base de datos nueva. Amplía un fichero
que feature 002 ya escribe (`beszel_hosts.json`) y reutiliza el mecanismo
de latido que ya usa el resto del homelab (`heartbeat.py`).

## Latido de recordatorios de Nextcloud

**Origen**: `heartbeat.write("bautista-calendar", ...)`, llamado desde
`bautista-calendar.sh` al final de cada ejecución del cron de las 10:00
(`research.md` §1). Mismo fichero de latido que ya define `heartbeat.py`
para el resto del homelab — sin esquema propio.

| Campo | Tipo | Significado |
|---|---|---|
| `job` | string | `"bautista-calendar"` |
| `epoch` | int | Cuándo terminó la ejecución más reciente del cron |
| `status` | string | `"ok"` — el cron completó su ciclo (con o sin eventos) |
| `detail` | string | Una de tres etiquetas fijas: `"recordatorios enviados"`, `"sin eventos hoy"`, `"error real detectado"` — nunca el contenido real de los eventos (`research.md` §1, riesgo de inyección) |

**Caducidad**: 108000 s / 30 horas (`research.md` §2), igual criterio que
`verify-backups`.

## `beszel_hosts.json` — ampliado

**Origen**: el mismo `scripts/beszel_hosts_monitor.py` de feature 002,
ampliado (`research.md` §3). El esquema que feature 002 ya define no
cambia — se añade una clave nueva junto a `hosts`.

```json
{
  "generated_at": "2026-08-09T10:05:00+02:00",
  "hosts": {
    "Host de Uptime Kuma": { "status": "up", "beszel_name": "UptimeKuma" },
    "Host de AdGuard Home (DNS primario)": { "status": "up", "beszel_name": "AdGuardHome" }
  },
  "hub_systems": {
    "Mac Mini Server": "2026-08-09 08:04:38.238Z",
    "UptimeKuma": "2026-08-09 08:04:40.305Z",
    "AdGuardHome": "2026-08-09 08:04:43.994Z"
  }
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `hub_systems` | objeto | Una entrada por cada sistema que Beszel tiene registrado en su tabla `systems` (hoy 3: Mac Mini, Uptime Kuma, AdGuard Home) — no limitado a los 2 hosts canónicos de `hosts` |
| `hub_systems.<nombre>` | string | El valor de `updated` tal cual lo reporta Beszel (UTC, con milisegundos) — el momento en que Beszel completó su último sondeo real de ese sistema, no cuándo se leyó aquí |

**Por qué `hub_systems` no lleva su propia marca de frescura**: igual que
`generated_at` del fichero completo, la vejez de cada `updated` se decide
en el momento de leer (`app.py`), comparando contra el reloj actual — no
se calcula ni se congela al escribir (`research.md` §3). Guardar aquí un
booleano "fresco: sí/no" sería una fecha de caducidad falsa en cuanto
pasara el tiempo sin que el fichero se reescribiera.

**Mismo "todo o nada" que `hosts`**: si la consulta a Beszel falla o
faltan los 2 hosts canónicos, `beszel_hosts_monitor.py` no reescribe el
fichero en absoluto (garantía ya establecida por feature 002,
`contracts/ficheros.md`) — `hub_systems` hereda esa misma garantía por
construcción, al formar parte del mismo payload atómico.

## Estado de vigilancia de Beszel (hub) — calculado, no persistido

**Origen**: una función nueva en `app.py` que lee `hub_systems` de
`beszel_hosts.json` y decide, sistema por sistema, si `updated` tiene
más de `BESZEL_HOSTS_MAX_AGE_S` (900 s / 15 min, `research.md` §5) de
antigüedad frente al momento de la lectura.

| Campo | Tipo | Significado |
|---|---|---|
| `sano` | booleano | `false` únicamente si **todos** los sistemas de `hub_systems` superan el umbral a la vez (FR-004); `true` en cualquier otro caso, incluido que solo uno o dos estén viejos |
| `systems` | lista | Por sistema: nombre, antigüedad de `updated`, si supera el umbral — para depuración, no para una alarma individual nueva (esa ya existe en el panel de hosts externos de feature 002 para los 2 hosts que le conciernen) |

No se persiste en ningún fichero propio — se recalcula en cada carga del
dashboard a partir de `beszel_hosts.json`, igual que el resto de estados
derivados de `app.py` (`get_external_hosts()`, `get_ha_monitor()`).
