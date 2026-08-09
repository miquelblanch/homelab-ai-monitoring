# Research — Central de Alarmas del Homelab

**Feature**: [spec.md](./spec.md)

No hay ningún `[NEEDS CLARIFICATION]` pendiente del Technical Context —
las tres decisiones que sí hacían falta (agrupación en cascada, orden
por gravedad, antigüedad opcional) ya se resolvieron en
`/speckit-clarify` y están en `spec.md` (FR-013, FR-004, FR-014). Este
documento resuelve las decisiones puramente técnicas que el spec no
fija a propósito (no lleva tecnología).

## §1 — Dónde vive la lógica de agregación: `app.py`, no el navegador

**Decisión**: una función nueva `get_active_alarms()` en
`homelab-dashboard/scripts/app.py`, en el mismo módulo y con el mismo
patrón que `get_external_hosts()`, `get_beszel_hub_status()` y
`get_ha_monitor()` — Python puro, se recalcula en cada petición a
`/api/data`, nada se persiste en disco.

**Rationale**: las otras funciones "derivadas" del dashboard (decidir
`sano`/`no-sano`, "caído"/"ok") ya viven en Python, no en el JavaScript
del navegador — el buscador de la pestaña Inventario (feature previa,
ad-hoc) es la única lógica de filtrado que vive en JS, y es filtrado
puro sobre datos ya clasificados, no una clasificación nueva. Este
feature sí clasifica (niveles de gravedad, agrupación) — encaja con el
patrón Python existente, no con el del buscador.

**Alternativas consideradas**: calcular la lista en el navegador a
partir de las claves que `/api/data` ya expone (`containers`, `ha`,
`socat_relays`...). Rechazada: duplicaría en JavaScript la lógica de
"qué cuenta como caído" que cada función Python ya calcula
(`get_containers()` ya distingue intencionado de no, `get_ha_monitor()`
ya trae `ok`/`motivo`...) — mantenerla en Python es releer esas mismas
decisiones, no reinterpretarlas.

## §2 — Catálogo de tipos de alarma: diccionario estático, mismo patrón que `MONITOR_INFO`

**Decisión**: un diccionario Python `ALARM_TYPES` a nivel de módulo,
clave = id de tipo (string), valor = `{"nivel": ..., "explicacion":
..., "remediacion": ...}`. `get_active_alarms()` solo instancia
alarmas con un id de tipo que exista en este diccionario; el texto en
sí se escribe a mano una vez por tipo (FR-005/FR-006/FR-015). Ver
`data-model.md` para el catálogo completo con los 19 tipos y su
nivel.

**Rationale**: mismo patrón exacto que `MONITOR_INFO`/`AGENT_DESC`, ya
en producción en este mismo fichero — cero dependencias nuevas, cero
tokens (FR-015), y trivial de ampliar cuando aparezca un tipo nuevo
(añadir una entrada al diccionario, no tocar la lógica de agregación).

**Alternativas consideradas**: fichero JSON externo editable sin
reconstruir la imagen (mismo mecanismo que
`/data/cron_name_overrides.json`, ya usado por `get_crons()`).
Rechazada por ahora: el texto de cada tipo es contenido de producto
(cambia con la misma frecuencia que el propio código de clasificación),
no un ajuste de despliegue — separarlo en un fichero aparte añadiría
una fuente de verdad más sin necesidad real. Queda anotado como opción
si en el futuro se editara con frecuencia sin querer reconstruir.

## §3 — Cómo se detecta y agrupa una cascada (FR-013)

**Decisión**: agrupar por la pareja `(origen, tipo)` — no por un
"motivo raíz" inferido con más inteligencia. Si más de `ALARM_GROUP_THRESHOLD`
(constante, valor 5) alarmas activas comparten el mismo `(origen,
tipo)` en la misma pasada de `get_active_alarms()`, se colapsan en una
sola entrada con `agrupada: true` y `cantidad: N`, usando el nivel y la
explicación/remediación del tipo tal cual (no hace falta un texto
"resumen" aparte).

**Rationale**: como FR-006 ya fija el texto por *tipo* general (no por
submotivo), un tipo ya es la unidad correcta de agrupación — no hace
falta inventar un concepto nuevo de "motivo raíz" distinto del tipo
(de hecho, `spec.md` FR-013 ya lo llama "motivo raíz" y equipara
explícitamente ese término a `tipo`, para que no queden como dos
conceptos distintos). Cubre los dos ejemplos del spec sin lógica
especial: la API de HA caída hace fallar ~100 checks, todos con tipo
`ha_entidad_no_disponible` o `ha_api_caida`; el daemon Docker/OrbStack
colgado hace que los ~40 contenedores aparezcan con tipo
`contenedor_caido`/`contenedor_caido_critico` (no `docker_monitor.py`:
`get_containers()` consulta `docker ps` en vivo, así que el disparador
real de esa cascada es el propio daemon, no el cron de 5 min que
reinicia contenedores).

**Antigüedad de una entrada agrupada**: el `antiguedad_s` más alto
entre las alarmas que agrupa (la más antigua del grupo) — implementado
así en `get_active_alarms()` y documentado en `data-model.md`. Elegido
sobre la más reciente o un promedio porque responde a la pregunta que
de verdad importa ("¿desde cuándo lleva este problema activo?"), no a
cuándo se sumó la última instancia a la cascada.

**Alternativas consideradas**: agrupar por similitud de `mensaje` (texto
libre). Rechazada: los mensajes en bruto de cada origen no son
uniformes entre sí (`state=unavailable` vs `Exited (1)` vs `disco al
92%`), comparar texto libre es fragil y no aporta nada que `(origen,
tipo)` no dé ya de forma determinista.

## §7 — Criterio de éxito para `cron_con_error`

**Decisión**: un cron habilitado (`enabled: true`) cuenta como alarma
cuando su `status` no es `"ok"`, `"success"` ni `"—"` (el valor de
"todavía sin ejecutar"). Un cron deshabilitado no genera alarma —
deshabilitarlo es una decisión intencionada, no un fallo (mismo
espíritu que `INTENTIONALLY_STOPPED_CONTAINERS` para contenedores).

**Rationale**: `get_crons()` ya expone `status` tal cual lo reporta
Hermes, sin un enumerado cerrado y documentado de valores posibles. En
vez de inventar uno nuevo para este feature, se reutiliza el mismo
criterio que el propio resumen del dashboard ya aplicaba antes de este
feature (`status==='ok'||status==='success'` cuenta como éxito) — ni
un enumerado más estricto, ni una alarma nueva.

## §4 — Niveles de gravedad y su color: reutilizar `--crit`/`--warn`/`--ok`

**Decisión**: los 3 niveles de FR-004 (Crítico/Aviso/Informativo) se
pintan con los tokens de color que el dashboard ya define en `:root`
(`--crit`, `--warn`, y una variante neutra para "Informativo" — se
reutiliza `--text-dim`/`--line-soft`, sin token de color nuevo). La
asignación completa tipo → nivel vive en `ALARM_TYPES` (§2), no en el
CSS.

**Rationale**: `barColor()`/`dotClass()` (uso de disco) y
`levelColor()`/`levelClass()` (niveles que se consumen, como la sal)
ya usan exactamente este vocabulario de 2-3 colores en toda la app —
añadir un cuarto color solo para esta pestaña rompería la consistencia
visual sin necesidad.

## §5 — Antigüedad opcional (FR-014): se lee del origen, nunca se calcula

**Decisión**: `get_active_alarms()` copia el campo de antigüedad que
cada función de origen ya expone cuando existe
(`down_since`/`age_s`/timestamp del heartbeat), y lo omite (`None`) en
los orígenes que no lo tienen (discos). Ninguna alarma calcula ni
persiste un "primera vez visto" propio.

**Rationale**: es la lectura literal de FR-014/FR-002 — cualquier
cálculo de "desde cuándo" que no exista ya en el origen sería una
condición de alarma nueva, prohibida por FR-002.

## §6 — Sin test automático para `app.py`; validación por `quickstart.md`

**Decisión**: mismo criterio que feature 002/003 — `app.py` no tiene
suite de test en este repo privado. Este feature se valida con los
pasos de `quickstart.md`, no con un fichero de test nuevo.

**Rationale**: es la convención ya establecida (`plan.md` de feature
003, sección Testing) — introducir aquí un test unitario aislado sería
inconsistente con el resto del fichero que se está modificando.
