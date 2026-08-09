# Research — Latido Propio: Recordatorios de Nextcloud y Beszel (Hub)

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-08-09

Cada decisión se contrastó contra el código real del homelab —
`bautista-calendar.sh`, `skill.py` (homelab-calendar), `heartbeat.py`,
`scripts/beszel_hosts_monitor.py` (feature 002) y
`docker/homelab-dashboard/scripts/app.py` — y, para el punto 3, contra el
propio hub de Beszel en marcha, no contra supuestos.

## 1. Dónde y cómo registrar el latido de recordatorios (FR-001, FR-002)

**Decision**: una llamada a `heartbeat.write("bautista-calendar", ...)` al
final de `bautista-calendar.sh`, justo después de calcular `OUTPUT` (la
salida de `recordatorios_hoy()`) y antes de la comprobación
`[ -z "$OUTPUT" ] && exit 0`. El `detail` que se registra es una de tres
etiquetas fijas y cortas decididas por el propio script —
`"recordatorios enviados"`, `"sin eventos hoy"` o `"error real
detectado"` — nunca el contenido de `$OUTPUT` en sí.

**Rationale**: `heartbeat.write()` vive en `heartbeat.py` (Python), y
`bautista-calendar.sh` ya tiene el patrón para invocar Python inline
(la lectura de credenciales de Telegram al principio del script, vía
`$PY -c "..."`) — se reutiliza el mismo patrón, sin introducir un
lenguaje nuevo. Colocar la llamada después de `OUTPUT` y antes del
`exit 0` de silencio es lo que hace que **el silencio intencionado
también cuente como ejecución correcta** (Acceptance Scenario 2 de User
Story 1): si se pusiera antes del cálculo de `OUTPUT`, un fallo dentro
de `recordatorios_hoy()` que lanzara una excepción no capturada
invalidaría el latido también en el caso de éxito silencioso real.

**Por qué el detail son etiquetas fijas, no el texto real**: `$OUTPUT`
puede contener texto libre de los propios eventos de calendario (títulos
que Miquel o Cécile escriben en Nextcloud). Interpolar ese texto sin
escapar dentro de un `python3 -c "..."` invocado desde bash es una
inyección de comandos clásica — un título de evento con comillas,
backticks o `$(...)` se ejecutaría como código Python/shell. Las tres
etiquetas fijas eliminan el vector por completo: nunca se interpola
contenido externo en el comando, solo un literal elegido por el propio
script bash mediante un `case`/`if` sobre si `OUTPUT` está vacío o
empieza por `❌`.

**Alternatives considered**: mover el latido dentro de
`recordatorios_hoy()` (Python, en `skill.py`) — descartado porque esa
función no sabe si el mensaje llegó a mandarse por Telegram, y porque
`bautista-calendar.sh` es quien de verdad completa el ciclo del cron;
mantener el latido en el script bash es más fiel a "¿terminó el cron?".

## 2. Umbral de caducidad del latido de recordatorios (Assumptions)

**Decision**: 108000 s (30 horas) — el mismo valor exacto que ya usa
`verify-backups` en `MONITOR_JOBS` (`app.py`) para otro cron de una vez
al día.

**Rationale**: mismo patrón de cron (una vez al día, sin reintento
automático si falla) y mismo margen ya validado en producción — diario +
un día de margen, sin inventar un número nuevo para un caso ya resuelto.

## 3. Qué comprobar para saber si Beszel (hub) sigue reportando (FR-003, FR-004)

Investigado contra el hub real, no contra documentación:

- La tabla `systems` de Beszel tiene una columna `updated`
  (`PRAGMA table_info(systems)` confirmado en vivo el 2026-08-09), con
  formato `"YYYY-MM-DD HH:MM:SS.mmmZ"` (UTC, con milisegundos) — es el
  momento en que Beszel completó su último sondeo de ese sistema, **no**
  el momento en que `beszel_hosts_monitor.py` leyó la fila.
- Consultada la tabla `system_stats` (histórico de métricas), Beszel
  sondea cada uno de los 3 sistemas (`Mac Mini Server`, `UptimeKuma`,
  `AdGuardHome`) con un ciclo de aproximadamente 60 segundos — filas
  consecutivas del mismo `system` distan ~60 s entre sí.
- `scripts/beszel_hosts_monitor.py` (feature 002) ya consulta la tabla
  `systems` completa cada 5 min vía `docker run` contra el volumen
  `beszel_hub_data` — el mismo mecanismo, ampliando la consulta de
  `select name, status` a `select name, status, updated`, sirve para
  este feature sin añadir una segunda vía de acceso a Beszel.

**Decision**: ampliar `scripts/beszel_hosts_monitor.py` para que, en el
mismo ciclo que ya hace, también capture `updated` de **todas** las
filas de `systems` (no solo los 2 hosts canónicos de feature 002) y las
persista en `beszel_hosts.json` bajo una clave nueva, `hub_systems`. La
decisión de "¿lleva más de 15 min sin refrescar?" se calcula **en el
momento de leer**, en `app.py` — comparando `updated` contra el reloj
actual — no en el momento de escribir. Es el mismo patrón que ya usa
`app.py` para decidir si `beszel_hosts.json` en conjunto está "sin
evidencia" (edad de `generated_at` calculada al leer, no al escribir):
un dato puede volverse viejo sin que nadie vuelva a escribir el fichero,
así que la comprobación de vejez no puede vivir en el escritor.

**Por qué reutilizar `beszel_hosts_monitor.py` en vez de un script
nuevo**: es literalmente el mismo `docker run` contra la misma tabla —
crear un segundo lector duplicaría la consulta a Beszel cada 5 min sin
ganar nada (Principio X, mínima superficie nueva).

**Alternatives considered**: comprobar solo la antigüedad de
`generated_at` del propio `beszel_hosts.json` (lo que feature 002 ya
hace) — descartado explícitamente: ese campo solo dice "¿pudo mi lector
conectarse a la base de datos de Beszel?", no "¿sigue Beszel sondeando
sus sistemas de verdad?". Los dos fallan de forma distinta: el volumen
puede seguir siendo legible mientras el proceso interno de Beszel que
sondea está colgado — exactamente el Caso 3 original de `BRIEFING.md`.

## 4. Cómo se refleja en el dashboard sin ser un segundo `MONITOR_JOBS` (FR-005)

**Decision**: una fila añadida a mano a la tabla "Estado de los
monitores", igual que ya hacen "heartbeat.py" y "Backup diario" en
`app.py` (`monitorsRows += monitorRow(...)`) — no una entrada más en
`MONITOR_JOBS`.

**Rationale**: `MONITOR_JOBS` decide sano/no-sano únicamente por edad de
un latido (¿corrió el script hace poco?) — esa pregunta para
`beszel_hosts_monitor.py` como proceso **ya la responde** el latido
`beszel-hosts` que escribió feature 002 (FR-008 de este feature se apoya
en ese latido ya existente, no crea uno nuevo — ver Edge Cases de
`spec.md`). Lo que falta aquí es una pregunta distinta y basada en
contenido: de los 3 sistemas que Beszel vigila, ¿cuántos tienen
`updated` fresco? Esa lógica no encaja en el modelo genérico de
`MONITOR_JOBS`, igual que "Backup diario" tampoco usa ese modelo (calcula
la edad de un fichero de latido externo con su propia regla) — mismo
precedente, misma solución.

**Alternatives considered**: sobrecargar el `status` del latido
`beszel-hosts` existente para reflejar también la frescura de Beszel —
descartado porque mezclaría dos preguntas independientes ("¿vive mi
lector?" y "¿vive Beszel?") en una sola señal, perdiendo la distinción
que exige FR-004/Edge Cases.

## 5. Umbral de frescura por sistema para el hub (Clarifications)

**Decision**: 900 s (15 min) — mismo valor que `BESZEL_HOSTS_MAX_AGE_S`,
ya definido en `app.py` por feature 002 para el latido `beszel-hosts`.
Se reutiliza la misma constante para juzgar la antigüedad de cada
`updated` de `hub_systems`, en vez de definir un segundo número para el
mismo tipo de dato.

**Rationale**: decidido explícitamente en `/speckit-clarify` (2026-08-09)
por consistencia entre las dos comprobaciones relacionadas con Beszel
dentro del mismo fichero, y de sobra frente al ciclo de sondeo real de
Beszel (~60 s, punto 3).
