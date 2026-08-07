# Feature Specification: Inventario Sistemático de Cobertura del Homelab

**Feature Branch**: `001-inventario-cobertura-homelab`

**Created**: 2026-08-07

**Status**: Draft

**Input**: User description: "Inventario sistemático de cobertura: recorrer todo lo que compone el homelab —contenedores, integraciones, la propia infraestructura de monitorización— y, de cada pieza, responder si tiene estado esperado declarado, si se vigila de verdad, y si un fallo llegaría al dashboard sin ausencias. Esto viene antes que escribir código de agente para casos nuevos (BRIEFING.md, sección 'En alcance ahora')."

## Clarifications

### Session 2026-08-07

- Q: Cuando el nombre real de un componente cambia entre dos ejecuciones del inventario (una entidad de HA renombrada, un contenedor renombrado), ¿debe reconocerse como el mismo componente con nombre nuevo, o tratarse siempre como "uno se fue, otro apareció"? → A: Emparejar por el identificador estable que ya expone cada fuente cuando exista; si la fuente no ofrece ninguno, tratarlo como baja+alta. *(Nota de `/speckit-plan`, 2026-08-07: el ejemplo original decía "container ID de Docker" — es impreciso, el ID interno de Docker cambia en cada recreación del contenedor. Lo estable en Docker es el nombre del contenedor/servicio; ver `research.md` §3.)*
- Q: ¿Cuánto histórico de ejecuciones anteriores del inventario necesita conservarse para poder compararlas? → A: Todas las ejecuciones, sin límite de tiempo — para poder comparar contra cualquier punto pasado, incluida la línea base del Principio IX (barrido del 2026-08-01).
- Q: ¿Cada cuánto tiempo se considera "caducada" una declaración de estado esperado si nadie la ha revisado (Principio III)? → A: Plazo fijo de calendario, 90 días desde la última revisión confirmada por Miquel — independiente de cuántas veces se ejecute el inventario.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver la cobertura real de todo el homelab (Priority: P1)

Miquel quiere una lista completa de todo lo que compone el homelab —cada
contenedor, cada integración, la propia infraestructura de monitorización— con,
para cada elemento, una respuesta explícita a tres preguntas: ¿tiene un estado
esperado declarado?, ¿se vigila de verdad?, y si fallara, ¿llegaría al
dashboard? Hoy esa lista no existe: los agujeros se han encontrado por
casualidad, cuatro veces, mirando cosas distintas cada vez.

**Why this priority**: Es el requisito que hace sistémico el resto del
proyecto. Sin este inventario, cualquier corrección posterior sigue siendo
"arreglar el caso que tocó encontrar hoy", que es exactamente el patrón que el
proyecto existe para romper (Principio XIII).

**Independent Test**: Se puede probar por completo generando el inventario una
vez y comprobando que cada uno de los contenedores y cada integración
conocida (relays, recordatorios de Nextcloud, backups, LaunchAgents) aparece
con las tres respuestas rellenas — ninguna en blanco. Entrega valor por sí
solo: es la primera vez que existe esta lista, sin necesidad de que ninguna
corrección automática esté construida todavía.

**Acceptance Scenarios**:

1. **Given** el inventario no se ha ejecutado nunca, **When** Miquel lo pide,
   **Then** recibe una lista donde cada componente del homelab tiene una
   respuesta explícita a las tres preguntas — nunca "sin revisar" o vacío.
2. **Given** un componente tiene un estado esperado declarado pero caducado
   (Principio III), **When** se inventaría, **Then** se marca como declaración
   caducada, distinto de "sin declarar" y distinto de "vigilado
   correctamente".
3. **Given** un componente está vigilado pero su fallo no llega al dashboard
   (como el caso de `bateria_cerradura` documentado en el CLAUDE.md del
   homelab), **When** se inventaría, **Then** se marca como brecha de
   cobertura, no como "vigilado" sin más.

---

### User Story 2 - Priorizar qué brecha atacar primero (Priority: P2)

De la lista completa, Miquel quiere quedarse solo con los componentes que
tienen alguna brecha (sin estado declarado, sin vigilancia, o vigilado pero
sin llegar al dashboard), con el contexto suficiente para decidir si la
corrige él mismo o si merece un spec propio.

**Why this priority**: Un inventario de 40+ componentes en verde y rojo mezclado
no es accionable. El valor está en poder mirar solo lo que falla.

**Independent Test**: Se puede probar generando el inventario completo (User
Story 1) y filtrando solo las brechas; se comprueba que cada brecha listada
tiene component, tipo de brecha y contexto suficiente para actuar sin tener que
volver a investigar desde cero.

**Acceptance Scenarios**:

1. **Given** el inventario completo ya existe, **When** Miquel pide solo las
   brechas, **Then** recibe una lista más corta que la completa, con al menos
   el nombre del componente, qué pregunta de las tres falla, y por qué importa.
2. **Given** una brecha ya conocida por barridos anteriores (`BARRIDO-xxx-xx-xx.md`),
    **When** el inventario la vuelve a encontrar,
   **Then** se identifica como ya conocida, no como un hallazgo nuevo sin
   contexto.

---

### User Story 3 - Repetir el inventario cuando el homelab cambia (Priority: P3)

Miquel añade un contenedor o una integración nueva al homelab. Quiere poder
volver a ejecutar el inventario y que el componente nuevo aparezca evaluado
contra las tres preguntas, sin tener que acordarse de añadirlo a mano a ningún
sitio.

**Why this priority**: Es la aplicación directa del Principio XIII ("todo lo
que se añada al homelab hereda esta misma obligación desde el momento en que
se añade"). Sin esto, el inventario es una foto fija que caduca en cuanto algo
cambia — y el homelab cambia constantemente.

**Independent Test**: Se puede probar añadiendo un componente nuevo (o
simulando su alta) y comprobando que la siguiente ejecución del inventario lo
incluye sin intervención manual adicional, y que además distingue qué brechas
son nuevas frente a la ejecución anterior.

**Acceptance Scenarios**:

1. **Given** un componente nuevo se ha añadido al homelab desde la última
   ejecución, **When** el inventario se repite, **Then** el componente nuevo
   aparece con las tres preguntas respondidas.
2. **Given** dos ejecuciones sucesivas del inventario, **When** Miquel las
   compara, **Then** puede distinguir qué brechas son nuevas y cuáles ya
   existían en la ejecución anterior, sin releer la lista completa cada vez.
3. **Given** nada ha cambiado formalmente en el homelab desde la última
   ejecución, **When** Miquel repite el inventario igualmente porque quiere
   volver a mirar con otro enfoque (descubrimiento deliberado, no solo
   detección de cambios), **Then** dispone de la ejecución completa, no solo
   de un diff — el diff es una ayuda, no el único resultado útil.

---

### Edge Cases

- ¿Qué pasa con un componente que **dos** vías distintas vigilan a la vez (p.
  ej. un contenedor cubierto tanto por `docker_monitor.py` como por un check
  de `ha_monitor.py`)? El inventario no debe contarlo como doble cobertura ni
  como confusión — debe quedar claro que está cubierto y por qué vía(s).
- ¿Qué pasa con un componente cuyo estado esperado se declaró pero cuyo
  nombre real cambió (el caso ya documentado de la entidad
  `bateria_cerradura`, donde el id declarado no existía)? Debe distinguirse de
  "sin vigilar": la vigilancia existe, apunta al sitio equivocado.
- ¿Qué pasa cuando el propio componente cambia de nombre entre dos
  ejecuciones del inventario (no la declaración: el componente real — una
  entidad HA cuyo `entity_id` cambia, un contenedor renombrado)? Si la
  fuente ofrece un identificador estable (el nombre de contenedor/servicio
  para Docker — su ID interno no sirve, cambia en cada recreación;
  `unique_id` para una entidad HA), el inventario lo usa para reconocer que
  es el mismo componente y no lo cuenta como baja+alta; si la fuente no
  ofrece ninguno, sí se trata como baja+alta (ver Clarifications).
- ¿Qué pasa con un componente que está intencionadamente parado o mudo (p.
  ej. `frigate`, en `NEVER_RESTART`)? No debe contar como brecha de cobertura
  — su estado esperado declarado es precisamente "no vigilar".
- ¿Qué pasa si el inventario no puede determinar si un fallo llegaría al
  dashboard porque nunca ha fallado en la ventana de datos disponible? Debe
  quedar marcado como "sin evidencia", distinto de "sí llega" y de "no llega".
- ¿Qué pasa con un componente que depende de otro para funcionar (p. ej. un
  relay `socat` del que depende una integración de Home Assistant)? El
  inventario evalúa cada uno por separado; una brecha en el relay no debe
  ocultar ni sustituir a la brecha en la integración que depende de él.
- ¿Qué pasa cuando Home Assistant expone muchas más entidades que
  integraciones (fácilmente cientos de entidades frente a un puñado de
  integraciones)? El volumen no es excusa para agrupar entidades distintas
  bajo una sola respuesta — cada entidad individual sigue necesitando sus
  tres respuestas propias.
- ¿Qué pasa si el propio canal de Telegram falla en silencio (token
  revocado, API caída, red cortada)? No es una brecha más entre otras
  cuarenta: es un riesgo concentrado que anula de golpe la entrega de casi
  todas las demás alertas del sistema. El inventario debe resaltarlo como
  tal, no enterrarlo en medio del listado de brechas ordinarias.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El inventario DEBE incluir, como elemento propio, cada uno de
  los contenedores Docker del homelab (los 40, activos o parados).
- **FR-002**: El inventario DEBE incluir, como elemento propio, cada
  integración del homelab que no sea un contenedor: relays hacia la LAN,
  recordatorios de Nextcloud, backups, LaunchAgents/crons de automatización.
- **FR-003**: Dentro de Home Assistant, el inventario DEBE bajar hasta la
  entidad individual como elemento propio, sea cual sea su dominio
  (sensor, dispositivo, automatización, script, o cualquier otro que exponga
  Home Assistant) — a diferencia del resto del homelab, donde la integración
  completa es la unidad de inventario, aquí la unidad es la entidad. Qué
  entidades existen en concreto no se enumera en este spec: lo determina la
  propia ejecución del inventario contra la instancia real de Home Assistant
  (ver Assumptions) — enumerarlas a mano repetiría el patrón anecdótico que
  el Principio XIII existe para romper.
- **FR-004**: El inventario DEBE incluir, como elemento propio, la propia
  infraestructura de monitorización (p. ej. qué vigila Beszel y sobre qué
  sistemas), no solo lo que esa infraestructura vigila.
- **FR-005**: El inventario DEBE incluir, como elementos propios, los hosts
  físicos del homelab distintos del Mac Mini — empezando por el host que
  aloja Uptime Kuma y el host que aloja AdGuard Home (DNS primario) — cada
  uno evaluado tanto como host en sí (¿se vigila que esté vivo y sano?) como
  por el servicio principal que aloja, exactamente con las mismas tres
  preguntas que el resto de componentes. Este punto cierra el Caso 3 de
  `BRIEFING.md` ("Beszel no vigila bien lo que vigila") dentro del propio
  inventario, en vez de dejarlo como investigación aparte.
- **FR-006**: El inventario DEBE incluir, como elementos propios y
  separados, el agente conversacional del homelab (Hermes/Bautista — un
  proceso nativo, no un contenedor Docker) y el canal de entrega de
  Telegram en sí. Telegram es el mecanismo por el que sale casi toda alerta
  del sistema (backups, monitor de Docker, monitor de HA, informe diario...),
  así que un fallo silencioso del propio canal invalidaría de golpe la
  respuesta "llega al dashboard/Telegram" de todos los demás componentes,
  aunque cada uno esté bien vigilado por separado — ver Edge Cases.
- **FR-007**: Para cada elemento, el inventario DEBE registrar si tiene un
  estado esperado declarado explícitamente (Principio III), y si esa
  declaración está vigente o caducada. Una declaración caduca a los 90 días
  desde su última revisión confirmada por Miquel, sea cual sea el número de
  ejecuciones del inventario transcurridas en ese tiempo (ver
  Clarifications).
- **FR-008**: Para cada elemento, el inventario DEBE registrar si está
  vigilado de verdad — no si "debería estarlo" — y por qué mecanismo concreto.
- **FR-009**: Para cada elemento, el inventario DEBE registrar si un fallo
  real de ese elemento llegaría al dashboard (`http://homelab.amsterdam9.home/`)
  sin ausencias, distinguiendo el caso "no llega" del caso "no hay evidencia
  suficiente para saberlo".
- **FR-010**: El inventario NO DEBE dejar ningún elemento sin las tres
  respuestas de FR-007 a FR-009 — "sin revisar" no es una respuesta válida en
  un inventario completo.
- **FR-011**: El inventario DEBE producir, además de la lista completa, un
  listado filtrado de solo los elementos con alguna brecha (declaración
  ausente o caducada, sin vigilancia real, o vigilado sin llegar al
  dashboard), con contexto suficiente para que Miquel decida sin
  reinvestigar desde cero.
- **FR-012**: El inventario DEBE marcar como intencionados (no como brecha)
  los elementos cuyo estado esperado declarado sea explícitamente "no
  vigilar" (p. ej. `frigate`, la entidad muda de la cerradura ya documentada
  en `NEVER_RESTART` y casos equivalentes) — ver
  [[homelab-estado-intencionado]].
- **FR-013**: El inventario DEBE poder repetirse contra un homelab que ha
  cambiado desde la última ejecución (componentes añadidos, eliminados o
  renombrados) sin requerir que alguien mantenga a mano la lista de
  componentes a revisar, y DEBE seguir siendo útil cuando se repite sin que
  nada haya cambiado formalmente — Miquel también lo relanza como
  herramienta de descubrimiento deliberado, no solo para detectar altas y
  bajas.
- **FR-014**: El inventario DEBE poder lanzarse a demanda, en el momento que
  Miquel decida, y no solo según una programación fija — ver Assumptions
  sobre el mecanismo concreto de disparo.
- **FR-015**: Cuando el inventario se repite, DEBE distinguir qué brechas son
  nuevas frente a la ejecución anterior y cuáles ya eran conocidas,
  reconociendo un componente como el mismo entre ejecuciones por su
  identificador estable cuando la fuente lo ofrece, aunque haya cambiado de
  nombre — y no solo por coincidencia de nombre.
- **FR-016**: El inventario NO DEBE modificar, reiniciar ni actuar sobre
  ningún componente del homelab — es una actividad de observación, no de
  corrección (esa corrección es un feature aparte, fuera de este spec).
- **FR-017**: El resultado del inventario DEBE quedar registrado de forma que
  se pueda comparar contra la línea base del Principio IX (barrido del
  2026-08-01: 11 problemas reales, 0 visibles en el dashboard, 2 falsos
  positivos de 12 comprobaciones). El inventario DEBE conservar **todas**
  las ejecuciones pasadas, sin límite de tiempo — no solo la más reciente —
  para poder comparar contra cualquier punto anterior, no solo contra el
  inmediatamente previo.
- **FR-018**: El inventario DEBE entregar sus resultados a través de canales
  que ya existen (el dashboard del homelab y/o Telegram) — no construye
  ninguna interfaz ni portal nuevo. Un portal específico de monitorización de
  Home Assistant queda fuera de este spec (ver Assumptions).

### Key Entities

- **Componente del homelab**: unidad mínima de inventario. Puede ser un
  contenedor Docker, una integración (relay, recordatorio, backup,
  LaunchAgent/cron), una entidad individual de Home Assistant de cualquier
  dominio (sensor, dispositivo, automatización, script, etc.), un host
  físico del homelab distinto del Mac Mini (p. ej. el que aloja Uptime Kuma
  o el que aloja AdGuard Home), el agente Hermes/Bautista, el propio canal
  de entrega de Telegram, o una pieza de la propia infraestructura de
  monitorización. Atributos: nombre, identificador estable cuando la fuente
  lo ofrece (nombre de contenedor/servicio para Docker, `unique_id` de HA —
  usado para reconocer el mismo componente entre ejecuciones aunque cambie
  de nombre; ver Clarifications), categoría, estado esperado declarado (sí/no + vigente o
  caducado a los 90 días sin revisión confirmada — ver Clarifications),
  mecanismo de vigilancia real (si existe), si un fallo llegaría al
  dashboard (sí / no / sin evidencia).
- **Hallazgo**: la respuesta a las tres preguntas para un componente
  concreto, en una ejecución concreta — es lo que compone el listado
  completo de `User Story 1`. Un mismo componente tiene un hallazgo
  distinto por cada ejecución del inventario, para poder comparar en el
  tiempo (`FR-015`).
- **Brecha de cobertura**: hallazgo derivado de un componente cuya respuesta a
  alguna de las tres preguntas no es plenamente satisfactoria. Atributos:
  componente afectado, qué pregunta falla, contexto explicativo, si ya era
  conocida por un barrido anterior o es nueva.
- **Ejecución del inventario**: instantánea con fecha de una pasada completa
  sobre todos los componentes. Atributos: fecha, lista de componentes
  revisados, lista de brechas, diferencia frente a la ejecución anterior. Se
  conservan todas las ejecuciones, sin límite de tiempo — nunca se purgan ni
  se sustituyen por la más reciente (ver Clarifications).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El inventario cubre el 100% de los componentes conocidos del
  homelab (los 40 contenedores, las integraciones y la infraestructura de
  monitorización listadas en el `CLAUDE.md` del homelab, cada entidad
  individual expuesta por Home Assistant, los hosts físicos distintos del
  Mac Mini —Uptime Kuma y AdGuard Home—, y el agente Hermes/Bautista junto
  con el canal de Telegram) — ninguno queda sin las tres respuestas.
- **SC-002**: El número de brechas de cobertura que encuentra el inventario es
  igual o superior a las 11 ya conocidas por el barrido de referencia del
  2026-08-01, confirmando que el método iguala o mejora la detección manual
  que le sirve de línea base (Principio IX).
- **SC-003**: Miquel puede, a partir del listado filtrado de brechas (User
  Story 2), decidir la siguiente acción para cada una (corregirla, escribir
  un spec, o descartarla como intencionada) sin tener que volver a consultar
  ninguna otra fuente que no sea el propio inventario.
- **SC-004**: Al repetir el inventario tras un cambio real en el homelab
  (alta, baja o cambio de un componente), el componente afectado queda
  reflejado en la siguiente ejecución sin ninguna intervención manual previa
  a esa ejecución.

## Assumptions

- El inventario se apoya en las fuentes que ya existen — `docker ps`,
  `homelab.db`, configuración de `ha_monitor.py`, `socat_relays.json`,
  `launchctl list`, `CLAUDE.md` del homelab — y no requiere instrumentar de
  cero ningún componente para poder responder las tres preguntas; cuando una
  fuente no basta para responder, el elemento se marca "sin evidencia" (ver
  Edge Cases) en vez de bloquear el resto del inventario.
- Determinar "si un fallo llegaría al dashboard" se hace por inspección
  razonada de cómo está conectada la vigilancia de ese componente (mismo
  método que se usó en `BARRIDO-2026-08-01.md`), no exigiendo provocar un
  fallo real ni encontrar un incidente histórico para cada uno de los 40+
  componentes — eso sería desproporcionado para el primer inventario.
- La granularidad de "componente" baja hasta la entidad individual dentro de
  Home Assistant (cada sensor, cada dispositivo expuesto) — decisión explícita
  de Miquel (2026-08-07), distinta del resto del homelab, donde la unidad
  sigue siendo el contenedor o la integración completa (p. ej. "relay
  Zigbee"). Esto amplía lo que decía `BRIEFING.md` sobre HA ("fuera de
  alcance por ahora: diagnosticar Home Assistant y los relays"): aquí no se
  diagnostica ninguna entidad, solo se comprueba su cobertura — es un check
  más barato que un diagnóstico, y por eso puede entrar en el inventario sin
  contradecir ese límite.
- Un **portal específico de monitorización de Home Assistant**, que Miquel
  quiere a futuro, queda **fuera de este spec**. Construirlo contradiría la
  decisión ya escrita en `BRIEFING.md` ("el dashboard ya existe, no se
  construye uno nuevo") y es un entregable distinto de hacer un inventario.
  Este feature entrega sus resultados por los canales que ya existen
  (FR-018); el portal queda anotado aquí como candidato a un feature futuro,
  sin decidir todavía su alcance ni si requeriría antes revisar esa decisión
  de `BRIEFING.md`.
- Este inventario es una actividad recurrente y repetible (Principio XIII),
  no un documento de una sola vez como los `BARRIDO-*.md` anteriores — su
  resultado debe poder compararse entre ejecuciones (FR-015). Repetirlo no es
  solo para detectar altas y bajas: Miquel también lo relanza
  deliberadamente como herramienta de descubrimiento (FR-013), aunque nada
  haya cambiado formalmente.
- El inventario DEBE poder lanzarse a demanda (FR-014); el mecanismo
  concreto de disparo (una tarea programada, un comando manual, o más
  adelante un botón en el dashboard que ya existe) se decide en el plan, no
  aquí. Un disparador en el dashboard actual no contradiría la decisión de
  "no construir un portal nuevo" —sería un control más sobre lo que ya
  existe, no una interfaz nueva—, pero es una decisión que Miquel deja
  explícitamente para más adelante.
- Hermes/Bautista y el canal de Telegram (FR-006) son dos componentes
  separados a propósito, con radio de impacto distinto: si falla solo
  Hermes, se pierden los comandos interactivos y los crons que dependen de
  él (`dreaming`, `noticias-ia`, `gbrain-weekly-purge`,
  `homelab-optimizer-weekly`), pero el resto de la monitorización sigue
  avisando por Telegram sin pasar por Hermes; si falla el canal de Telegram
  en sí, se pierde casi toda la entrega del sistema de golpe. Tratarlos como
  un único componente ocultaría esa diferencia.
- Este spec no enumera qué dispositivos, automatizaciones ni entidades
  concretas existen dentro de Home Assistant (p. ej. la antena Zigbee, sus
  automatizaciones asociadas). Hacerlo sería fijar de antemano una lista
  elegida a mano — justo el patrón anecdótico que el Principio XIII busca
  evitar. FR-003 ya obliga a cubrir cualquier entidad, de cualquier dominio;
  el inventario de qué existe en concreto es resultado de *ejecutar* el
  inventario contra la instancia real, no un dato de entrada del spec. Si la
  primera ejecución revela que hace falta una regla adicional (p. ej. cómo
  tratar la salud de un coordinador Zigbee que no se expone como entidad),
  eso se resuelve entonces, con evidencia real delante en vez de anticiparlo.
- Los hosts físicos distintos del Mac Mini (FR-005) se identifican en este
  spec por el software que alojan (Uptime Kuma, AdGuard Home), no por su
  dirección IP — coherente con la política de saneado del repo (`CLAUDE.md`
  del proyecto: "nada de... IPs"). La IP real, si hace falta para implementar,
  vive fuera de este repositorio.
- No se propone ni ejecuta ninguna corrección de las brechas encontradas
  como parte de este feature: eso pertenece a "corregir, de forma reversible,
  lo que ya esté diagnosticado" (`BRIEFING.md`, "En alcance ahora"), que es
  un feature distinto y posterior.
- Al planificar la entrega al dashboard (`FR-018`) se descubrió, leyendo el
  código real de `docker/homelab-dashboard/scripts/app.py`, que las
  alarmas que ya calculan `docker_monitor.py` y `ha_monitor.py`
  (`docker_monitor_state.json`, `ha_monitor_state.json` — un `ok`/
  `down_since` por contenedor o check) **no llegan hoy al dashboard**: la
  app solo lee `socat_relays.json` y `launchagents_raw.txt` de esa carpeta.
  Es exactamente el problema del Principio XII (NO NEGOCIABLE). Se decidió
  con Miquel (2026-08-07) que **no** entra en este spec: es mecánicamente
  independiente de las tres preguntas del inventario (no necesita
  identidad estable, ni caducidad, ni SQLite — solo leer dos ficheros que
  ya existen y sumarlos al panel), y `BRIEFING.md` ya trata "cobertura y
  precisión del dashboard" como un punto de "En alcance ahora" distinto del
  inventario. Queda anotado aquí como el candidato natural a **feature
  002**, siguiente en la cola tras este.
