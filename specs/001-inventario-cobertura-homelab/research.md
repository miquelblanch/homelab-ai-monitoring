# Research — Inventario Sistemático de Cobertura del Homelab

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-08-07

Cada decisión de esta fase se contrastó contra el código ya existente en
`/Volumes/FastData/homelab/scripts/` (fuera de este repo, en la máquina del
homelab) para no reinventar convenciones que ya funcionan. Ninguna decisión
introduce tecnología no mencionada en `BRIEFING.md` ni en la constitución.

## 1. Lenguaje y política de dependencias

**Decision**: Python 3.11, solo librería estándar (`sqlite3`, `subprocess`,
`urllib`, `json`, `pathlib`) salvo que un integración concreta lo impida (ver
punto 4).

**Rationale**: Es la convención sin excepciones del resto del homelab —
`docker_monitor.py`, `ha_monitor.py` y `metrics_db.py` declaran explícitamente
"sin dependencias externas" en su cabecera, y la Regla 10 de `CLAUDE.md` del
homelab general exige Python 3.11 para cualquier cosa que corra vía
LaunchAgent (`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`
— los shims de pyenv no funcionan desde `launchd`). Seguir la misma
convención hace que este feature encaje sin fricción si algún día se dispara
desde un LaunchAgent (FR-014).

**Alternatives considered**: Un framework de scripting más rico (`click`,
`typer` para la CLI) — rechazado: añadiría una dependencia externa que ningún
otro monitor del homelab necesita, a cambio de un beneficio marginal para una
CLI de un puñado de subcomandos.

## 2. Almacenamiento de las ejecuciones del inventario

**Decision**: SQLite, en una base de datos propia dentro de
`docker/homelab-orchestrator/data/` (mismo directorio que ya usa
`homelab.db`), con tablas nuevas — no se reutilizan las tablas de
`container_metrics` porque su semántica es distinta (una métrica a 5 min, no
una ejecución de inventario).

**Rationale**: Es el mismo patrón que `metrics_db.py` ya usa para persistir
lo que antes solo se mandaba a Telegram, y ese directorio ya está dentro de
`/Volumes/FastData/homelab/`, cubierto por el backup nocturno completo
(Política de Backup del homelab general) — relevante porque la Clarification
del 2026-08-07 exige conservar **todas** las ejecuciones sin límite de
tiempo (FR-017): que el backup ya las proteja es una propiedad gratis de
reusar la misma ubicación, no algo que haya que construir aparte.

**Alternatives considered**: Ficheros JSON por ejecución (como
`socat_relays.json`) — rechazado para el histórico de ejecuciones porque
comparar y diferenciar (`FR-015`) entre decenas de ejecuciones es más simple
con una consulta SQL que abriendo N ficheros; sí se usa un JSON puntual para
alimentar el dashboard (ver punto 6).

## 3. Identidad estable de un componente entre ejecuciones (Clarification 1)

La Clarification del 2026-08-07 exige emparejar componentes por un
identificador estable "cuando la fuente lo ofrece". El identificador
concreto **no es el mismo para cada fuente** — esto se investigó fuente por
fuente:

- **Contenedores Docker**: el **nombre** del contenedor (o la etiqueta
  `com.docker.compose.service` cuando se gestiona vía compose) es lo
  estable — se mantiene entre recreaciones. El **ID interno de Docker no
  sirve**: cambia en cada recreación del contenedor (actualización de
  imagen, `docker-compose up -d --force-recreate`), aunque el nombre se
  mantenga. *(Nota: el spec, al recoger la respuesta de la Clarification,
  usó "container ID" como ejemplo — es la corrección técnica que se hace en
  este research y que conviene reflejar en el propio spec, ver informe de
  cierre de este plan.)*
- **Entidades de Home Assistant**: el `unique_id` del registro de entidades
  sí es estable frente a un renombrado de `entity_id` — es su propósito de
  diseño. No está expuesto por la API REST clásica (`/api/states` solo da
  `entity_id` + estado + atributos). Vive en
  `.storage/core.entity_registry` dentro del volumen de configuración de
  HA — un fichero JSON interno, no documentado como API estable entre
  versiones de HA.
- **El resto de fuentes** (relays, recordatorios, backups, LaunchAgents,
  hosts externos, Hermes, Telegram, infraestructura de monitorización) no
  ofrecen ningún identificador nativo — se identifican por el nombre
  declarado en el propio inventario, y un cambio de nombre se trata como
  baja+alta, tal como ya prevé el spec como comportamiento por defecto.

**Decision**: usar nombre de contenedor/servicio compose para Docker,
`unique_id` (leído directamente del fichero de registro de HA) para
entidades de Home Assistant, y nombre declarado para todo lo demás.

**Rationale**: ambas rutas evitan añadir una dependencia nueva —
`docker inspect` ya expone las etiquetas de compose, y leer un fichero JSON
del volumen de HA es coherente con el Principio X (Local por Defecto) y con
la decisión ya tomada en `BRIEFING.md` de "consultar SQLite directamente"
como criterio general de "acceso directo antes que integración nueva".

**Alternatives considered**: API WebSocket de HA (`config/entity_registry/
list`) para obtener `unique_id` de forma oficial y estable entre versiones —
más robusta a largo plazo, pero exige implementar el *handshake* de
autenticación por WebSocket (no soportado por `urllib` de la stdlib sin
trabajo adicional) o añadir una dependencia externa (`websocket-client`).
Se aparca para una iteración futura si la lectura directa del fichero
resulta frágil en la práctica; mientras tanto, el propio spec ya cubre el
caso de que la fuente no ofrezca identificador ("sin evidencia de
continuidad" → baja+alta), así que no bloquea este feature.

## 4. Retención del histórico (Clarification 2)

**Decision**: las tablas de ejecuciones e identidades de componente son
**append-only**: ninguna rutina de purga las toca, a diferencia de
`container_metrics` (retención 30 días) o `container_metrics_hourly`.

**Rationale**: es la traducción directa de la Clarification 2 ("todas las
ejecuciones, sin límite de tiempo"). La regla de `homelab.db`
("nunca ejecutar `prune(require_rollup=False)` sin saber lo que se hace")
ya establece el precedente de que la retención es explícita por tabla, no
un valor global — coherente con añadir una tabla con política propia.

**Alternatives considered**: Reutilizar la retención de 30 días de
`container_metrics` — descartada explícitamente por la Clarification 2.

## 5. Caducidad de una declaración de estado esperado (Clarification 3)

**Decision**: campo `last_reviewed_at` por componente; una declaración es
`caducada` si `hoy - last_reviewed_at > 90 días`. La revisión se confirma
explícitamente (no se renueva sola por ejecutarse el inventario).

**Rationale**: traducción directa de la Clarification 3. No depende de
cuántas veces se ejecute el inventario (que ahora es a demanda, `FR-014`),
solo del calendario.

## 6. Entrega del resultado (FR-018)

**Decision**: dos vías — una reutilizada tal cual, la otra reutilizada pero
con una pieza de código nueva y pequeña:

1. **Telegram**, con el mismo `homelab_secrets.telegram()` que ya usan
   `docker_monitor.py` y `ha_monitor.py` — el listado filtrado de brechas
   (`FR-011`), destacando el riesgo concentrado de la propia entrega
   (`FR-006`, ver punto 7) si aplica. Reutilización directa, sin cambios en
   nada existente.
2. **Dashboard** (`docker/homelab-dashboard/scripts/app.py`, un único
   FastAPI de 787 líneas): **corregido tras inspeccionar el código real**
   (no es la suposición original de este research). El dashboard **no**
   lee genéricamente cualquier JSON de
   `docker/homelab-orchestrator/data/` — tiene lectores cableados a mano
   para exactamente dos ficheros de esa carpeta (`socat_relays.json`,
   `launchagents_raw.txt`) más un `cron_name_overrides.json`, y sus
   secciones (`system`, `disks`, `containers`, `crons`, `launchagents`,
   `socat_relays`) están fijadas en `collect()`. **No lee
   `docker_monitor_state.json` ni `ha_monitor_state.json`, pese a que
   existen en esa misma carpeta** — dato relevante para todo el proyecto,
   no solo para este feature: explica en parte por qué el barrido del
   2026-08-01 encontró 11 problemas reales con 0 visibles en el dashboard.
   Para que el inventario aparezca ahí hace falta:
   - Escribir un `inventario.json` en `docker/homelab-orchestrator/data/`
     (mismo patrón de fichero que `socat_relays.json`), **y**
   - Añadir una función `get_inventory()` a `app.py` que lo lea, sumarla a
     `collect()`, y añadir una sección nueva al HTML/JS del propio
     `app.py` (el frontend vive embebido en el mismo fichero, no hay
     plantillas separadas).

**Rationale**: seguir siendo "el dashboard que ya existe, no uno nuevo"
(`FR-018`, `BRIEFING.md`) no depende de que el cambio cueste cero — depende
de que sea una sección más del mismo panel único, no una superficie nueva.
Añadir una función y una sección a un fichero que ya tiene seis secciones
del mismo tipo es exactamente eso: extender, no construir. Se documenta el
tamaño real del cambio (`contracts/entrega.md`) para que `tasks.md` lo
recoja como una tarea propia, no como "gratis" por escribir un JSON.

**Alternatives considered**: dejar el inventario solo en Telegram para v1 y
aplazar la integración con el dashboard a un feature posterior — no se
adopta como decisión porque `FR-018` y `SC-001`/`SC-003` del spec ya piden
el dashboard como canal, pero queda anotado como opción de reducción de
alcance si `tasks.md` necesita recortar.

**Fuera de alcance de este research, decidido con Miquel (2026-08-07)**:
`docker_monitor_state.json` y `ha_monitor_state.json` contienen las
alarmas reales de `docker_monitor.py`/`ha_monitor.py` (`ok`/`down_since`
por contenedor o check) y tampoco las lee `app.py` — problema directo del
Principio XII. Se decidió **no** resolverlo como parte de este feature: es
mecánicamente independiente de las tres preguntas del inventario. Queda
como candidato a feature 002 (ver Assumptions del spec).

## 7. Mitigar el riesgo concentrado de Telegram (Edge Case, FR-006)

**Decision**: tras cada ejecución exitosa, registrar un latido con
`heartbeat.py` (`heartbeat.write("inventario-cobertura", ...)`), igual que
ya hacen los demás LaunchAgents del homelab.

**Rationale**: el propio spec señala que un fallo silencioso de Telegram
invalidaría la entrega de casi todo (Edge Case de `FR-006`). Un latido
separado, ya vigilado por `amsterdam9.health` y empujado a Uptime Kuma
(ver `heartbeat.py`), da una **segunda vía** de detección que no depende de
que Telegram esté funcionando — si el inventario corre pero no logra
avisar, el latido lo delata igualmente. No es una tarea nueva: es aplicar
un patrón que ya existe a un caso que el propio spec pidió vigilar.

## 8. Determinar "si un fallo llegaría al dashboard" (FR-009)

**Decision**: inspección razonada basada en reglas declaradas por tipo de
fuente (p. ej. "todo lo que pasa por `docker_monitor.py` llega"; "una
entidad de HA solo llega si algún check de `ha_monitor.py` la referencia
explícitamente"), no ejecución de una falla real ni búsqueda de un
incidente histórico por componente.

**Rationale**: ya lo fijó la Clarification/Assumption del spec ("mismo
método que se usó en `BARRIDO-2026-08-01.md`") — no es una decisión nueva
de este plan, se documenta aquí solo para que quede trazada la fuente antes
del modelo de datos.

## 9. Disparo a demanda (FR-014)

**Decision**: script CLI (`python3 -m inventory.cli`) invocable a mano en
cualquier momento; el mismo binario puede colgarse de un LaunchAgent para
una cadencia regular más adelante, sin cambiar el contrato de entrada. El
botón en el dashboard existente (mencionado en el spec como idea a futuro)
queda fuera de este plan.

**Rationale**: Cumple `FR-014` con el mínimo mecanismo posible; no
compromete ninguna opción futura (LaunchAgent programado, botón del
dashboard) porque ambas solo necesitarían invocar el mismo comando.
