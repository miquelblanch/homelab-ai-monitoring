# Quickstart — Validar los latidos de recordatorios y Beszel (hub)

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/ficheros.md](./contracts/ficheros.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `scripts/beszel_hosts_monitor.py` (feature 002) ya desplegado y con su
  LaunchAgent cargado — este feature lo amplía, no lo sustituye.
- Acceso a `bautista-calendar.sh` y a su LaunchAgent de las 10:00.

## 1 — Latido de recordatorios, con y sin eventos (User Story 1)

```bash
/Volumes/FastData/homelab/scripts/bautista-calendar.sh
python3 /Volumes/FastData/homelab/scripts/heartbeat.py --report | grep bautista-calendar
```

**Esperado**: aparece una fila `bautista-calendar` con latido reciente,
tanto en un día con eventos (revisar que además llegó el mensaje de
Telegram, sin relación con el latido) como en un día sin eventos (sin
mensaje de Telegram, pero el latido sí se registra) — escenarios de
aceptación 1 y 2 de `User Story 1`.

Para el escenario 3 (caducidad): no ejecutar el script un día y
comprobar, pasadas 30 h desde el último latido real, que
`heartbeat.py --report` lo marca como no-ok, y que el panel "Estado de
los monitores" del dashboard lo refleja igual.

## 2 — Frescura de Beszel (hub) coincide con la realidad (User Story 2)

```bash
docker run --rm -v beszel_hub_data:/data python:3.11-alpine \
  python3 -c "import sqlite3; print(sqlite3.connect('/data/data.db').execute('select name, updated from systems').fetchall())"
```

**Esperado**: los 3 `updated` de la consulta directa tienen menos de 15
min de antigüedad (Beszel sondea cada ~60 s) — el dashboard debe mostrar
el mecanismo de vigilancia de Beszel como sano (escenario de aceptación
1 de `User Story 2`).

## 3 — Un solo sistema viejo no es "hub roto" (Clarifications, escenario 3 de US2)

No hay forma segura de simular esto contra el Beszel real sin desconectar
un sistema de verdad. Validar por inspección de código + dato sintético:
editar temporalmente una copia de `beszel_hosts.json` con un solo
`hub_systems` envejecido (`updated` de hace más de 15 min, los otros dos
frescos) en un directorio de prueba, y comprobar que la función que
decide `sano` en `app.py` devuelve `true` — nunca ejecutar esto contra el
fichero real que lee el dashboard en producción.

## 4 — Los 3 a la vez sí es "hub roto" (escenario 2 de US2, SC-002)

Parar el LaunchAgent de `beszel_hosts_monitor.py`
(`amsterdam9.beszel.hosts-reader`) y esperar más de 15 min — mismo
procedimiento que `quickstart.md` §3 de feature 002. Con el fichero
`beszel_hosts.json` envejeciendo entero, los 3 `hub_systems` superan el
umbral a la vez.

**Esperado**: el dashboard muestra el mecanismo de vigilancia de Beszel
como no-sano. Volver a cargar el LaunchAgent para restaurar.

## 5 — El resto del dashboard sigue vivo si algo falla (SC-004)

Renombrar temporalmente `beszel_hosts.json`, recargar el dashboard, y
restaurar el nombre original.

**Esperado**: el resto de paneles se cargan con normalidad; el
mecanismo de vigilancia de Beszel se muestra como no-sano (sin dato que
leer), sin que la página falle ni quede en blanco — mismo criterio que
feature 002 ya estableció para `docker_monitor_state.json` ausente.

## 6 — Cierre de las 2 brechas restantes (SC-003)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard
```

**Esperado**: ninguna brecha de categoría `infra_monitorizacion` para
"Beszel (hub)", ni de `integracion` para "Recordatorios de Nextcloud
(Tareas/Calendario)", sigue apareciendo en el listado.
