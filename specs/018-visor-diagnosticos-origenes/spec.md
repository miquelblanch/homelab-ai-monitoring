# Feature Specification: Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Feature Branch**: `018-visor-diagnosticos-origenes`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "El visor de diagnósticos en el dashboard (feature 008) solo muestra el diagnóstico de contenedores caídos, y además está roto: sigue consultando una columna (contenedor) que el feature 009 renombró a componente+origen el mismo día, así que lleva desde el 2026-08-11 sin mostrar ningún diagnóstico en producción, ni siquiera el de contenedor — se traga el error en silencio. Quiero arreglar ese emparejamiento primero, y luego generalizarlo a los 9 orígenes restantes del motor de diagnóstico (disco, HA, backup, relay, inventario, host externo, hub de Beszel, agente, latido) para que cualquier alarma activa con un diagnóstico ya hecho lo muestre, igual que ya hace contenedor. Para los orígenes con modo diferido y un ancla temporal real en la alarma (contenedor, HA), el emparejamiento respeta la misma ventana de tolerancia que ya usa contenedor. Para el resto, que no tienen ese ancla o no tienen modo diferido, basta con el episodio más reciente de ese origen. No incluye dar cobertura de diagnóstico a los crons de Hermes, que hoy comparten la alarma \"agentes\" con los LaunchAgents pero no los cubre ningún origen del motor. No incluye ningún cambio de frontend — ya es agnóstico al origen. No incluye poder lanzar un diagnóstico nuevo desde el navegador."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recuperar el diagnóstico de contenedor, hoy roto en producción (Priority: P1)

Miquel abre la pestaña "Alarmas" y ve un contenedor caído que ya
diagnosticó por CLI durante esta misma caída. Hoy no ve nada — la
consulta que empareja la alarma con el episodio lleva rota desde el
2026-08-11 (usa una columna que ya no existe), y el fallo se traga en
silencio. Miquel quiere que vuelva a funcionar exactamente como
describía el feature 008.

**Why this priority**: Es una regresión activa de una funcionalidad ya
construida y validada — Principio XII (Precisión del Dashboard, NO
NEGOCIABLE) violado ahora mismo. Arreglarla es requisito previo para
generalizar: no tiene sentido extender una consulta rota a 9 orígenes
más.

**Independent Test**: Se puede probar por completo diagnosticando en
vivo un contenedor caído por CLI, abriendo la pestaña Alarmas, y
comprobando que la alarma vuelve a mostrar la conclusión — mismos
escenarios que ya validó 008.

**Acceptance Scenarios**:

1. **Given** una alarma de un contenedor caído cuya caída actual ya se
   diagnosticó, **When** Miquel abre la pestaña, **Then** ve la
   conclusión junto a la alarma — igual que antes de que la migración
   de esquema del feature 009 rompiera el emparejamiento.
2. **Given** el estado real de `diagnostico.db` hoy (esquema
   `componente`+`origen`, sin columna `contenedor`), **When** se
   ejecuta la consulta de emparejamiento, **Then** no lanza ningún
   error de columna inexistente.

---

### User Story 2 - Ver el diagnóstico de los 7 orígenes con identidad estable (Priority: P1)

Para las alarmas de HA, disco, relay, host externo, agente
(LaunchAgent), latido de monitor e inventario de cobertura, Miquel
quiere ver el mismo tipo de sección de diagnóstico que ya ve para
contenedor, cuando exista un episodio diagnosticado para ese
componente concreto.

**Why this priority**: Es el valor central de la generalización — sin
esto, 7 de los 9 orígenes generalizados en 009-017 siguen siendo
invisibles fuera de la CLI, el mismo problema que 008 ya resolvió para
contenedor.

**Independent Test**: Se puede probar por completo diagnosticando en
vivo un componente de cada uno de los 7 orígenes por CLI, abriendo la
pestaña Alarmas (si hay una alarma activa para ese componente), y
comprobando que muestra la conclusión — mismo criterio de éxito que
User Story 1, replicado por origen.

**Acceptance Scenarios**:

1. **Given** una alarma de HA cuyo check ya se diagnosticó dentro de
   la ventana de tolerancia de esa caída, **When** Miquel abre la
   pestaña, **Then** ve la conclusión — emparejada por el identificador
   real del check (`cid`), no por su etiqueta de pantalla.
2. **Given** una alarma de disco, relay, host externo, agente o
   inventario con un episodio diagnosticado del mismo componente,
   **When** Miquel abre la pestaña, **Then** ve la conclusión más
   reciente para ese componente — sin ventana temporal, porque esa
   alarma no lleva ningún ancla de "desde cuándo".
3. **Given** una alarma de latido de monitor con un episodio
   diagnosticado del mismo `job`, **When** Miquel abre la pestaña,
   **Then** ve la conclusión — emparejada por el `job` real (feature
   017), no por la etiqueta legible que muestra la alarma.
4. **Given** una alarma de relay caído cuyo único diagnóstico
   disponible es en diferido (agregado, sin nombre de relay
   identificado), **When** Miquel abre la pestaña, **Then** esa alarma
   no muestra ningún diagnóstico — un diagnóstico agregado nunca se le
   atribuye a un relay concreto (limitación real del origen `relay`,
   no un fallo de este feature).
5. **Given** una alarma de la Central de Alarmas agrupada (varias
   caídas del mismo tipo a la vez, feature 006 FR-013), **When**
   Miquel abre la pestaña, **Then** esa entrada agrupada no muestra
   ningún diagnóstico — mismo criterio que FR-012 de 008 para
   contenedor, generalizado a cualquier origen.

---

### User Story 3 - Ver el diagnóstico de los 2 orígenes sin identidad estable (Priority: P2)

Para las alarmas de backup diario y del propio hub de Beszel —donde
solo existe un backup y un hub, sin un nombre que los distinga—,
Miquel quiere ver el diagnóstico más reciente de ese origen cuando
exista, sin necesitar un nombre de componente con el que emparejar.

**Why this priority**: Depende del mismo mecanismo que User Story 2,
pero cubre un caso distinto (sin identidad de componente en absoluto,
solo un origen singleton) — menos urgente porque son solo 2 de los 9
orígenes, y ya quedan cubiertos honestamente como "sin diagnóstico"
hasta que se implemente.

**Independent Test**: Se puede probar diagnosticando en vivo el
backup o el hub de Beszel por CLI, abriendo la pestaña Alarmas (si hay
una alarma activa de ese origen), y comprobando que muestra la
conclusión del episodio más reciente de ese origen.

**Acceptance Scenarios**:

1. **Given** una alarma de backup diario atrasado con al menos un
   episodio de origen `backup` ya diagnosticado, **When** Miquel abre
   la pestaña, **Then** ve la conclusión del episodio más reciente de
   ese origen, con su fecha visible.
2. **Given** una alarma del hub de Beszel sin reportar con al menos un
   episodio de origen `hub_beszel` ya diagnosticado, **When** Miquel
   abre la pestaña, **Then** ve la conclusión del episodio más
   reciente de ese origen, con su fecha visible.

---

### Edge Cases

- ¿Qué pasa con la alarma de "Crons" de Hermes, que hoy comparte el
  origen visual `agentes` con los LaunchAgents? No obtiene ninguna
  sección de diagnóstico — ningún origen de `diagnostico.py` cubre los
  crons de Hermes (mecanismo distinto, `get_crons()`, nunca
  generalizado). Se trata igual que "sin episodio asociado", nunca
  como un error.
- ¿Qué pasa si `diagnostico.db` no existe o no se puede leer? Las
  alarmas se siguen mostrando con normalidad, sin ninguna sección de
  diagnóstico — mismo comportamiento a prueba de fallos que ya exigía
  FR-008 de 008, ahora para los 10 orígenes.
- ¿Qué pasa si un origen sin identidad estable (backup, hub_beszel)
  nunca se ha diagnosticado todavía? No muestra ninguna sección — igual
  que "sin episodio asociado" en cualquier otro origen.
- ¿Qué pasa con un origen sin modo diferido (agente, latido) cuyo
  único episodio real es mucho más antiguo que la alarma actual?
  Se muestra igualmente — sin ventana temporal que aplicar, es el
  único diagnóstico posible de ese componente, con su fecha siempre
  visible para que Miquel juzgue la vigencia él mismo (mismo principio
  de transparencia que FR-004/FR-005 de 008).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE corregir el emparejamiento de
  diagnóstico de contenedor para que funcione contra el esquema real
  de `diagnostico.db` (`componente`+`origen`, no `contenedor`) — User
  Story 1.
- **FR-002**: El sistema DEBE, para cada alarma de HA, disco, relay,
  host externo, agente (LaunchAgent), latido de monitor, o brecha de
  inventario, comprobar si existe un episodio diagnosticado del mismo
  origen y del mismo componente, usando el identificador real que usa
  `diagnostico.db` para ese origen — no necesariamente la etiqueta de
  pantalla de la alarma (research.md documenta la correspondencia
  exacta por origen).
- **FR-003**: Cuando el origen tenga modo diferido y la alarma lleve
  un ancla temporal real (contenedor, HA), el sistema DEBE aplicar la
  misma tolerancia de ventana ya validada por el feature 008 — nunca
  mostrar el diagnóstico de una caída anterior ya resuelta como si
  fuera de la actual.
- **FR-004**: Cuando el origen no tenga ancla temporal en la propia
  alarma (disco, relay, host externo, agente, latido, inventario), el
  sistema DEBE mostrar el episodio más reciente de ese origen y
  componente, sin inventar una ventana que la evidencia no tiene.
- **FR-005**: El sistema DEBE, para los orígenes `backup` y
  `hub_beszel` (sin identidad de componente estable — el propio
  `componente` es el momento del diagnóstico), mostrar el episodio más
  reciente de ese origen, sin comprobación de nombre — User Story 3.
- **FR-006**: El sistema NO DEBE mostrar ningún diagnóstico para la
  alarma de Crons de Hermes — ningún origen del motor los cubre
  todavía.
- **FR-007**: El sistema NO DEBE mostrar ningún diagnóstico en una
  alarma agrupada (feature 006 FR-013), para ningún origen — mismo
  criterio que FR-012 de 008, generalizado.
- **FR-008**: El sistema DEBE seguir mostrando cada hipótesis
  considerada de un diagnóstico visible (descripción, comprobación,
  desenlace) para cualquier origen, con el mismo detalle que ya exigía
  FR-003 de 008 — sin cambios de frontend, ya es agnóstico al origen.
- **FR-009**: Si los datos de diagnóstico no están disponibles o no se
  pueden leer para un origen concreto, el sistema NO DEBE dejar de
  mostrar las alarmas de ese origen ni de ningún otro — mismo criterio
  a prueba de fallos que FR-008 de 008, con cada origen aislado del
  resto (un origen roto no debe tumbar los demás).
- **FR-010**: El sistema NO DEBE ofrecer ninguna forma de lanzar un
  diagnóstico nuevo desde el dashboard — estrictamente de lectura,
  mismo alcance que FR-009 de 008.
- **FR-011**: El sistema NO DEBE modificar ni escribir nunca los datos
  de diagnóstico — solo lectura, mismo alcance que FR-010 de 008.
- **FR-012**: El sistema NO DEBE dar cobertura de diagnóstico a los
  crons de Hermes en este feature — es un mecanismo sin origen en
  `diagnostico.py`, fuera de alcance (ver FR-006 y Assumptions).

### Key Entities

- **Alarma de cualquier origen**: ya existente (feature 006, los 10
  orígenes de `get_active_alarms()`). Este feature le añade, cuando
  aplica, un diagnóstico asociado — generalización de lo que 008 ya
  hacía solo para contenedor.
- **Episodio diagnosticado**: ya existente (007, generalizado por
  009-017). El vínculo con una alarma se hace por `origen` +
  identificador real del componente (research.md documenta el mapeo
  por origen, no siempre igual a la etiqueta que muestra la alarma) y,
  cuando aplica, proximidad temporal al ancla de la alarma.
- **Diagnóstico / Hipótesis / Gasto diario**: ya existentes (007) — se
  leen tal cual, sin transformarlos, para cualquier origen.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El emparejamiento de contenedor vuelve a funcionar
  contra el esquema real — 0 errores de "columna inexistente" al
  consultar `diagnostico.db` (User Story 1).
- **SC-002**: El 100% de las alarmas activas de los 7 orígenes de User
  Story 2 con un episodio diagnosticado real del mismo componente
  muestran su conclusión en el dashboard, sin que Miquel necesite
  ejecutar ningún comando.
- **SC-003**: El 100% de las alarmas activas de `backup`/`hub_beszel`
  con al menos un episodio diagnosticado de ese origen muestran la
  conclusión del más reciente (User Story 3).
- **SC-004**: El 0% de los diagnósticos mostrados, para cualquier
  origen con modo diferido y ancla temporal, corresponde a una caída
  anterior ya resuelta distinta de la que causa la alarma mostrada —
  mismo criterio que SC-006 de 008, generalizado.
- **SC-005**: El 0% de las alarmas de Crons de Hermes o de alarmas
  agrupadas muestra ningún diagnóstico.
- **SC-006**: Una alarma de cualquier origen sin diagnóstico asociado
  se sigue viendo, antes y después de este feature, exactamente igual
  — cero regresiones sobre la pestaña "Alarmas" ya existente.

## Assumptions

- **Bug real confirmado antes de especificar** (no una suposición): la
  consulta de emparejamiento de contenedor usa `WHERE contenedor = ?`
  contra un esquema que ya no tiene esa columna desde el feature 009
  (`store.py::_migrar_episodios_contenedor_a_componente`) — comprobado
  ejecutando la consulta real contra `diagnostico.db`
  (`BRIEFING.md`, "Feature 018 — material de partida"). El visor de
  contenedor lleva roto en producción desde el 2026-08-11.
- **El frontend (JS/CSS) no cambia** — `diagnosticoHtml(a)` ya se
  invoca para cualquier alarma con `a.diagnostico` no nulo, sin
  distinguir de qué origen es (comprobado leyendo `app.py`). Todo el
  trabajo de este feature es backend.
- **La identidad real para emparejar no siempre coincide con la
  etiqueta que muestra la alarma** — HA usa `cid` (no `label`), latido
  usa `job` (no `label`), agente usa el `label` completo del
  LaunchAgent (no el `short` que se muestra en pantalla), host externo
  usa el nombre canónico de `HOSTS_EXTERNOS` (no el nombre de
  pantalla). Documentado por origen en `research.md`.
- **`relay` solo empareja diagnósticos hechos en vivo por nombre
  concreto** — en diferido, la evidencia agregada de ese origen nunca
  identifica cuál relay causó la caída (research.md de 012). No es un
  fallo de este feature ni algo a corregir aquí — es una limitación
  real y ya documentada del propio motor.
- **`backup` y `hub_beszel` no tienen identidad de componente
  estable** — su `componente` en `diagnostico.db` es el momento ISO
  del propio diagnóstico, no un nombre. Se emparejan por origen
  solamente, tomando el episodio más reciente.
- **Los crons de Hermes quedan fuera de alcance** — comparten la
  alarma visual `agentes` con los LaunchAgents, pero ningún origen de
  `diagnostico.py` los cubre; ampliar eso es un feature nuevo, no
  este.
- **Todo el código de este feature vive fuera de este repositorio**
  (`homelab-dashboard/scripts/app.py`, sin control de versiones) —
  mismo patrón que 008. Este repo solo contiene spec, plan y
  contratos.
- **No se añade ningún control para lanzar diagnósticos nuevos desde
  el dashboard** — sigue siendo exclusivamente por línea de comandos,
  mismo criterio que 008.
