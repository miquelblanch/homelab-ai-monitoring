# Feature Specification: Remediación Asistida por DeepSeek — Contenedores

**Feature Branch**: `021-remediacion-contenedores`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "No es exactamente lo que quiero. Lo que realmente tiene que tener la fase de remediación es la capacidad de remediar, de reparar, de arreglar cosas. No sé si la solución pasa por reiniciar un contenedor o no; eso lo tiene que valorar el cerebro que estamos construyendo a base de las alarmas, los logs almacenados y toda la info de que disponga. Si es necesario que DeepSeek lo analice todo y dé solución. Entonces, en base al tipo de alarma, analiza la info, analiza logs y que DeepSeek aporte e implemente una solución. Quiero que para ciertos sistemas no críticos, sea totalmente autónomo." Reemplaza el planteamiento anterior de esta misma feature (condición fija "no está `running and healthy`" → reiniciar directamente) por uno donde DeepSeek decide, evidencia en mano, si la acción existente (`reiniciar_contenedor`) aplica a cada caso concreto — nunca inventa una acción nueva, solo elige dentro de la lista cerrada ya aprobada (Principios V/VI, confirmado explícitamente con Miquel tras el giro de planteamiento).

## Clarifications

### Session 2026-08-14

- **Q: `/speckit-analyze` detectó que FR-017 (`docker_monitor.py` deja de
  decidir reinicios de no críticos) entra en conflicto con el Principio VII
  de la constitución tal y como estaba redactado entonces ("la remediación
  automática existente DEBE seguir funcionando con independencia del estado
  del agente", sin excepción) — si `remediacion`/DeepSeek no está disponible
  (sin presupuesto, sin respuesta), los 26 no críticos dejarían de
  auto-repararse, sin que nada lo distinga de "sigue vigilado". ¿Cómo se
  resuelve?
  Why it matters: es un conflicto real con un principio existente, no una
  ambigüedad de redacción — proceder sin resolverlo dejaría la constitución
  y el spec diciendo cosas incompatibles.
  A: Se acota el Principio VII a los contenedores críticos (confirmado con
  Miquel, `AskUserQuestion`, constitution.md v2.0.0) — para esos, la
  independencia de `docker_monitor.py` sigue siendo absoluta y sin cambios.
  Para los no críticos, la cesión de responsabilidad a `remediacion` se
  acepta explícitamente — es, literalmente, lo pedido desde el Input de este
  spec ("docker-monitor no tiene que hacer nada", "que las reparaciones
  siempre las haga deepseek") — con una contrapartida no negociable: un
  aviso cuando la nueva capa lleve varias evaluaciones seguidas sin poder
  decidir (FR-019, nueva en esta sesión) — nunca un silencio que parezca
  vigilancia cuando ya no la hay.

### Session 2026-08-13

- **Q: Cuando DeepSeek decide la solución, ¿elige entre una lista cerrada de acciones ya aprobadas y reversibles, o puede proponer acciones nuevas que el sistema no conocía de antemano?**
  Why it matters: es la diferencia entre extender el modelo de seguridad ya existente y romperlo — ejecutar algo que nadie revisó de antemano es un riesgo mucho mayor sobre un homelab real.
  A: Solo lista cerrada de acciones reversibles (confirmado con Miquel, `AskUserQuestion`) — DeepSeek nunca ejecuta ni propone nada fuera de las acciones ya definidas en código (hoy: `reiniciar_contenedor`). Principios V/VI de la constitución quedan intactos.
- **Q: ¿Para qué orígenes de alarma empieza esta capacidad?**
  Why it matters: el motor de diagnóstico (007-017) ya cubre 10 orígenes, pero la lista cerrada de acciones reversibles hoy solo tiene una aplicable a contenedores (`reiniciar_contenedor`) — para el resto de orígenes no hay nada real entre lo que DeepSeek pudiera elegir.
  A: Solo contenedores por ahora (confirmado con Miquel) — diseñado para ser extensible cuando exista una acción cerrada real para otro origen, sin rehacer el mecanismo.
- **Q: ¿Esta feature depende de que el motor de diagnóstico (007-017) ya haya concluido una `causa_probable` (hoy, 0 de 36 veces), o hace una pregunta distinta y más directa a DeepSeek?**
  Why it matters: atar esta feature a `causa_probable` la dejaría, en la práctica, sin ningún caso real donde actuar — la misma razón por la que 019 (`rotar_log`) evitó depender de DeepSeek del todo.
  A: Pregunta nueva y directa, sin depender de `causa_probable` (confirmado con Miquel) — reutiliza la misma evidencia que ya reúne `src/diagnostico/` para el origen `contenedor` (research.md decide el mecanismo exacto de reutilización), pero le pregunta a DeepSeek algo más concreto: dada esta alarma y esta evidencia, ¿aplica alguna de las acciones ya existentes, y cuál?
- **Q: Para un sistema no crítico en modo autónomo, ¿DeepSeek decide Y ejecuta sin aprobación; y en modo manual, decide pero Miquel aprueba la acción sugerida antes de ejecutarla?**
  Why it matters: define si el interruptor manual/automático ya construido para `reiniciar_contenedor` sigue significando lo mismo una vez DeepSeek entra en la decisión.
  A: Sí, ese mismo reparto (confirmado con Miquel) — modo manual: DeepSeek decide, el sistema propone esa decisión con su razonamiento, Miquel aprueba o rechaza. Modo automático: DeepSeek decide y el sistema ejecuta directo, mismas verificaciones y cortacircuito que ya existían.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - DeepSeek decide si reiniciar es la acción correcta (Priority: P1)

Un contenedor no crítico no está `running and healthy`. En vez de
reiniciarlo por una condición fija, el sistema reúne su evidencia
real (estado, métricas recientes, logs) — la misma que ya reúne
`src/diagnostico/` para este origen — y le pregunta a DeepSeek si,
con esa evidencia, `reiniciar_contenedor` es la acción que aplica.

**Why this priority**: Es el cambio central que pidió Miquel al
interrumpir el planteamiento anterior — sin esto, la feature sigue
siendo la condición fija ya descartada, no lo que realmente se pidió.

**Independent Test**: Se puede probar parando un contenedor de prueba
con una condición de fondo simulada (p. ej. logs que indican que el
problema no es del propio proceso, sino de un recurso externo que un
reinicio no arreglaría) y comprobando que DeepSeek puede recomendar
"no reiniciar", no solo "sí reiniciar".

**Acceptance Scenarios**:

1. **Given** un contenedor no crítico que no está `running and
   healthy`, **When** el sistema reúne su evidencia y pregunta a
   DeepSeek, **Then** DeepSeek responde con una decisión (aplica
   `reiniciar_contenedor`, o ninguna acción de la lista cerrada
   aplica) y su razonamiento, basado en la evidencia real entregada —
   nunca inventa una acción fuera de la lista cerrada.
2. **Given** una evidencia donde reiniciar claramente no ayudaría
   (p. ej. el propio log del contenedor indica que el problema es
   externo, no del proceso), **When** DeepSeek la analiza, **Then**
   puede concluir que ninguna acción de la lista cerrada aplica —
   la decisión no es automáticamente "reiniciar" solo porque el
   contenedor esté caído.
3. **Given** la llamada a DeepSeek, **When** se registra, **Then**
   queda su coste (tokens, EUR) contabilizado contra el mismo límite
   de gasto diario compartido que ya usa `src/diagnostico/` — nunca
   sin límite.

---

### User Story 2 - Modo manual: la decisión de DeepSeek se propone, no se ejecuta sola (Priority: P1)

Con un contenedor en modo manual, la decisión de DeepSeek (aplicar
`reiniciar_contenedor`, con su razonamiento) se registra como
propuesta pendiente — igual que en 019/US1, pero la propuesta ahora
lleva el análisis de DeepSeek, no una condición fija. Miquel aprueba
o rechaza.

**Why this priority**: Es la mitad "manual" del interruptor — sin
esto, no hay forma de que Miquel vea y confirme el razonamiento de
DeepSeek antes de que algo se ejecute sobre un contenedor real.

**Independent Test**: Se puede probar con un contenedor de prueba en
manual, forzando que DeepSeek recomiende reiniciar, y comprobando que
se crea una propuesta pendiente con esa recomendación y su
razonamiento — sin que el contenedor se toque hasta aprobarla.

**Acceptance Scenarios**:

1. **Given** un contenedor en modo manual, **When** DeepSeek
   recomienda `reiniciar_contenedor` para él, **Then** se registra
   una propuesta pendiente con la recomendación y el razonamiento de
   DeepSeek, y el contenedor no se toca todavía.
2. **Given** esa propuesta pendiente, **When** Miquel la aprueba,
   **Then** se ejecuta el reinicio real, con la misma verificación
   post-reinicio ya acordada (running de verdad, no solo código de
   salida).
3. **Given** esa propuesta pendiente, **When** Miquel la rechaza,
   **Then** el contenedor no se toca y queda registrada como
   "rechazado", con el razonamiento de DeepSeek conservado para
   referencia futura.
4. **Given** un contenedor en modo manual, **When** DeepSeek concluye
   que ninguna acción aplica, **Then** no se crea ninguna propuesta de
   `reiniciar_contenedor` — ver User Story 4 para qué pasa con ese
   caso.

---

### User Story 3 - Modo automático: DeepSeek decide y el sistema ejecuta solo (Priority: P1)

Con un contenedor en modo automático, si DeepSeek recomienda
`reiniciar_contenedor`, el sistema lo ejecuta directamente — mismas
verificaciones y protecciones ya acordadas (verificación real
post-reinicio, cortacircuito de 3 intentos en 6 horas).

**Why this priority**: Es la mitad "autónoma" del interruptor — el
pedido explícito de Miquel de que ciertos sistemas no críticos se
reparen solos, ahora con el juicio de DeepSeek de por medio en vez de
una condición ciega.

**Independent Test**: Se puede probar con un contenedor de prueba en
automático, forzando que DeepSeek recomiende reiniciar, y comprobando
que se ejecuta sin ninguna aprobación intermedia, con verificación
real de que quedó `running`.

**Acceptance Scenarios**:

1. **Given** un contenedor en modo automático, **When** DeepSeek
   recomienda `reiniciar_contenedor`, **Then** el sistema lo ejecuta
   de inmediato, verifica que queda `running` de verdad, y registra
   el intento como "ejecutado" con la recomendación de DeepSeek que lo
   originó.
2. **Given** ese mismo contenedor, **When** DeepSeek concluye que
   ninguna acción aplica, **Then** el sistema NO reinicia — el modo
   automático nunca fuerza `reiniciar_contenedor` cuando DeepSeek dice
   que no ayudaría.
3. **Given** 3 intentos fallidos de un mismo contenedor en 6 horas,
   **When** DeepSeek vuelve a recomendar reiniciar, **Then** el
   cortacircuito lo impide igual que si la recomendación fuera una
   condición fija, y avisa por Telegram.

---

### User Story 4 - Ninguna acción aplica: avisar con el análisis, no quedarse callado (Priority: P2)

Cuando DeepSeek concluye que ninguna acción de la lista cerrada
resuelve el problema de un contenedor caído, el sistema avisa a
Miquel con la evidencia y el razonamiento — en vez de no hacer nada
en silencio, o de forzar un reinicio que DeepSeek ya descartó.

**Why this priority**: Es lo que hace que "DeepSeek decide" tenga
valor real más allá de reiniciar — sin esto, un caso donde reiniciar
no ayuda se perdería en silencio, igual que los casos que motivaron
este proyecto desde el principio.

**Independent Test**: Se puede probar forzando una evidencia donde
DeepSeek concluye que ninguna acción aplica, y comprobando que llega
un aviso por Telegram con el razonamiento — no solo silencio.

**Acceptance Scenarios**:

1. **Given** un contenedor caído donde DeepSeek concluye que ninguna
   acción de la lista cerrada aplica, **When** eso ocurre, **Then**
   el sistema envía un aviso por Telegram con la evidencia relevante y
   el razonamiento de DeepSeek — mismo criterio que un contenedor
   crítico caído (aviso, no acción).
2. **Given** ese aviso, **When** se registra, **Then** queda también
   como intento (estado "sin_accion" o equivalente) consultable
   después, no solo como un mensaje efímero de Telegram.

---

### User Story 5 - Cambiar el modo de un contenedor concreto (Priority: P1)

Igual que en el planteamiento anterior: Miquel puede pasar un
contenedor no crítico de manual a automático (o al revés) de forma
individual, sin afectar a los demás.

**Why this priority**: Sigue siendo el control de granularidad que
motivó la feature desde el principio — no cambia con el giro hacia
DeepSeek, solo cambia qué decide el modo automático.

**Independent Test**: Igual que antes — cambiar el modo de un
contenedor de prueba y comprobar que solo afecta a ese contenedor.

**Acceptance Scenarios**:

1. **Given** dos contenedores no críticos, uno en automático y otro en
   manual, **When** los dos generan una recomendación de DeepSeek a
   la vez, **Then** el primero se ejecuta solo y el segundo genera una
   propuesta pendiente — cada uno según su propio modo.
2. **Given** un contenedor concreto, **When** Miquel le cambia el
   modo, **Then** el cambio afecta solo a ese contenedor.

---

### Edge Cases

- ¿Qué pasa si se intenta poner un contenedor crítico (o `frigate`) en
  modo automático, o si DeepSeek "recomendara" reiniciar uno de
  ellos? Se rechaza explícitamente en cualquier caso — la lista
  crítica y `NEVER_RESTART` son un límite que ni siquiera DeepSeek
  puede recomendar cruzar; para esos contenedores, un aviso por
  Telegram (ya acordado) es lo único que ocurre, nunca una propuesta
  ni una ejecución.
- ¿Qué pasa si se agota el límite de gasto diario compartido antes de
  poder preguntar a DeepSeek sobre un contenedor caído? No se
  pregunta — mismo criterio que ya usa `src/diagnostico/` (FR-010 de
  007): sin presupuesto, no hay llamada, y el sistema debe dejar
  constancia de que no se pudo evaluar (no confundir con "DeepSeek
  dijo que no aplica ninguna acción").
- ¿Qué pasa si DeepSeek tarda demasiado, falla, o devuelve algo que no
  se puede interpretar como una decisión válida? Se trata como "no
  se pudo evaluar" — nunca se interpreta un fallo de la llamada como
  "ninguna acción aplica" (evitaría acciones o silencios por un
  problema de la propia llamada, no del contenedor).
- ¿Qué pasa con el resto de responsabilidades de `docker_monitor.py`
  (métricas, discos)? Sin cambios — solo deja de ejecutar su lógica
  de reinicio, igual que en el planteamiento anterior.
- ¿Qué pasa con la reversibilidad de un reinicio decidido por
  DeepSeek? Igual que antes — no hay operación de deshacer para un
  reinicio, decida quien decida que había que hacerlo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE reunir evidencia real de un contenedor
  no crítico que no está `running and healthy` — reutilizando el
  mismo mecanismo de recogida de evidencia que ya usa
  `src/diagnostico/` para el origen `contenedor` (007), no una copia
  nueva.
- **FR-002**: El sistema DEBE preguntar a DeepSeek, con esa evidencia,
  si alguna acción de la lista cerrada de acciones reversibles aplica
  al caso — para esta feature, la única candidata es
  `reiniciar_contenedor`. Esta pregunta es independiente de si el
  motor de diagnóstico (007-017) ha concluido o no una
  `causa_probable` para el mismo episodio.
- **FR-003**: DeepSeek NO DEBE poder recomendar, y el sistema NO DEBE
  poder ejecutar, ninguna acción fuera de la lista cerrada ya
  definida en código — nunca una acción inventada o ad-hoc.
- **FR-004**: El sistema DEBE mantener un modo (`manual` o
  `automatico`) por cada contenedor individual no crítico — mismo
  modelo de granularidad ya acordado, ahora aplicado a la decisión de
  DeepSeek en vez de a una condición fija.
- **FR-005**: Los 26 contenedores no críticos DEBEN empezar en modo
  `automatico` en el momento del corte — mismo criterio ya confirmado
  con Miquel, sin regresión de resiliencia el día del despliegue.
- **FR-006**: El sistema NO DEBE permitir, bajo ninguna circunstancia
  ni modo, que un contenedor de la lista crítica (12) o `frigate`
  (`NEVER_RESTART`) sea reiniciado por este sistema, ni que DeepSeek
  reciba o resuelva una pregunta sobre ellos — para esos, el único
  comportamiento es el aviso por Telegram ya definido.
- **FR-007**: En modo `manual`, cuando DeepSeek recomienda
  `reiniciar_contenedor`, el sistema DEBE registrar una propuesta
  pendiente con esa recomendación y su razonamiento, y NO DEBE
  ejecutar el reinicio hasta que Miquel la apruebe explícitamente.
- **FR-008**: En modo `automatico`, cuando DeepSeek recomienda
  `reiniciar_contenedor`, el sistema DEBE ejecutarlo directamente, sin
  paso de aprobación intermedio.
- **FR-009**: Cuando DeepSeek concluye que ninguna acción de la lista
  cerrada aplica, el sistema NO DEBE reiniciar el contenedor en
  ningún modo, y DEBE enviar un aviso por Telegram con la evidencia
  relevante y el razonamiento de DeepSeek.
- **FR-010**: El sistema DEBE verificar, tras cada reinicio ejecutado,
  que el contenedor está realmente `running` (no solo que el comando
  devolviera éxito) antes de registrarlo como "ejecutado" — mismo
  criterio que ya corrigió `docker_monitor.py` el 2026-07-26.
- **FR-011**: El sistema DEBE detener los reintentos automáticos de un
  contenedor tras 3 intentos fallidos en una ventana de 6 horas
  (cortacircuito), registrar ese intento, y avisar por Telegram —
  sin importar si el intento se originó por una recomendación de
  DeepSeek en vez de una condición fija.
- **FR-012**: El sistema DEBE enviar un aviso por Telegram en estos
  momentos: (a) cortacircuito abierto, (b) contenedor crítico caído
  (sin tocarlo), (c) recuperación tras una caída, (d) DeepSeek
  concluye que ninguna acción aplica (US4). Un reinicio automático
  exitoso sin ninguno de estos casos, o una aprobación manual
  resuelta, no generan aviso adicional.
- **FR-013**: El coste de cada llamada a DeepSeek de esta feature
  (tokens, EUR) DEBE contabilizarse contra el mismo límite de gasto
  diario compartido que ya usa `src/diagnostico/` — nunca un
  presupuesto aparte ni sin límite.
- **FR-014**: Si no queda presupuesto diario disponible, el sistema NO
  DEBE llamar a DeepSeek para un contenedor caído — el episodio queda
  sin evaluar, de forma distinguible de "DeepSeek dijo que ninguna
  acción aplica" (Edge Cases).
- **FR-015**: Un fallo o timeout de la llamada a DeepSeek NO DEBE
  interpretarse como "ninguna acción aplica" ni como "reiniciar" —
  se registra como "no se pudo evaluar", sin ejecutar nada.
- **FR-016**: El sistema NO DEBE prometer ni implementar una operación
  de deshacer para un reinicio ya ejecutado, decida quien decida que
  hacía falta.
- **FR-017**: `docker_monitor.py` NO DEBE ejecutar su propia lógica de
  reinicio de contenedores una vez esta feature está activa — sigue
  ejecutando el resto de sus responsabilidades (métricas, discos) sin
  cambios.
- **FR-018**: El sistema DEBE registrar cada evaluación (con o sin
  acción recomendada), propuesta y ejecución, con su detalle real y
  desenlace, consultable después.
- **FR-019**: Si un contenedor no crítico acumula un número de
  evaluaciones consecutivas en `sin_evaluar` (sin presupuesto, sin
  respuesta de DeepSeek, o respuesta no interpretable — FR-014/FR-015)
  por encima de un umbral configurable, el sistema DEBE avisar por
  Telegram — contrapartida no negociable de ceder a `remediacion` la
  decisión de reinicio que antes tomaba `docker_monitor.py` en
  solitario (Principio VII enmendado, constitution.md v2.0.0). Un
  `sin_evaluar` aislado (uno solo, resuelto en el siguiente ciclo) no
  avisa — solo la persistencia lo hace, mismo criterio de "no ruido
  por un caso puntual" que ya usa el cortacircuito (FR-011).

### Key Entities

- **Configuración de contenedor**: el modo actual
  (`manual`/`automatico`) de un contenedor no crítico concreto.
- **Evaluación de DeepSeek**: el resultado de preguntarle a DeepSeek
  por un contenedor concreto — evidencia entregada, acción
  recomendada (o ninguna), razonamiento, coste (tokens/EUR), momento.
- **Intento de reinicio**: una propuesta o ejecución de
  `reiniciar_contenedor` originada por una evaluación de DeepSeek —
  nombre del contenedor, la evaluación que lo originó, modo en que se
  creó, estado (`pendiente`/`rechazado`/`ejecutado`/`fallido`/
  `cortacircuito`/`sin_evaluar`). Sin campo de rollback (FR-016).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 0% de las evaluaciones o reinicios de este sistema
  ocurre sobre un contenedor de la lista crítica o `frigate`.
- **SC-002**: El 100% de los 26 contenedores no críticos siguen
  auto-reparándose sin intervención manual el mismo día del corte,
  cuando DeepSeek recomienda reiniciar.
- **SC-003**: El 100% de las decisiones de DeepSeek (acción
  recomendada o ninguna) quedan registradas con su razonamiento,
  consultable después sin ambigüedad.
- **SC-004**: El 0% de las llamadas a DeepSeek de esta feature ocurre
  sin presupuesto diario disponible, verificado contra
  `src/diagnostico/gasto.py`.
- **SC-005**: El 100% de los reinicios ejecutados quedan verificados
  contra el estado real del contenedor, nunca solo contra el código
  de salida del comando.
- **SC-006**: El cortacircuito se abre siempre exactamente al tercer
  intento fallido dentro de una ventana de 6 horas, sin importar si el
  intento se originó por una recomendación de DeepSeek.
- **SC-007**: El 100% de las rachas de `sin_evaluar` que superan el
  umbral configurable de FR-019 generan un aviso por Telegram —
  ninguna incapacidad persistente de evaluar un contenedor no crítico
  queda sin avisar, verificado contra `intentos_reinicio`.

## Assumptions

- **Reutiliza la recogida de evidencia de `src/diagnostico/`, no una
  copia nueva** — el origen `contenedor` (007) ya sabe reunir estado,
  métricas y logs de un contenedor; el mecanismo exacto de
  reutilización (llamar a esas funciones directamente, o duplicar
  solo lo mínimo necesario para no crear una dependencia cruzada
  entre paquetes) es una decisión de `/speckit-plan`, no de este spec.
- **Comparte el límite de gasto diario con `src/diagnostico/`, no uno
  propio** — mismo mecanismo (`gasto.py`, `_LIMITE_POR_DEFECTO_EUR`),
  para no poder gastar el doble llamando a DeepSeek desde dos sitios
  distintos del mismo proyecto. El mecanismo exacto de compartir esa
  contabilidad (misma tabla, o una vista agregada) se decide en el
  plan.
- **La pregunta a DeepSeek es nueva y específica de esta feature** —
  no reutiliza el prompt de generación de hipótesis de causa probable
  de `src/diagnostico/` (007-017), que pregunta algo distinto ("por
  qué falló") y rara vez concluye nada (0 de 36 veces). El contenido
  exacto del prompt se decide en el plan.
- **Migración del comportamiento actual, no una capacidad nueva desde
  cero** — igual que en el planteamiento anterior: los 26 contenedores
  no críticos ya se reinician solos hoy, así que empiezan en
  automático para no regresar la resiliencia actual el día del corte.
- **`restart_history` (tabla existente de `metrics_db.py`) no se toca
  por esta feature** — igual que antes, su disposición final (convive
  tal cual, o los nuevos intentos también se reflejan ahí) se decide
  en el plan.
- **La lista de 12 contenedores críticos y `frigate` es exactamente la
  misma que ya usa `docker_monitor.py` hoy** — esta feature no la
  redefine, solo la reutiliza como límite no negociable (FR-006).
- **Sin cambio en el dashboard** — no se pidió; si se quisiera una
  superficie visual de las decisiones de DeepSeek, sería una feature
  separada, mismo patrón que 020 fue aparte de 019.
