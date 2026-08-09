# Feature Specification: Central de Alarmas del Homelab

**Feature Branch**: `006-central-alarmas`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "El homelab ya vigila casi todo (Frente 1 del proyecto, cerrado): 9 sistemas distintos calculan hoy si algo está mal — contenedores, Home Assistant, backups, relays, hosts externos, el propio hub de Beszel, agentes programados, discos y el inventario de cobertura. El problema es que esa información vive repartida en 6 pestañas del dashboard, cada una con su propio formato, y no hay ningún sitio que diga de un vistazo \"esto es todo lo que está roto ahora mismo\". Quiero una pestaña nueva, \"Alarmas\", que reúna en una sola lista cualquier alarma activa de cualquiera de esos 9 orígenes, ordenada por gravedad. Cada alarma tiene que traer, además del dato en bruto que ya existe, una explicación en lenguaje sencillo de qué significa ese fallo y una sugerencia de cómo solucionarlo — en texto, para que yo decida y actúe, no algo que el sistema ejecute solo. No incluye ninguna corrección automática ni un agente que decida por su cuenta — eso es explícitamente para más adelante. Tampoco incluye vigilar nada que hoy no se vigile ya: esta pestaña muestra lo que los 9 sistemas existentes ya calculan, no añade una fuente de datos nueva."

## Clarifications

### Session 2026-08-09

- Q: Si un solo fallo raíz hace que un origen reporte muchas alarmas de
  golpe (p. ej. la API de HA cae y sus 113 checks fallan a la vez, o el
  daemon Docker/OrbStack deja de responder y los 40 contenedores
  parecen caídos), ¿la pestaña debe mostrar una fila por fallo
  individual o agrupar los que comparten origen y motivo en una
  entrada resumen? →
  A: Agrupar cuando hay muchas alarmas del mismo origen y motivo a la
  vez (umbral pequeño, por ejemplo 5), en una sola entrada resumen.
- Q: Los 10 orígenes no comparten ninguna escala de gravedad común —
  ¿con qué criterio se ordena la lista para que "lo más grave primero"
  (FR-004) sea real? → A: 3 niveles fijos por tipo de alarma (Crítico
  / Aviso / Informativo), reutilizando el mismo lenguaje warn/crit que
  ya usa el dashboard; dentro del mismo nivel, la más antigua primero.
- Q: El atributo "antigüedad" no existe hoy para todos los orígenes
  (un disco es una lectura instantánea, sin ningún "desde cuándo"
  guardado) — añadirlo donde falta exigiría un estado nuevo, en contra
  de FR-002. ¿Cómo se trata cuando el origen no la proporciona? → A:
  Es opcional; se omite para los orígenes que no la calculan ya, sin
  añadir ningún estado nuevo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver de un vistazo todo lo que está roto en el homelab (Priority: P1)

Miquel quiere abrir una única pestaña "Alarmas" en el dashboard y ver
ahí, en una sola lista, cualquier alarma activa de cualquiera de los 10
orígenes que el homelab ya vigila (contenedores, Home Assistant,
backups, latidos de monitores programados, relays socat, hosts
externos vigilados por Beszel, salud del propio hub de Beszel, agentes
programados, discos, e inventario de cobertura) — sin tener que
recorrer las 6 pestañas actuales para reconstruir el cuadro completo.

**Why this priority**: Es el valor mínimo del feature — sin la
agregación no hay "central de alarmas"; el resto (explicación,
remediación) son capas que solo tienen sentido sobre esta base.

**Independent Test**: Con al menos uno de los 10 orígenes en una
condición de fallo real (viva o histórica), abrir la pestaña Alarmas
y comprobar que esa alarma aparece en la lista; y que si ningún origen
tiene ninguna condición de fallo activa, la pestaña lo indica
explícitamente en vez de aparecer vacía sin contexto.

**Acceptance Scenarios**:

1. **Given** al menos uno de los 10 orígenes tiene una condición de
   fallo activa ahora mismo, **When** Miquel abre la pestaña Alarmas,
   **Then** ve esa alarma listada, con su origen y el componente
   afectado identificados.
2. **Given** ninguno de los 10 orígenes tiene ninguna condición de
   fallo activa, **When** Miquel abre la pestaña Alarmas, **Then** ve
   un mensaje explícito de que no hay alarmas activas, no una lista
   vacía sin explicación.
3. **Given** dos orígenes distintos reportan alarmas sobre problemas
   no relacionados entre sí a la vez, **When** Miquel abre la
   pestaña, **Then** ambas aparecen como entradas independientes en
   la lista.

---

### User Story 2 - Entender qué significa cada alarma sin investigarla (Priority: P2)

Para cada alarma de la lista, Miquel quiere una explicación en
lenguaje sencillo de qué está pasando — no solo el dato en bruto que
cada origen ya produce (por ejemplo, `state=unavailable`), sino qué
implica eso para el homelab.

**Why this priority**: Depende de que la User Story 1 exista primero
(no hay dónde poner la explicación sin la lista); es lo que separa
esta pestaña de simplemente copiar las tablas que ya existen en otras
pestañas.

**Independent Test**: Se puede probar comprobando, para un tipo de
alarma con texto ya escrito, que lo mostrado no es únicamente el
valor técnico bruto, sino una frase que una persona sin acceso al
código pueda entender.

**Acceptance Scenarios**:

1. **Given** una alarma de un tipo con explicación ya escrita,
   **When** se muestra en la lista, **Then** incluye esa explicación
   en prosa, visible sin necesidad de ninguna acción adicional.
2. **Given** una alarma de un tipo todavía sin explicación escrita,
   **When** se muestra en la lista, **Then** se indica explícitamente
   que no hay explicación documentada todavía, en vez de mostrar solo
   el dato en bruto sin ningún aviso.

---

### User Story 3 - Tener una sugerencia de qué hacer, sin que nada se ejecute solo (Priority: P3)

Junto a la explicación, Miquel quiere una remediación sugerida en
texto — qué comprobar o qué acción tomar — para decidir y actuar él
mismo. Ningún control de la pestaña ejecuta ninguna acción sobre el
homelab.

**Why this priority**: Es la culminación del feature, pero depende de
que existan la lista (US1) y la explicación (US2) — una remediación
sin ese contexto no aporta nada por sí sola.

**Independent Test**: Se puede probar comprobando que ninguna
interacción de la pestaña Alarmas modifica nada del homelab, y que
cada alarma trae un texto de remediación sugerida o el aviso
explícito de que todavía no existe una para ese tipo.

**Acceptance Scenarios**:

1. **Given** una alarma de un tipo con remediación ya escrita,
   **When** se muestra en la lista, **Then** incluye ese texto, sin
   ningún control que la ejecute automáticamente.
2. **Given** una alarma de un tipo sin remediación escrita todavía,
   **When** se muestra, **Then** se indica explícitamente que no hay
   remediación documentada, en vez de omitir esa sección o mostrarla
   vacía sin explicación.
3. **Given** cualquier alarma mostrada en la pestaña, **When** Miquel
   la revisa, **Then** ninguna acción disponible en la pestaña
   ejecuta cambios en el homelab.

---

### Edge Cases

- ¿Qué pasa si uno de los 10 orígenes deja de responder (por ejemplo,
  el fichero que lee no existe o no se puede interpretar)? Debe
  aparecer como su propia alarma de "origen sin datos" — igual que
  cada pestaña actual ya distingue "sin datos" de "ok" — nunca como
  ausencia silenciosa de esa fuente en la lista (Principio II: salud
  por resultado, no por ejecución).
- ¿Qué pasa con condiciones que un origen ya clasifica como
  intencionadas o falso positivo conocido (por ejemplo, `frigate`
  parado a propósito, o las automatizaciones "controladas a mano" ya
  triadas en el feature de triage de `entidad_ha`)? No deben aparecer
  como alarma real — la pestaña respeta la clasificación de
  intencionalidad que cada origen ya calcula, no la reevalúa.
- ¿Qué pasa si dos orígenes reportan sobre el mismo componente físico
  a la vez (por ejemplo, un contenedor caído y, a la vez, el latido de
  su monitor caducado)? Aparecen como dos entradas independientes —
  este feature no fusiona ni deduplica entre orígenes distintos.
- ¿Qué pasa con un tipo de alarma que no encaja en ningún tipo
  conocido con texto ya escrito? Se muestra igualmente, con el dato en
  bruto del origen y un aviso explícito de "sin explicación/
  remediación documentada todavía" — nunca se oculta (Principio XII:
  ninguna alarma real activa puede faltar).
- ¿Qué pasa si un solo fallo raíz hace que un origen reporte muchas
  alarmas a la vez (por ejemplo, la API de Home Assistant cae y sus
  113 checks fallan de golpe, o el daemon Docker/OrbStack deja de
  responder y los 40 contenedores parecen caídos)? Se agrupan en una
  sola entrada resumen en vez de listar cada fallo individual — ver
  FR-013.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mostrar, en una pestaña nueva "Alarmas"
  del dashboard ya existente, toda alarma activa procedente de los 10
  orígenes ya calculados: estado de contenedores, checks de Home
  Assistant, heartbeat de backup diario, latidos de monitores
  programados, relays socat, hosts externos vigilados por Beszel,
  salud del propio hub de Beszel, estado de agentes/crons
  programados, uso de disco, y brechas del inventario de cobertura.
- **FR-002**: El sistema NO DEBE calcular ninguna condición de alarma
  nueva — DEBE limitarse a leer y presentar las señales que esos 9
  orígenes ya producen.
- **FR-003**: El sistema DEBE mostrar, para cada alarma, como mínimo:
  el origen, el componente o entidad afectada, y el mensaje o dato ya
  calculado por ese origen.
- **FR-004**: El sistema DEBE ordenar la lista de alarmas por gravedad,
  clasificando cada *tipo* de alarma en uno de tres niveles fijos —
  Crítico, Aviso, Informativo — usando el mismo lenguaje warn/crit ya
  establecido en el resto del dashboard (por ejemplo: un contenedor de
  la lista de críticos caído, o el hub de Beszel sin reportar, son
  Crítico; un disco por encima del umbral de aviso, o un host externo
  confirmado caído, son Aviso; un host externo "sin evidencia" —
  ausencia de dato, no un fallo confirmado— o una brecha del
  inventario de cobertura, son Informativo). Dentro del mismo nivel,
  ordena por antigüedad — la más antigua primero.
- **FR-005**: El sistema DEBE mostrar, para cada alarma, una
  explicación en lenguaje sencillo de qué implica ese tipo de fallo,
  declarada por tipo de alarma — no redactada de forma distinta para
  cada instancia individual del mismo tipo.
- **FR-006**: El sistema DEBE mostrar, para cada alarma, una
  remediación sugerida en texto — qué comprobar o qué hacer — fija
  por tipo general de alarma, igual para todas sus instancias y
  submotivos (por ejemplo, un único texto para "entidad de Home
  Assistant no disponible", sin desglosar por `no_disponible` /
  `umbral` / `sin_respuesta`; un único texto para "contenedor caído",
  salvo la distinción de FR-007 para contenedores críticos).
- **FR-007**: Para alarmas sobre un contenedor de la lista de
  críticos del monitor (`homeassistant`, `vaultwarden`, `nextcloud` y
  su base de datos y redis, `immich` y sus componentes,
  `pangolin-server`, `gerbil`, `traefik`), la remediación sugerida
  DEBE advertir explícitamente que no se debe reiniciar ni modificar
  el contenedor sin aprobación humana previa, en vez de la
  recomendación genérica que se daría para un contenedor no crítico
  — coherente con la regla no negociable ya vigente en
  `docker_monitor.py`.
- **FR-008**: El sistema DEBE indicar explícitamente, para cualquier
  alarma de un tipo sin explicación o remediación escrita todavía,
  que esa información no existe aún — nunca debe ocultar la alarma ni
  mostrarla sin ningún aviso al respecto.
- **FR-009**: El sistema NO DEBE ejecutar ninguna acción sobre el
  homelab desde la pestaña Alarmas — ninguna remediación se aplica
  automáticamente ni mediante ningún control de la interfaz.
- **FR-010**: El sistema DEBE indicar explícitamente cuando ninguno de
  los 10 orígenes tiene ninguna alarma activa, en vez de mostrar una
  lista vacía sin contexto.
- **FR-011**: El sistema DEBE respetar la clasificación de
  "intencionado" o falso positivo conocido que cada origen ya
  calcula (por ejemplo, `frigate` parado a propósito, automatizaciones
  controladas a mano) — esas condiciones no deben aparecer como
  alarma real en la pestaña.
- **FR-012**: El sistema DEBE mostrar las alarmas de orígenes
  distintos como entradas independientes, incluso si se refieren al
  mismo componente físico — este feature no fusiona ni deduplica
  entre orígenes.
- **FR-013**: Cuando un mismo origen reporte más de un umbral pequeño
  (de referencia, 5) de alarmas activas a la vez del mismo *tipo* de
  alarma — el "motivo raíz" que motivó esta aclaración es, en la
  práctica, el propio `tipo` ya definido en FR-005/FR-006, no un
  concepto nuevo que distinguir (por ejemplo, todos los checks de Home
  Assistant fallando porque la API no responde comparten el tipo
  `ha_api_caida`, o todos los contenedores marcados caídos porque el
  daemon Docker/OrbStack no responde comparten `contenedor_caido`), el
  sistema DEBE agruparlas en una única entrada resumen (origen, tipo,
  cuántas alarmas incluye) en vez de mostrar una fila por cada una —
  para que un fallo en cascada no tape el resto de alarmas reales de
  la lista.
- **FR-014**: El sistema DEBE mostrar la antigüedad de una alarma
  (desde cuándo está activa) únicamente cuando el origen que la
  calcula ya la proporciona (contenedores, Home Assistant, backup,
  latidos de monitores, relays y hosts externos). Para orígenes de
  lectura instantánea sin ese dato (por ejemplo, discos), la alarma se
  muestra igualmente, sin ese atributo — el sistema NO DEBE crear
  ningún registro nuevo solo para calcularla.
- **FR-015**: El sistema NO DEBE depender de ningún LLM, servicio de
  IA ni token de API para producir la explicación o la remediación de
  ninguna alarma. Ambas son texto fijo por tipo de alarma, redactado
  una sola vez en tiempo de implementación (mismo patrón que los
  diccionarios `MONITOR_INFO`/`AGENT_DESC` ya usados en el dashboard),
  no generado ni en tiempo de ejecución ni por instancia. Esta fase es
  exclusivamente de detección y explicación estática — la generación
  dinámica de contenido mediante IA, si llega a hacer falta, queda
  para el feature de remediación posterior.

### Key Entities

- **Alarma activa**: instancia de un problema real detectado por uno
  de los 10 orígenes ya vigilados. Atributos relevantes: origen, tipo
  de alarma, componente o entidad afectada, mensaje/dato en bruto ya
  calculado, nivel de gravedad (Crítico/Aviso/Informativo) y,
  opcionalmente, antigüedad (desde cuándo está activa) — presente solo
  cuando el propio origen ya la calcula; los orígenes de lectura
  instantánea (por ejemplo, discos) no la incluyen. Cuando muchas
  alarmas del mismo origen comparten *tipo* (FR-013), se representan
  como una única alarma agrupada, con el recuento de cuántas incluye
  en vez de un componente individual — antigüedad de una entrada
  agrupada: la de la alarma más antigua del grupo (ver Assumptions).
- **Tipo de alarma**: categoría de fallo (por ejemplo, "contenedor
  caído", "entidad de Home Assistant no disponible", "disco por
  encima del umbral", "backup atrasado"...) a la que se asocia una
  explicación en prosa y una remediación sugerida, reutilizada por
  todas las alarmas activas de ese tipo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Miquel puede identificar cualquier problema activo del
  homelab consultando una única pestaña del dashboard, sin necesidad
  de revisar las otras 6 pestañas para reconstruir el cuadro
  completo.
- **SC-002**: El 100% de las alarmas activas mostradas incluye una
  explicación en lenguaje sencillo y una remediación sugerida, o un
  aviso explícito de que todavía no existe una para ese tipo.
- **SC-003**: El 100% de las acciones disponibles en la pestaña
  Alarmas son de solo lectura — ninguna modifica el estado del
  homelab.
- **SC-004**: Cuando no hay ningún problema activo en ninguno de los
  10 orígenes, la pestaña lo confirma explícitamente. La cláusula de
  tiempo de carga está garantizada por diseño, no medida aparte: la
  pestaña se pinta a partir de la misma respuesta de `/api/data` que
  ya cargan las demás pestañas, sin ninguna petición adicional (ver
  Assumptions).
- **SC-005**: El número de alarmas mostradas coincide, en cualquier
  momento, con el número de condiciones de fallo reales que ya
  calculan los 10 orígenes por separado — salvo cuando varias se
  agrupan en una entrada resumen (FR-013), en cuyo caso el recuento
  indicado en esa entrada coincide con el número real de fallos que
  agrupa (verificable comparando contra cada pestaña de origen).

## Assumptions

- No se añade ninguna fuente de datos ni lógica de detección nueva —
  se listan únicamente los 10 orígenes ya descritos en `BRIEFING.md`
  ("Feature 006 — material de partida"). Cualquier fuente futura se
  integraría en un feature posterior.
- **Antigüedad de una entrada agrupada (FR-013)**: es la de la alarma
  más antigua del grupo (el `antiguedad_s` máximo entre las que
  agrupa) — así una cascada reciente no oculta que el problema, en
  realidad, lleva activo más tiempo desde su primera instancia.
- **Disparo de `cron_con_error`**: reutiliza el mismo criterio que ya
  usa el resumen del dashboard para los crons de Hermes/Bautista
  (`status` distinto de `"ok"`/`"success"`) — no se define un enumerado
  nuevo de estados válidos, se hereda el que el propio dashboard ya
  usaba antes de este feature.
- **SC-004, tiempo de carga**: no se mide con un cronómetro — se
  garantiza por construcción, ya que la pestaña Alarmas se pinta a
  partir de la misma respuesta única de `/api/data` que las demás
  pestañas (`contracts/api-alarms.md`), sin ninguna petición de red
  adicional propia.
- La remediación automática y el agente de diagnóstico (principios
  IV a VIII de la constitución) quedan explícitamente fuera de este
  feature — es exclusivamente de detección y explicación.
- No se usa ningún token de API ni servicio de IA en esta fase (ver
  FR-015) — coherente con el Principio X (Local por Defecto): los
  datos de diagnóstico no salen de la máquina sin justificación
  explícita, y aquí no la hay. Un feature posterior de remediación
  real (Frente 2) es el candidato natural si en algún momento hace
  falta análisis dinámico con IA — decisión aparte, no de este spec.
- La asignación exacta de cada tipo de alarma concreto a uno de los
  tres niveles (Crítico / Aviso / Informativo) se completa en el plan
  — el criterio general (tres niveles fijos, antigüedad como
  desempate) ya queda fijado en FR-004.
- La deduplicación o agrupación de alarmas relacionadas entre
  distintos orígenes queda fuera de este feature.
- El repositorio es público (ver "Repositorio público" en
  `BRIEFING.md`): ni esta especificación ni el contenido mostrado
  deben incluir IPs, credenciales, ni nombres de entidades ligadas a
  dispositivos de seguridad física — solo software y tipos de
  componente.
