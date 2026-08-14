# Feature Specification: Clasificación de Remediación en Inventario, con DeepSeek Evaluando también Contenedores Críticos

**Feature Branch**: `022-clasificacion-remediacion`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "La pestaña Inventario del dashboard lista cada componente del homelab (contenedores, entidades de Home Assistant, integraciones, hosts externos, Hermes, Telegram) pero no dice cómo se resolvería una alarma sobre él. Quiero una columna de remediación por componente: manual, automática, o IA. Hoy solo dos tipos de componente tienen de verdad una forma de remediarse sin que yo intervenga a mano: los logs vigilados (una regla fija de tamaño decide, y según el interruptor se ejecuta sola o espera mi aprobación) y los contenedores no críticos (DeepSeek decide si reiniciar ayuda, y según el interruptor se ejecuta solo o espera mi aprobación). Todo lo demás no tiene ninguna acción real definida todavía, así que para esos la columna debe decir \"manual\" — no quiero que este feature invente acciones nuevas para lo que no las tiene, solo que sea honesto sobre lo que hay. Además, cuando salte una alarma de un componente que sí tiene acción real (contenedor o log), quiero que la pestaña Alarmas, además de la explicación de siempre, muestre el estado real de esa remediación — si hay una propuesta pendiente, si ya se ejecutó, si se rechazó — en vez de solo el texto fijo genérico que muestra hoy. No incluye ningún botón nuevo que ejecute nada desde Inventario o Alarmas: para actuar de verdad se sigue usando remediacion.cli o su visor, igual que hoy." Ampliado en la misma sesión, tras iniciar `/speckit-specify`: "no quiero hablar de contenedores críticos solamente — vamos a generalizar a dispositivos críticos o no críticos. Los críticos se tratan todos de manera manual, que quiere decir que el LLM (DeepSeek) analiza y decide pero yo ejecuto. Los no críticos se tratan todos con IA. Las automáticas se ejecutan de manera automática, tanto si son críticas como no críticas."

## Clarifications

### Session 2026-08-14

- Q: Para las categorías sin ninguna acción real hoy (`entidad_ha`, `integracion`,
  `host_externo`, `hermes`, `telegram`), ¿"no críticos = IA" exige diseñar y construir
  una vía de decisión+ejecución autónoma para ellas ahora, o es una regla de política
  para cuando exista una acción real? → A: Regla de política a futuro. Hoy solo se
  aplica donde ya hay una acción real (contenedores). El resto sigue clasificado
  "Manual", sin inventar ninguna acción nueva — no contradice, sino que reafirma, la
  decisión ya tomada al abrir esta sesión (FR-003).
- Q: ¿Qué alcance tiene el eje crítico/no crítico en este feature, dado que solo existe
  definido hoy para contenedores (`docker_monitor.py`, lista de 12)? → A: Solo
  contenedores por ahora. El resto de categorías no usa este eje — no hay lista de
  "entidad HA crítica" ni equivalente, y este feature no la crea.
- Q: Para contenedores críticos, ¿DeepSeek pasa a evaluarlos y proponer una acción
  (nunca ejecutada sola), o siguen totalmente fuera de cualquier evaluación como
  quedó en 021? → A: Sí, DeepSeek también los evalúa y propone — siempre pendiente de
  aprobación explícita de Miquel, sin ningún modo automático posible para un
  contenedor crítico (FR-009, FR-010).
- Q: Extender la evaluación de DeepSeek a críticos choca con el texto literal del
  Principio VII de la versión 2.0.0 de la constitución ("nadie le retira ni le compite
  [a `docker_monitor.py`] esa responsabilidad" para críticos) — ¿cómo se resuelve? →
  A: Enmienda a la constitución (`constitution.md`, v2.0.0 → v2.1.0, MINOR): se añade
  un párrafo a Principio VII que distingue "vigilar y avisar" (sigue siendo solo de
  `docker_monitor.py`, sin cambios) de "analizar y proponer sin ejecutar nunca" (nueva
  responsabilidad de `remediacion`/DeepSeek) — no compiten, así que no hace falta
  acotar de nuevo la garantía de 021, solo añadir la distinción.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver cómo se resolvería una alarma de cualquier componente (Priority: P1)

Miquel abre la pestaña Inventario y ve, junto a cada componente listado
(contenedor, entidad de Home Assistant, integración, host externo,
Hermes, Telegram), una columna de remediación con exactamente uno de
tres valores: Manual, Automática, o IA — sin tener que ir a otra
pestaña ni a la línea de comandos para saber si una alarma sobre ese
componente se resolvería sola, con ayuda de DeepSeek, o depende
enteramente de él.

**Why this priority**: Es el valor mínimo del feature — sin la
columna no hay nada que unificar después con Alarmas, ni nada sobre lo
que construir la evaluación de críticos de la User Story 2.

**Independent Test**: Abrir Inventario y comprobar que el 100% de los
componentes listados trae la columna con uno de los tres valores,
coherente con la configuración y la criticidad reales (nunca una
clasificación inventada o mantenida a mano aparte).

**Acceptance Scenarios**:

1. **Given** un log vigilado con `rotar_log` en modo automático,
   **When** Miquel mira su fila en Inventario, **Then** ve
   "Automática".
2. **Given** un log vigilado con `rotar_log` en modo manual, **When**
   Miquel mira su fila, **Then** ve "Manual".
3. **Given** un contenedor no crítico, **When** Miquel mira su fila,
   **Then** ve "IA" — con independencia de si su modo de ejecución
   vigente (interruptor de 021) es manual o automático; ese matiz se
   ve en Alarmas (User Story 3), no cambia el valor de esta columna.
4. **Given** un contenedor de la lista de críticos, **When** Miquel
   mira su fila, **Then** ve "Manual" — y, si hay una propuesta real
   de DeepSeek pendiente para él (User Story 2), esa propuesta es
   visible en Alarmas, no solo una etiqueta vacía.
5. **Given** el contenedor `NEVER_RESTART` (hoy, `frigate`), **When**
   Miquel mira su fila, **Then** ve "Manual", igual que un crítico,
   pero sin ninguna propuesta de DeepSeek asociada — queda excluido de
   cualquier evaluación, sin cambios respecto a hoy.
6. **Given** un componente de una categoría sin ninguna acción cerrada
   definida (entidad de Home Assistant, integración, host externo,
   Hermes, Telegram), **When** Miquel mira su fila, **Then** ve
   "Manual" — nunca en blanco, nunca "sin clasificar".

---

### User Story 2 - DeepSeek también analiza los contenedores críticos, pero nunca actúa sin aprobación (Priority: P1)

Para un contenedor de la lista de críticos que no está `running and
healthy`, el sistema reúne su evidencia real —igual que ya hace para
los no críticos desde la feature 021— y le pregunta a DeepSeek si
alguna acción de la lista cerrada aplica. La respuesta se registra
como una propuesta pendiente, visible para Miquel. No existe, para un
contenedor crítico, ninguna configuración que la ejecute sola.

**Why this priority**: Es el cambio de mayor riesgo de este feature —
toca los contenedores más sensibles del homelab. Va en P1 porque, sin
esto, la clasificación "Manual" de un contenedor crítico (User Story
1) sería una etiqueta vacía en vez de la propuesta real que Miquel
pidió poder ver y aprobar.

**Independent Test**: Con un contenedor crítico de prueba en una
condición de fondo real, comprobar que DeepSeek lo evalúa y genera una
propuesta pendiente — y que ninguna configuración posible hace que esa
propuesta se ejecute sin una aprobación explícita de Miquel ese mismo
día.

**Acceptance Scenarios**:

1. **Given** un contenedor crítico que no está `running and healthy`,
   **When** el sistema reúne su evidencia y pregunta a DeepSeek,
   **Then** se crea una propuesta pendiente con la recomendación y el
   razonamiento de DeepSeek — mismo mecanismo que ya existe para no
   críticos (021), pero sin ningún modo "automático" disponible para
   este contenedor.
2. **Given** esa propuesta pendiente, **When** Miquel la aprueba
   explícitamente, **Then** se ejecuta el reinicio real, con la misma
   verificación post-reinicio ya acordada (`running` de verdad, no
   solo código de salida).
3. **Given** esa propuesta pendiente, **When** Miquel no la aprueba
   (la rechaza, o simplemente no actúa), **Then** el contenedor no se
   toca — ninguna cuenta atrás ni reintento automático la convierte en
   ejecución por sí sola.
4. **Given** cualquier contenedor de la lista de críticos, **When** se
   consulta o se intenta fijar su configuración, **Then** el sistema
   no permite un modo "automático" para él — ni por configuración
   manual ni por ningún valor por defecto.
5. **Given** el contenedor `NEVER_RESTART` (`frigate`), **When** el
   sistema decide qué contenedores evaluar, **Then** queda excluido de
   cualquier evaluación de DeepSeek — mismo trato que ya tiene hoy,
   sin cambios de este feature.
6. **Given** DeepSeek concluye que ninguna acción de la lista cerrada
   aplica a un contenedor crítico, **When** eso ocurre, **Then** el
   sistema avisa a Miquel con la evidencia y el razonamiento — mismo
   criterio que ya existe para no críticos (021, User Story 4) — no
   silencio.

---

### User Story 3 - Ver en Alarmas el estado real de una remediación en curso (Priority: P2)

Para una alarma activa sobre un componente que sí tiene una acción
real (un contenedor, crítico o no, o un log vigilado), Miquel quiere
ver en la propia pestaña Alarmas, junto a la explicación fija que ya
existe desde la feature 006, el estado real del intento de
remediación vigente si lo hay — pendiente de aprobación, ya ejecutado,
rechazado, sin acción aplicable, o detenido por el cortacircuito — en
vez de tener que abrir el visor de remediación (feature 020) o el CLI
para saberlo.

**Why this priority**: Depende de que existan la clasificación (User
Story 1) y la evaluación de críticos (User Story 2) — solo tiene
sentido mostrar un estado de remediación donde ya se sabe que existe
una. Es la mitad "que actúen en base a ese criterio" del pedido
original.

**Independent Test**: Con un intento de remediación real registrado
(pendiente, ejecutado, rechazado, sin acción, o cortacircuito) para un
contenedor —crítico o no— o un log, abrir Alarmas y comprobar que la
alarma correspondiente muestra ese estado real, no solo el texto fijo
genérico.

**Acceptance Scenarios**:

1. **Given** un contenedor no crítico con un intento de reinicio en
   estado "pendiente" (modo manual, esperando aprobación), **When**
   Miquel ve su alarma en Alarmas, **Then** ve, además de la
   explicación fija de 006, que hay una propuesta pendiente de
   aprobación.
2. **Given** un contenedor crítico con una propuesta de DeepSeek
   pendiente (User Story 2), **When** Miquel ve su alarma en Alarmas,
   **Then** ve esa propuesta y su razonamiento — no solo el aviso
   genérico de "contenedor crítico caído" que ya existe desde 006.
3. **Given** un log vigilado ya rotado automáticamente (intento en
   estado "ejecutado"), **When** su alarma deja de estar activa
   (porque ya se resolvió), **Then** deja de aparecer en Alarmas —
   mismo criterio que cualquier alarma resuelta hoy (Principio XII);
   este feature no añade una vista de remediaciones ya resueltas
   dentro de Alarmas.
4. **Given** un contenedor (crítico o no) donde DeepSeek concluyó que
   ninguna acción de la lista cerrada aplica (intento "sin_accion"),
   **When** Miquel ve su alarma en Alarmas, **Then** ve ese estado
   explícito, no solo el texto fijo genérico de "contenedor caído".
5. **Given** una alarma sobre un componente clasificado como "Manual"
   sin ningún intento de remediación posible (por ejemplo, una
   entidad de Home Assistant), **When** Miquel la ve en Alarmas,
   **Then** el comportamiento es idéntico al de hoy (feature 006) —
   sin ningún cambio.

---

### Edge Cases

- ¿Qué pasa si un contenedor no crítico todavía no tiene fila en
  `configuracion_contenedor` (nunca se evaluó)? Se clasifica igual que
  cualquier componente de su categoría con acción real disponible pero
  sin configuración explícita todavía — ver Assumptions.
- ¿Qué pasa con un componente que en un momento dado tiene más de un
  intento de remediación en su historial? Solo el más reciente y
  vigente (no resuelto, o resuelto muy recientemente) es relevante
  para lo que se muestra en Alarmas — mismo criterio de "vigente" que
  ya usan 019/021 para decidir si crear un intento nuevo.
- ¿Qué pasa si el propio origen de datos de remediación
  (`remediacion.db`) no responde o no se puede leer? La columna de
  Inventario y el estado en Alarmas deben indicarlo explícitamente
  (p. ej. "sin datos de remediación") en vez de mostrar un valor por
  defecto que parezca una clasificación real — mismo criterio que el
  resto del dashboard ante un origen sin datos (Principio II).
- ¿Qué pasa si DeepSeek recomienda una acción para un contenedor
  crítico y pasan días sin que Miquel la apruebe ni la rechace? Sigue
  pendiente indefinidamente — nada la convierte en ejecución por el
  simple paso del tiempo.
- ¿Qué pasa con el gasto de DeepSeek al añadir los 12 contenedores
  críticos a la población evaluada? Cuenta contra el mismo límite de
  gasto diario compartido que ya usan el diagnóstico (007) y la
  remediación de no críticos (021) — no se crea un límite aparte para
  críticos.
- ¿Qué pasa con categorías o componentes nuevos que se añadan al
  homelab después de este feature? Heredan "Manual" hasta que un
  feature posterior les defina una acción real — coherente con el
  Principio XIII.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mostrar, en la pestaña Inventario, para
  cada componente listado, una columna de clasificación de
  remediación con exactamente uno de tres valores: Manual, Automática,
  o IA.
- **FR-002**: La clasificación DEBE derivarse de la configuración de
  remediación y de la criticidad reales ya existentes
  (`configuracion_accion` para `rotar_log`, `configuracion_contenedor`
  y la lista de críticos/`NEVER_RESTART` de `docker_monitor.py` para
  contenedores) — el sistema NO DEBE mantener una clasificación nueva
  por componente de forma independiente a esas fuentes.
- **FR-003**: Los componentes de una categoría sin ninguna acción
  cerrada de remediación definida hoy (`entidad_ha`, `integracion`,
  `host_externo`, `hermes`, `telegram`) DEBEN clasificarse como
  Manual. El sistema NO DEBE diseñar, definir ni exponer ninguna
  acción de remediación nueva para esas categorías — este feature
  documenta lo que ya existe, no amplía la lista cerrada de acciones
  reversibles (Principios V/VI).
- **FR-004**: Un contenedor no crítico DEBE clasificarse como IA, con
  independencia de si su modo de ejecución vigente (interruptor de la
  feature 021) es manual o automático — la columna refleja quién
  decide (siempre DeepSeek), no quién aprueba la ejecución.
- **FR-005**: Un log vigilado DEBE clasificarse como Automática cuando
  el modo vigente de `rotar_log` es automático, y como Manual cuando
  es manual — el eje crítico/no crítico no aplica a los logs.
- **FR-006**: Un contenedor de la lista de críticos DEBE clasificarse
  como Manual. Esta etiqueta no implica ausencia de análisis: si
  existe una propuesta de DeepSeek pendiente para él (FR-009), esa
  propuesta DEBE ser visible en Alarmas (FR-011) — la etiqueta indica
  que la ejecución exige siempre aprobación explícita, no que nadie lo
  haya evaluado.
- **FR-007**: El contenedor `NEVER_RESTART` (hoy, `frigate`) DEBE
  clasificarse como Manual y quedar excluido de cualquier evaluación
  de DeepSeek — mismo trato que ya tiene hoy; este feature no lo
  cambia.
- **FR-008**: El sistema NO DEBE, bajo ninguna configuración, modo ni
  comportamiento por defecto, ejecutar sobre un contenedor crítico
  ninguna acción de la lista cerrada sin la aprobación explícita de
  Miquel ese mismo día — no existe, para un contenedor crítico, ningún
  modo "automático" (Principio VII).
- **FR-009**: Para un contenedor de la lista de críticos que no está
  `running and healthy`, el sistema DEBE reunir su evidencia real
  (mismo mecanismo ya construido en la feature 021 para no críticos) y
  preguntar a DeepSeek si alguna acción de la lista cerrada aplica.
- **FR-010**: Toda propuesta de DeepSeek sobre un contenedor crítico
  DEBE registrarse en estado pendiente de aprobación — nunca en un
  estado que implique ejecución sin intervención humana. Cuando
  DeepSeek concluye que ninguna acción aplica, el sistema DEBE avisar
  a Miquel con la evidencia y el razonamiento (mismo criterio que 021,
  User Story 4), no quedarse en silencio.
- **FR-011**: Para una alarma activa sobre un componente con un
  intento de remediación vigente en `remediacion.db` (contenedor
  crítico o no crítico, o log vigilado), la pestaña Alarmas DEBE
  mostrar el estado real de ese intento (pendiente, ejecutado,
  rechazado, sin acción aplicable, o detenido por cortacircuito),
  además de la explicación fija ya establecida por la feature 006 —
  nunca en sustitución de ella.
- **FR-012**: Para una alarma sobre un componente sin ningún intento
  de remediación vigente (incluida cualquier alarma sobre un
  componente clasificado como Manual sin acción real, o sobre
  `NEVER_RESTART`), la pestaña Alarmas NO DEBE cambiar su
  comportamiento respecto al ya establecido por la feature 006.
- **FR-013**: Ni la pestaña Inventario ni la pestaña Alarmas DEBEN
  ofrecer ningún control que ejecute, apruebe, rechace o modifique una
  acción de remediación — ambas permanecen de solo lectura; actuar de
  verdad sigue pasando exclusivamente por `remediacion.cli` o su
  visor (feature 020).
- **FR-014**: El sistema NO DEBE calcular ninguna condición de alarma
  nueva ni ninguna fuente de datos nueva — reutiliza únicamente las
  señales y la configuración de remediación que ya producen las
  features 006, 019, 020 y 021, ampliadas por FR-009/FR-010 a la
  población de contenedores críticos.
- **FR-015**: El coste de las llamadas a DeepSeek para evaluar
  contenedores críticos DEBE contabilizarse contra el mismo límite de
  gasto diario compartido que ya usan el diagnóstico (007) y la
  remediación de contenedores no críticos (021) — el sistema NO DEBE
  crear un límite de gasto aparte para críticos.

### Key Entities

- **Clasificación de remediación**: valor derivado (Manual /
  Automática / IA) asociado a un componente del inventario, calculado
  en el momento de mostrarse a partir de la configuración de
  remediación y la criticidad reales vigentes para ese componente (o
  su ausencia) — no es un dato persistido de forma independiente.
- **Propuesta de remediación para contenedor crítico**: evaluación de
  DeepSeek sobre un contenedor crítico caído, con su recomendación y
  razonamiento — extiende el mismo concepto ya definido en 021 para no
  críticos (`intento de reinicio`), pero sin ningún camino posible
  hacia una ejecución sin aprobación explícita.
- **Intento de remediación vigente**: el intento más reciente y no
  superseded de `remediacion.db` (`intentos_remediacion` para logs,
  `intentos_reinicio` para contenedores, ya definidos en 019/021, y
  ampliado por este feature a los contenedores críticos) para un
  componente concreto — reutilizado, no redefinido por este feature,
  para alimentar el estado que se muestra en Alarmas (User Story 3).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Miquel puede determinar, para cualquier componente
  visible en Inventario, cómo se resolvería una alarma sobre él
  (Manual / Automática / IA) sin salir de esa pestaña.
- **SC-002**: El 100% de los componentes listados en Inventario
  muestra uno de los tres valores de clasificación — ninguno queda en
  blanco o sin clasificar.
- **SC-003**: Para el 100% de las alarmas activas sobre un componente
  con un intento de remediación vigente —incluidos los contenedores
  críticos—, Miquel puede ver su estado real sin abrir el visor de
  remediación (020) ni el CLI.
- **SC-004**: Cero acciones de remediación nuevas, y cero controles de
  ejecución nuevos, se añaden como resultado de este feature — el
  número de acciones en la lista cerrada (Principio V) permanece en
  dos (`rotar_log`, `reiniciar_contenedor`) al cerrar el feature; lo
  que cambia es la población de contenedores evaluada, no el catálogo
  de acciones.
- **SC-005**: El 100% de las propuestas de remediación sobre un
  contenedor crítico requiere la aprobación explícita de Miquel antes
  de ejecutarse — verificable por diseño, ya que no existe ninguna
  configuración que permita un modo "automático" para un contenedor de
  la lista de críticos (FR-008).

## Assumptions

- No se añade ninguna acción de remediación nueva ni ninguna fuente de
  datos nueva — se reutiliza exclusivamente lo que ya calculan y
  persisten las features 006 (Alarmas), 019 (`rotar_log`), 020 (visor)
  y 021 (`reiniciar_contenedor`), y se amplía la población de
  contenedores que 021 evalúa para incluir también a los críticos.
- Un componente con acción real disponible pero sin fila de
  configuración explícita todavía (por ejemplo, un contenedor no
  crítico nunca evaluado por `remediacion`) se trata con el mismo
  valor por defecto que ya usa el sistema existente para ese caso
  (`configuracion_contenedor`/`configuracion_accion` ya crean la fila
  en modo manual por defecto la primera vez que se necesita — 019,
  021) — no hace falta un estado "pendiente de configurar" adicional.
- Enviar la evidencia de un contenedor crítico a la API de DeepSeek
  exige la misma justificación explícita por el Principio X (Local por
  Defecto) que ya se aceptó para el diagnóstico (007) y la remediación
  de no críticos (021) — mismo proveedor, mismo principio de
  justificación ya aceptado, ahora extendido a la población de
  críticos.
- El eje crítico/no crítico queda limitado a la categoría `contenedor`
  en este feature — no se define ninguna noción de "crítico" para
  `entidad_ha`, `integracion`, `host_externo`, `hermes` ni `telegram`;
  esas categorías siguen su propia regla (FR-003), sin este eje.
- La enmienda a `constitution.md` (Principio VII, v2.0.0 → v2.1.0)
  que permite esta extensión ya se ha redactado y ratificado como
  parte de la preparación de este spec — no queda pendiente para
  `/speckit-plan`.
- El repositorio es público (ver "Repositorio público" en
  `BRIEFING.md`): ni esta especificación ni el contenido mostrado
  deben incluir IPs, credenciales, ni nombres de entidades ligadas a
  dispositivos de seguridad física — solo software y tipos de
  componente, mismo criterio que el resto del proyecto.
