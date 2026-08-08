# Quickstart — Validar las alarmas en el dashboard

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/ficheros.md](./contracts/ficheros.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `docker_monitor.py` ya corriendo cada 5 min (sin cambios de este
  feature).
- El script nuevo (`research.md` §5) desplegado y con su LaunchAgent
  cargado.
- Acceso local a `docker run` contra el volumen `beszel_hub_data`
  (mismo entorno donde ya corre `docker_monitor.py`).

## 1 — Alarma de contenedor fundida en la fila (User Story 1)

Parar un contenedor no crítico un momento (o simular su caída) y esperar
a que `docker_monitor.py` complete un ciclo (hasta 5 min):

```bash
docker stop <contenedor-no-critico>
# esperar al siguiente ciclo de docker_monitor.py
```

**Esperado**: al abrir el dashboard, la tarjeta de ese contenedor muestra
"Caído desde `<hora>`" en la misma fila donde ya se veía su estado en
vivo — no aparece una segunda alarma en ningún otro sitio del panel
(escenario de aceptación 1 de `User Story 1`, Clarification 1).

Arrancarlo de nuevo y esperar otro ciclo: la marca de "caído desde" sigue
visible aunque el contenedor ya esté corriendo (escenario de aceptación
2) — confirma que no depende solo del estado en vivo de `docker ps`.

## 2 — Estado de Kuma/AdGuard en el dashboard (User Story 2)

```bash
docker run --rm -v beszel_hub_data:/data python:3.11-alpine \
  python3 -c "import sqlite3; print(sqlite3.connect('/data/data.db').execute('select name, status from systems').fetchall())"
```

**Esperado**: la salida de este comando (consulta directa, para
comparar) coincide con lo que muestra el dashboard para "Host de Uptime
Kuma" y "Host de AdGuard Home (DNS primario)" tras el siguiente ciclo del
script nuevo (escenarios de aceptación 1-2 de `User Story 2`).

## 3 — "Sin evidencia" ante un fallo del propio mecanismo (FR-004, SC-004/SC-005)

Parar el LaunchAgent del script nuevo y esperar más de 15 minutos:

```bash
launchctl bootout gui/$(id -u)/amsterdam9.beszel.hosts-reader
```

**Esperado**:

- El estado de Kuma/AdGuard en el dashboard pasa a "sin evidencia" — no
  se queda congelado en el último "arriba" como si siguiera siendo
  verdad (escenario de aceptación 3 de `User Story 2`).
- El panel "Estado de los monitores" muestra la fila `beszel-hosts` en
  rojo, sin latido reciente — Miquel se entera por ahí, no porque note
  días después que el dato no se ha movido (`SC-005`).

Volver a cargar el LaunchAgent para restaurar el mecanismo:

```bash
launchctl bootstrap gui/$(id -u) <ruta-del-plist>
```

## 4 — El resto del dashboard sigue vivo si algo falla (`SC-004`)

Renombrar temporalmente `docker_monitor_state.json` para simular que no
existe, recargar el dashboard, y restaurar el nombre original.

**Esperado**: el resto de paneles (sistema, discos, crons, LaunchAgents,
inventario de cobertura) se cargan con normalidad; solo el dato de
"caído desde" de los contenedores deja de aparecer, sin que la página
falle ni quede en blanco.

## 5 — Cierre de las brechas de feature 001 (`SC-003`)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
python3 -m inventory.cli --gaps --no-telegram --no-dashboard
```

**Esperado**: ninguna brecha de categoría `contenedor`, y ninguna de
`host_externo` para "Host de Uptime Kuma" / "Host de AdGuard Home (DNS
primario)", aparece ya en el listado — el propio inventario de feature
001 sirve de verificación automática de este feature, sin duplicar
lógica de comprobación.
