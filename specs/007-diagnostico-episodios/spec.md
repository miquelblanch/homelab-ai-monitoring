# Feature Specification: Diagnóstico de Episodios (Frente 2, sin remediación)

**Feature Branch**: `007-diagnostico-episodios`

**Created**: 2026-08-10

**Status**: Draft

**Input**: User description: "Con el Frente 1 cerrado (cobertura sistemática y detección unificada de alarmas, features 001-006), quiero empezar el Frente 2: un agente que diagnostique causas que no se conocen de antemano — algo que una tabla de reglas fijas no puede cubrir. El agente recibe un episodio (una alarma activa ahora mismo, o un episodio histórico ya cerrado como los reinicios de beszel) y tiene que formular varias hipótesis de causa probable, contrastar cada una contra datos reales del homelab (métricas, logs, estado de contenedores), y registrar cada hipótesis con su comprobación y su desenlace. El resultado siempre es uno de dos: una causa probable con su evidencia, o \"no se puede diagnosticar con la evidencia disponible\" — nunca debe inventarse una causa por dar una respuesta. Tiene que poder ejecutarse tanto en vivo como en diferido contra el mismo episodio histórico, para poder medirlo sin esperar a que algo se rompa de verdad. El caso de prueba es beszel: ya sé que 3 de 5 episodios comprobados no tienen evidencia suficiente, así que el éxito ahí es llegar a esa misma conclusión honesta, no inventarse una causa. Para generar las hipótesis quiero usar un LLM en la nube, con un límite de gasto diario (contando tokens reales de cada respuesta, no consultando la facturación de la API) que pare las llamadas al llegar a un límite diario y responda que no se puede diagnosticar sin superarlo. No incluye ejecutar ninguna acción correctiva ni sugerir una nueva remediación (eso ya lo cubre el feature 006 para las causas conocidas, y la lista cerrada de acciones reversibles es un feature posterior). No incluye tocar contenedores críticos de ninguna forma. No incluye ningún RAG sobre el histórico de resoluciones — sin episodios resueltos todavía no hay nada que indexar, eso queda para un feature posterior reutilizando GBrain. No incluye ninguna pestaña nueva en el dashboard — primero tiene que funcionar el mecanismo."

## Clarifications

### Session 2026-08-10

- Q: ¿El agente debe limitarse a episodios de reinicios/caídas de
  contenedores, o debe poder diagnosticar cualquiera de las 10 alarmas
  de la Central de Alarmas desde el principio? → A: Solo contenedores
  por ahora — coincide con el caso de prueba de beszel; generalizar la
  evidencia a las otras 9 fuentes queda para un feature posterior, una
  vez validado que el enfoque funciona para el caso más simple.
- Q: ¿Cómo se dispara el diagnóstico de un episodio — automático por
  cada alarma nueva, bajo demanda, o programado? → A: Bajo demanda —
  Miquel elige explícitamente qué episodio diagnosticar; nada se
  dispara solo. Controla mejor el gasto que un disparo automático, que
  el cortacircuitos diario no evitaría en una ráfaga puntual.
- Q: Una alarma en vivo no tiene id propio (se recalcula cada vez en
  el dashboard) — ¿qué identifica "el mismo episodio" para poder
  comprobar la reproducibilidad de FR-002? → A: Un snapshot de la
  evidencia se congela en el momento de elegir diagnosticar — la
  reproducibilidad se comprueba repitiendo el diagnóstico sobre ese
  snapshot guardado, no sobre "la alarma en vivo", que puede cambiar o
  desaparecer.
- Q: Miquel pidió inicialmente remediación automática al 100% para
  todos los contenedores sin diferenciar, incluidos los críticos —
  contradice la lista de aprobación explícita ya vigente en
  `docker_monitor.py`/`SOUL.md` de Bautista y el Principio V (NO
  NEGOCIABLE) de la constitución. → A: Se descarta — la lista crítica
  se queda exactamente como está, sin remediación automática. Lo que
  sí quedó confirmado como requisito explícito: el agente DEBE
  diagnosticar (sin actuar) los episodios de contenedores críticos con
  el mismo rigor que los no críticos (FR-013/FR-013a) — es el caso
  donde más falta hace el diagnóstico, precisamente porque no hay red
  de seguridad automática detrás.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar un episodio en diferido, reproduciblemente (Priority: P1)

Miquel quiere poder ejecutar el agente contra un episodio ya ocurrido
(por ejemplo, uno de los reinicios históricos de `beszel`) y obtener
siempre la misma conclusión si le da los mismos datos de entrada — sin
depender de que el sistema esté en vivo ni de esperar a que algo se
rompa para poder probar el agente.

**Why this priority**: Es la base de todo lo demás — sin poder
reproducir un diagnóstico en diferido (Principio XI), no hay forma de
medir si el agente funciona ni de compararlo contra la línea base ya
establecida (los 5 episodios de beszel ya investigados a mano).

**Independent Test**: Se puede probar por completo ejecutando el
agente dos veces contra el mismo episodio histórico de `beszel` (mismo
`restart_history`, misma ventana de `container_metrics`/`disk_metrics`)
y comprobando que produce la misma conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un episodio histórico de `restart_history` con su ventana
   de métricas asociada, **When** Miquel ejecuta el agente contra ese
   episodio, **Then** el agente reúne esa evidencia real y produce una
   conclusión (causa probable, o "no se puede diagnosticar").
2. **Given** el mismo episodio histórico, **When** se ejecuta el
   agente una segunda vez sin que los datos de entrada hayan cambiado,
   **Then** produce la misma conclusión que la primera vez.
3. **Given** uno de los 3 episodios de beszel ya identificados como
   "sin evidencia suficiente" en la investigación manual, **When** el
   agente lo diagnostica, **Then** concluye "no se puede diagnosticar
   con la evidencia disponible" — no inventa una causa.
4. **Given** un episodio de un contenedor de la lista de críticos
   (por ejemplo, `homeassistant`), **When** Miquel lo diagnostica,
   **Then** el agente reúne evidencia y formula hipótesis con el mismo
   rigor que para un contenedor no crítico, y la conclusión no incluye
   ninguna acción ejecutada ni propuesta sobre él (FR-013/FR-013a).

---

### User Story 2 - Formular y contrastar varias hipótesis, con registro (Priority: P1)

Para cualquier episodio, Miquel quiere que el agente no se quede en la
primera explicación plausible: que proponga varias hipótesis de causa
probable, compruebe cada una contra los datos reales disponibles, y
dejen constancia escrita de qué se comprobó y con qué resultado —
legible después, no solo mientras corre.

**Why this priority**: Es el valor central del feature — sin varias
hipótesis contrastadas y registradas, esto no es diagnóstico, es una
opinión sin auditar (Principio VIII).

**Independent Test**: Se puede probar revisando, para una ejecución
cualquiera del agente, el registro resultante: debe listar más de una
hipótesis considerada, con su comprobación concreta contra datos reales
y su desenlace (confirmada, descartada, o sin evidencia suficiente).

**Acceptance Scenarios**:

1. **Given** un episodio con evidencia suficiente para al menos una
   causa probable, **When** el agente lo diagnostica, **Then** el
   registro resultante incluye más de una hipótesis contrastada, no
   solo la que resultó confirmada.
2. **Given** una hipótesis que el agente comprueba y descarta,
   **When** se revisa el registro, **Then** queda constancia de por
   qué se descartó, no solo de que se descartó.
3. **Given** cualquier episodio diagnosticado, **When** se revisa el
   registro más tarde (no en el momento de la ejecución), **Then** se
   puede reconstruir qué se pensó, qué se comprobó y por qué se llegó
   a esa conclusión, sin volver a ejecutar el agente.

---

### User Story 3 - No gastar más de lo previsto en un día (Priority: P2)

Miquel quiere generar las hipótesis con DeepSeek sin arriesgarse a una
factura inesperada — un límite de gasto diario que, al alcanzarse,
detenga las llamadas nuevas hasta el día siguiente en vez de seguir
gastando.

**Why this priority**: Depende de que exista ya el mecanismo de
diagnóstico (US1/US2) — el cortacircuitos protege un gasto que solo
existe una vez que el agente hace llamadas reales; no tiene sentido
antes.

**Independent Test**: Se puede probar fijando el límite diario a un
valor ya superado por el gasto acumulado del día y comprobando que la
siguiente llamada no se realiza — el agente responde que no puede
diagnosticar sin superar el límite, en vez de llamar a la API de todos
modos.

**Acceptance Scenarios**:

1. **Given** el gasto acumulado del día está por debajo del límite
   diario, **When** el agente necesita generar hipótesis, **Then**
   llama a DeepSeek con normalidad y suma el coste real de esa llamada
   (a partir de los tokens que la propia respuesta reporta) al
   acumulado del día.
2. **Given** el gasto acumulado del día ya alcanza o supera el límite
   diario, **When** el agente necesita generar hipótesis nuevas,
   **Then** no llama a DeepSeek y concluye explícitamente que no puede
   diagnosticar ese episodio sin superar el límite del día — nunca
   fuerza la llamada.
3. **Given** ha pasado a un nuevo día natural, **When** el agente
   necesita generar hipótesis, **Then** el acumulado de gasto se
   considera reiniciado a cero para ese nuevo día.

---

### Edge Cases

- ¿Qué pasa si no hay ningún dato de contexto disponible para un
  episodio (por ejemplo, `container_metrics` ya purgado por retención)?
  El agente concluye "no se puede diagnosticar con la evidencia
  disponible" — ausencia de datos nunca se trata como confirmación de
  ninguna hipótesis (Principio II, salud/certeza por resultado, no por
  omisión).
- ¿Qué pasa si DeepSeek no responde o responde con un error? Se trata
  igual que alcanzar el límite de gasto — el agente no fuerza una
  conclusión sin las hipótesis del LLM; registra el fallo y concluye
  que no pudo diagnosticar en ese intento.
- ¿Qué pasa si dos ejecuciones en diferido del mismo episodio producen
  distinto `conclusion_tipo` (causa_probable en una, no_diagnosticable
  en la otra)? Rompe la garantía de reproducibilidad de la User Story 1
  — es un fallo real, no un comportamiento aceptable de este feature.
- ¿Qué pasa si dos ejecuciones en diferido del mismo episodio coinciden
  en `conclusion_tipo` pero varían en el número o el detalle de las
  hipótesis formuladas (por ejemplo, 0 hipótesis en un intento y 3 en
  otro)? **Resuelto el 2026-08-11** (hallazgos U1/I1 de
  `/speckit-analyze`, con evidencia real de T030: mismo episodio,
  mismo `conclusion_tipo`, distinto número de hipótesis): esto **sí**
  es un comportamiento aceptado de este feature, no una regresión que
  perseguir. `temperature=0` reduce pero no elimina la variación de un
  LLM en la nube en el texto y número de hipótesis que formula
  (research.md §2); SC-001 y FR-002 exigen reproducibilidad de la
  **conclusión** (`conclusion_tipo`), que es el resultado que de verdad
  usa Miquel para decidir — no la composición exacta de hipótesis
  intermedias. La variante de la User Story 1 sobre un
  `conclusion_tipo` distinto sigue siendo un fallo real; esta, no.
- ¿Qué pasa con un episodio sobre un contenedor crítico? El agente
  DEBE reunir evidencia y formular hipótesis igual que con cualquier
  otro contenedor (FR-013) — no es opcional, es precisamente el caso
  donde el diagnóstico más falta hace, ya que no hay remediación
  automática de respaldo. Este feature no incluye ninguna vía para
  proponer ni ejecutar una acción sobre él (FR-013a).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de contenedor (caída
  o reinicio) como entrada, tanto en vivo (una alarma activa de tipo
  `contenedor_caido`/`contenedor_caido_critico` de la Central de
  Alarmas) como en diferido (un episodio histórico ya cerrado de
  `restart_history`, con su ventana de métricas asociada). Las alarmas
  de los otros 9 orígenes de la Central de Alarmas quedan fuera de este
  feature.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio en
  vivo, congelar un snapshot de su evidencia en ese momento — el
  contenedor, la ventana de tiempo y las métricas asociadas. Para un
  mismo snapshot (en vivo ya congelado, o histórico) DEBE producir el
  mismo `conclusion_tipo` en ejecuciones distintas (Principio XI,
  Reproducibilidad Diferida) — no se exige que el número o el detalle
  de las hipótesis intermedias coincida entre ejecuciones (ver SC-001,
  Edge Cases). La reproducibilidad se exige contra el snapshot
  guardado, no contra el estado en vivo del homelab, que puede cambiar
  entre una ejecución y otra.
- **FR-003**: El sistema DEBE reunir evidencia real del homelab
  asociada al episodio (métricas de contenedores/disco, logs, estado
  de otros componentes relevantes) antes de formular ninguna hipótesis.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio cuando la evidencia lo permita, no detenerse
  en la primera explicación plausible.
- **FR-005**: El sistema DEBE contrastar cada hipótesis formulada
  contra la evidencia reunida antes de aceptarla o descartarla.
- **FR-006**: El sistema DEBE registrar cada hipótesis formulada junto
  con su comprobación concreta y su desenlace (confirmada, descartada,
  o sin evidencia suficiente para decidir), de forma legible después de
  que termine la ejecución (Principio VIII).
- **FR-007**: El sistema DEBE concluir cada diagnóstico con exactamente
  uno de dos resultados: una causa probable respaldada por evidencia
  concreta, o una declaración explícita de que no se puede diagnosticar
  con la evidencia disponible. NO DEBE presentar nunca una causa sin
  evidencia que la respalde.
- **FR-008**: El sistema DEBE usar un LLM en la nube (DeepSeek) para
  formular las hipótesis de causa probable.
- **FR-009**: El sistema DEBE llevar un acumulado de gasto real en
  tokens de DeepSeek por día natural, calculado a partir del uso que
  reporta cada respuesta de la API — nunca consultando la facturación
  de la API en tiempo real.
- **FR-010**: El sistema NO DEBE realizar ninguna llamada a DeepSeek
  que haga superar el límite de gasto diario configurado; al
  alcanzarlo, DEBE concluir que no puede diagnosticar ese episodio sin
  superar el límite, en vez de realizar la llamada de todos modos.
- **FR-011**: El sistema DEBE poder validarse contra episodios
  históricos reales de `beszel` (`restart_history.container_name =
  'beszel'`, 49 filas en total), incluidos los que no tengan evidencia
  de métricas suficiente — el diagnóstico automático DEBE concluir
  `no_diagnosticable` para esos, nunca inventar una causa (Principio
  IX, medida contra la línea base). **Corregido el 2026-08-11**
  (hallazgo U2 de `/speckit-analyze`): la formulación original citaba
  "los 5 episodios ya investigados a mano, 3 sin evidencia suficiente"
  de la investigación manual descrita en `BRIEFING.md` (Caso 1) — pero
  ningún artefacto de este repo llegó a registrar nunca los
  `restart_history_id` concretos de esos 5, así que no se podían usar
  como línea base verificable. El conjunto de referencia vigente desde
  esta corrección es el que T030 validó de verdad contra DeepSeek real
  (`tasks.md`): `restart_history_id` 16, 17, 25 (evidencia de métricas
  totalmente vacía — coincide con el patrón "sin evidencia suficiente"
  de la investigación original) y 4, 79, 81 (con 2 muestras horarias
  cada uno). No se afirma que estos sean los mismos 5 de la
  investigación manual original — solo que son el conjunto real,
  documentado y reproducible que este feature usa como línea base a
  partir de ahora (ver SC-002).
- **FR-012**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre el homelab, ni proponer una remediación nueva más allá de lo
  que el feature 006 ya sugiere de forma estática para causas conocidas
  de antemano.
- **FR-013**: El sistema DEBE diagnosticar episodios de contenedores
  críticos exactamente igual que los no críticos — mismas hipótesis,
  misma evidencia, mismo registro (Principio VIII) — precisamente
  porque no hay remediación automática para ellos (FR-013a): sin este
  diagnóstico, un fallo real en un contenedor crítico solo generaría la
  alarma ya estática del feature 006, sin ninguna pista adicional
  sobre la causa. El sistema NO DEBE, en ningún caso, formular
  hipótesis con intención de preparar o justificar una acción futura
  sobre ellos, ni proponer ninguna vía hacia esa acción en este
  feature.
- **FR-013a**: El sistema NO DEBE ejecutar ni proponer ninguna acción
  correctiva sobre un contenedor de la lista de críticos
  (`homeassistant`, `vaultwarden`, `nextcloud*`, `immich*`,
  `pangolin-server`, `gerbil`, `traefik`) — la misma lista y el mismo
  criterio "requiere aprobación explícita de Miquel" ya vigentes en
  `docker_monitor.py` y en `SOUL.md` de Bautista, confirmados sin
  cambios el 2026-08-10.
- **FR-014**: El sistema NO DEBE indexar ni consultar un histórico de
  resoluciones previas (RAG) — cada diagnóstico parte de la evidencia
  del episodio actual, sin memoria de episodios anteriores en esta
  fase.
- **FR-015**: El sistema NO DEBE diagnosticar ningún episodio por su
  cuenta — cada diagnóstico se dispara únicamente cuando Miquel elige
  explícitamente qué episodio de contenedor diagnosticar (en vivo o
  histórico). El sistema NO DEBE vigilar la Central de Alarmas ni
  `restart_history` para lanzarse solo.

### Key Entities

- **Episodio**: unidad de trabajo del agente — una caída o reinicio
  real de un contenedor, en vivo o histórico, sobre el que hay que
  diagnosticar una causa (alcance de este feature: solo contenedores,
  ver Clarifications). Atributos relevantes: contenedor afectado,
  ventana de tiempo, si es en vivo o en diferido, y el snapshot de
  evidencia congelado en el momento de elegir diagnosticarlo (FR-002)
  — es ese snapshot, no el estado en vivo del homelab, lo que se vuelve
  a usar si se repite el diagnóstico.
- **Hipótesis**: una causa probable propuesta para un episodio.
  Atributos relevantes: descripción de la causa, cómo se comprobó
  contra la evidencia, y su desenlace (confirmada / descartada / sin
  evidencia suficiente).
- **Diagnóstico**: el resultado final de procesar un episodio.
  Atributos relevantes: el episodio al que corresponde, la lista de
  hipótesis consideradas, y la conclusión (causa probable con
  evidencia, o "no se puede diagnosticar").
- **Gasto diario de DeepSeek**: acumulado de coste real en tokens
  consumidos, por día natural. Atributos relevantes: fecha, coste
  acumulado, límite configurado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ejecutar el agente dos veces contra el mismo episodio
  (histórico, o un snapshot ya congelado de uno en vivo) produce el
  mismo `conclusion_tipo` (causa_probable / no_diagnosticable) las dos
  veces, el 100% de las veces que se prueba. No exige que el número o
  el texto de las hipótesis intermedias coincida entre las dos
  ejecuciones (aclarado el 2026-08-11 tras `/speckit-analyze`, hallazgo
  I1 — ver Edge Cases).
- **SC-002**: De los 6 episodios históricos de referencia de `beszel`
  fijados en FR-011 (`restart_history_id` 4, 16, 17, 25, 79, 81), el
  agente concluye `no_diagnosticable` en los 3 sin evidencia de
  métricas (16, 17, 25) — no inventa una causa donde no hay datos que
  la respalden (corregido el 2026-08-11, hallazgo U2 — ver FR-011 para
  el porqué de este conjunto concreto en vez de "los 5 investigados a
  mano").
- **SC-003**: El 100% de los diagnósticos producidos incluyen más de
  una hipótesis registrada con su comprobación, salvo que la evidencia
  disponible sea tan escasa que no permita formular más de una.
- **SC-004**: El gasto real en DeepSeek nunca supera el límite diario
  configurado, verificable revisando el acumulado de cualquier día
  contra ese límite.
- **SC-005**: Ningún diagnóstico producido por el agente incluye una
  acción ejecutada ni una remediación nueva sugerida — el 100% son de
  solo diagnóstico.

## Assumptions

- El límite de gasto diario de DeepSeek es un valor configurable; la
  cifra de partida que maneja Miquel es 5 €/día, pero el número exacto
  y su mecanismo de configuración se fijan en el plan, no en este
  documento.
- La fuente de "evidencia real" para un episodio (qué métricas, logs o
  estados se reúnen exactamente) depende del tipo de episodio y se
  detalla en el plan — este documento solo exige que sea evidencia real
  del homelab, no que se enumere aquí cada fuente posible.
- El caso de beszel se usa para validar el mecanismo, no como objetivo
  de encontrar su causa raíz — coherente con el alcance ya fijado en
  `BRIEFING.md` (Caso 1) desde antes de este feature.
- La superficie visible de un diagnóstico (dónde se lee, si aparece en
  el dashboard o solo por Telegram) queda fuera de este feature — se
  decide en uno posterior, una vez que haya diagnósticos reales que
  mostrar.
- El RAG sobre resoluciones pasadas, y la lista cerrada de acciones
  reversibles con su ejecución, quedan explícitamente fuera de este
  feature para features posteriores (`BRIEFING.md`, "Feature 007 —
  material de partida").
- Los datos de un episodio que salen de la máquina hacia la API de
  DeepSeek son evidencia de diagnóstico (métricas, logs, estado de
  componentes) — nunca credenciales ni datos de seguridad física,
  coherente con el resto del proyecto.
