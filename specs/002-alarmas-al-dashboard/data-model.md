# Data Model — Alarmas Ya Calculadas al Panel del Dashboard

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Este feature no introduce ninguna base de datos nueva. Los dos "modelos"
son los ficheros JSON que ya existen o que este feature añade en
`docker/homelab-orchestrator/data/` — el mismo directorio que ya monta el
dashboard en `/data`.

## Alarma de contenedor

**Origen**: `docker_monitor_state.json`, ya escrito por `docker_monitor.py`
cada 5 minutos. Este feature **no** modifica ese fichero — solo lo lee.

```json
{
  "container:<nombre-del-contenedor>": {
    "ok": true,
    "down_since": null
  }
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `ok` | booleano | `false` si `docker_monitor.py` lo detectó caído/`unhealthy` en su ciclo más reciente |
| `down_since` | string ISO 8601 o `null` | Desde cuándo, si `ok` es `false`; `null` si está sano |

**Identidad**: el nombre tras `container:` es el mismo nombre de
contenedor que expone `docker ps` — no hace falta ningún emparejamiento
adicional (mismo espacio de nombres, ver `research.md` §1).

**Ausencia esperada**: un contenedor en `NEVER_RESTART` (`frigate`) no
tiene clave en este fichero — `docker_monitor.py` hace `continue` antes de
escribirla. Ausencia de clave ≠ alarma; se trata igual que "sano" a
efectos de este feature (no es una brecha de este feature: `frigate` ya
está marcado como intencionadamente no vigilado desde antes, `FR-012` de
feature 001).

## Estado de host externo

**Origen**: nuevo — lo escribe el script de este feature (ver "Project
Structure" en `plan.md`), leyendo la tabla `systems` del hub de Beszel vía
el volumen `beszel_hub_data` (`research.md` §3).

**Fichero nuevo**: `beszel_hosts.json`

```json
{
  "generated_at": "2026-08-08T19:05:00+02:00",
  "hosts": {
    "Host de Uptime Kuma": { "status": "up", "beszel_name": "UptimeKuma" },
    "Host de AdGuard Home (DNS primario)": { "status": "up", "beszel_name": "AdGuardHome" }
  }
}
```

| Campo | Tipo | Significado |
|---|---|---|
| `generated_at` | string ISO 8601 | Cuándo terminó el ciclo que produjo este fichero |
| `hosts` | objeto | Una entrada fija por cada uno de los 2 hosts en alcance (`FR-002`) |
| `hosts.<nombre>.status` | string | Valor tal cual lo reporta la columna `status` de la tabla `systems` de Beszel (`up`, u otro valor si Beszel lo cambia — no se traduce ni se filtra) |
| `hosts.<nombre>.beszel_name` | string | El nombre interno que usa Beszel para ese sistema (`research.md` §3) — se conserva para poder depurar sin volver a consultar la base de Beszel a mano |

**Nombres canónicos**: `"Host de Uptime Kuma"` y `"Host de AdGuard Home
(DNS primario)"` — exactamente los mismos literales que ya usa
`src/inventory/sources.py` (feature 001) para la categoría `host_externo`,
para que ambos features hablen del mismo componente con el mismo nombre.

**"Sin evidencia" no vive en este fichero**: si el script no puede leer
Beszel, no escribe un `beszel_hosts.json` a medias — o completa el ciclo
con los 2 hosts, o no reescribe el fichero y deja que `generated_at` (o el
`mtime` del propio fichero) envejezca más allá de los 15 minutos
(`FR-004`), que es lo que el dashboard interpreta como "sin evidencia".
Mismo principio "a prueba de fallos" que el resto de monitores del
homelab: un ciclo fallido no debe dejar un dato falso, debe dejar un dato
viejo y detectable como tal.

## Latido del mecanismo nuevo

**Origen**: `heartbeat.write("beszel-hosts", ...)`, mismo mecanismo que ya
usan `docker_monitor.py`, `ha_monitor.py`, `verify_backups.py`,
`dns_pi_monitor.py` y `telegram_monitor.py` (`FR-008`). No se documenta
esquema aparte: es el mismo fichero de latido que ya define `heartbeat.py`
para el resto del homelab.
