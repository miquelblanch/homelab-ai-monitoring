# Feature Specification: Reinicio de Agentes y Relays (LaunchAgents/LaunchDaemons)

**Feature Branch**: `026-reiniciar-agentes-relays`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "Miquel quiere ampliar la lista cerrada de acciones reversibles de remediación con una acción nueva, `reiniciar_agente`, aplicada a los LaunchAgents de usuario (`amsterdam9.*`, incluidos los que vigilan al propio sistema de monitorización) y a los LaunchDaemons root de los relays de Home Assistant (`com.homeassistant.*`, con permiso `sudo` acotado al comando exacto vía `sudoers`, nunca una contraseña compartida) — mismo patrón exacto que `reiniciar_contenedor` (021): reunir evidencia real (reutilizando el origen `agente` del motor de diagnóstico, feature 016), preguntar a DeepSeek si la acción aplica, y ejecutar o proponer según el interruptor manual/automático vigente por tipo de acción, con cortacircuito si falla repetidamente. Además, conectar el hallazgo `Beszel (hub)` del inventario (categoría `infra_monitorizacion`) a la acción `reiniciar_contenedor` que ya existe para el contenedor `beszel`, en vez de aparecer sin ninguna remediación real cuando en realidad sí la tiene. No incluye los jobs de Hermes (`cron: *`, se reinician con `hermes cron run`, mecanismo distinto) ni el reinicio de `host_externo` por SSH (bloqueado hoy por no tener aún la credencial/usuario correcto de la Raspberry Pi) — ambos quedan fuera, documentados como casuística aparte para features futuras. Tampoco incluye ninguna acción sobre entidades de Home Assistant individuales, ni sobre los 3 enchufes inteligentes Tapo P115 (uno de ellos controla la alimentación del propio Mac Mini que ejecuta el homelab) — exclusión explícita y permanente, no solo ausencia. Investigación previa completa en `BRIEFING.md` (sección Feature 026) y `CASUISTICA-026-acciones-reversibles.md`."

## Clarifications

### Session 2026-08-16

- Q: ¿El cortacircuito de `reiniciar_agente` (FR-009) y el aviso por
  fallo persistente al decidir (FR-014) reutilizan el mismo umbral ya
  establecido para contenedores (3 intentos en 6 horas), o esta acción
  necesita su propio umbral independiente? → A: Opción A — mismo
  umbral compartido, 3 intentos en 6 horas, sin configuración nueva.
- Q: ¿Sigue siendo una única acción cerrada (reiniciar, con "ninguna
  acción aplica" como conclusión legítima de DeepSeek), o se añade una
  segunda acción concreta distinta de reiniciar para un agente caído?
  → A: Una sola acción — reiniciar o nada. Mismo patrón exacto que
  `reiniciar_contenedor` (021); el nombre `reiniciar_agente` describe
  la acción en sí, no el proceso completo — el proceso siempre
  diagnostica primero (FR-002 reforzado para dejarlo explícito). No se
  diseña ninguna acción nueva en esta feature.
- Q: Si el permiso `sudoers` para `com.homeassistant.*` todavía no
  está instalado, ¿Remediaciones muestra esos relays igual que el
  resto (`IA` sin más), o distingue que están bloqueados? → A:
  Distinguir el bloqueo — Remediaciones NO DEBE mostrar como
  ejecutable algo que fallaría por falta de permiso (FR-023,
  Principio XII).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reiniciar un LaunchAgent de usuario caído (Priority: P1)

Miquel quiere que, cuando uno de los ~32 LaunchAgents de usuario que
ejecutan la automatización del homelab (`amsterdam9.*`) deje de tener
un proceso activo, el sistema reúna evidencia real, le pregunte a
DeepSeek si un reinicio tiene sentido, y actúe o proponga según el
interruptor manual/automático vigente para esa acción — en vez de que
el único aviso sea un texto que Miquel tiene que traducir él mismo en
`launchctl kickstart`.

**Why this priority**: Es la pieza central del feature — sin ella no
hay ninguna acción real nueva, solo diagnóstico. Cubre el grupo más
amplio (32 de 43 agentes candidatos) sin necesitar ningún permiso
especial.

**Independent Test**: Puede probarse por completo simulando un
LaunchAgent `amsterdam9.*` sin proceso activo y comprobando que el
sistema genera una evaluación de DeepSeek y, según el modo vigente,
ejecuta el reinicio o deja una propuesta pendiente de aprobación — sin
tocar ningún LaunchDaemon root ni ningún contenedor.

**Acceptance Scenarios**:

1. **Given** un LaunchAgent `amsterdam9.*` sin proceso activo y modo
   automático, **When** el ciclo de comprobación se ejecuta, **Then**
   el sistema reúne evidencia real, DeepSeek evalúa el caso, y si
   recomienda `reiniciar_agente` el sistema lo ejecuta y verifica que
   el proceso vuelve a estar activo antes de marcarlo como éxito.
2. **Given** el mismo caso en modo manual, **When** el ciclo se
   ejecuta, **Then** queda una propuesta pendiente de aprobación
   explícita de Miquel, sin ejecutar nada todavía.
3. **Given** un LaunchAgent que ya acumula el número configurado de
   intentos fallidos en la ventana vigente, **When** vuelve a
   detectarse caído, **Then** el sistema no vuelve a intentar
   reiniciarlo — avisa del cortacircuito en vez de repetir la acción.

---

### User Story 2 - Reiniciar un relay HA gestionado por un LaunchDaemon root (Priority: P2)

Miquel quiere que los 11 relays de Home Assistant que corren como
LaunchDaemon root (`com.homeassistant.*`) reciban el mismo tratamiento
que los LaunchAgents de usuario, sin que eso signifique dar acceso de
`sudo` genérico al sistema de remediación — solo permiso para el
comando exacto de reinicio de cada relay conocido.

**Why this priority**: Mismo valor que la User Story 1, pero depende
de una pieza de despliegue fuera del código (`sudoers`) que la User
Story 1 no necesita — puede entregarse después sin bloquear la pieza
principal.

**Independent Test**: Puede probarse igual que la User Story 1, pero
apuntando a un `com.homeassistant.*` — solo requiere que el permiso
`sudoers` acotado esté instalado en la máquina de pruebas.

**Acceptance Scenarios**:

1. **Given** un LaunchDaemon `com.homeassistant.*` sin proceso activo
   y modo automático, **When** el ciclo se ejecuta, **Then** el
   sistema ejecuta el reinicio con el comando exacto autorizado por
   `sudoers` y verifica el resultado, igual que con un LaunchAgent de
   usuario.
2. **Given** el permiso `sudoers` no está instalado en la máquina
   (por ejemplo, un despliegue nuevo), **When** el sistema intenta
   ejecutar el reinicio, **Then** el intento queda registrado como
   fallido con el motivo real (permiso denegado), nunca como si
   ninguna acción aplicara al caso.

---

### User Story 3 - Cablear el hallazgo "Beszel (hub)" a la acción ya existente (Priority: P3)

Miquel quiere que, cuando el inventario reporte que el hub de Beszel
no está haciendo bien su trabajo de vigilar los tres sistemas a su
cargo, esa alarma quede conectada a la acción `reiniciar_contenedor`
que ya existe para el contenedor `beszel` — en vez de aparecer como
"sin remediación real" cuando la solución ya está construida, solo sin
cablear.

**Why this priority**: Es un cableado sobre algo que ya funciona, no
una construcción nueva — bajo esfuerzo y bajo riesgo, pero no bloquea
a las otras dos historias.

**Independent Test**: Puede probarse comprobando que una alarma sobre
"Beszel (hub)" muestra el mismo estado de remediación (pendiente/
ejecutado/rechazado/cortacircuito) que ya se muestra hoy para el
contenedor `beszel`, sin haber creado ninguna acción ni tabla nueva.

**Acceptance Scenarios**:

1. **Given** el hallazgo "Beszel (hub)" activo en el inventario,
   **When** Miquel lo consulta, **Then** ve el estado real del
   intento de remediación vigente del contenedor `beszel`, no un
   "sin acción disponible".

---

### User Story 4 - Ver en "Remediaciones" qué es arreglable y cómo (Priority: P4)

Miquel quiere una pestaña nueva del dashboard, "Remediaciones",
distinta de "Inventario", que muestre solo los componentes que de
verdad tienen una acción de remediación real hoy (clasificación
`automática` o `IA`, nunca `manual`) junto con la acción concreta que
les corresponde (`rotar_log` / `reiniciar_contenedor` /
`reiniciar_agente`) — sin tener que filtrar a mano la tabla completa
de Inventario, donde la inmensa mayoría de los 792 componentes
(sobre todo `entidad_ha`) no tiene ninguna acción posible.

**Why this priority**: Es la superficie de visibilidad para todo lo
que este feature, junto con 019/021/022, ya construyó — sin ella,
saber "qué es arreglable y cómo" exige leer código o filtrar
manualmente una tabla de 792 filas.

**Independent Test**: Puede probarse comprobando que la pestaña
muestra únicamente los componentes con clasificación distinta de
`manual`, cada uno con su acción real asociada, sin depender de que
ningún intento se haya ejecutado todavía ni de tocar Inventario.

**Acceptance Scenarios**:

1. **Given** el inventario con su clasificación vigente (022, ampliada
   por este feature), **When** Miquel abre Remediaciones, **Then** ve
   solo los componentes con acción real, cada uno con la acción
   concreta que le aplica.
2. **Given** un componente que pasa de `manual` a `IA` (por ejemplo, un
   LaunchAgent nuevo reconocido por esta feature), **When** se
   actualiza el inventario, **Then** aparece en Remediaciones sin
   ninguna intervención manual — es una proyección calculada, no una
   lista mantenida aparte.
3. **Given** un componente sin ninguna acción real (por ejemplo, una
   entidad de Home Assistant), **When** Miquel abre Remediaciones,
   **Then** no aparece — de solo lectura, sin ningún control que
   ejecute, apruebe, rechace o cambie el modo, mismo criterio que
   Inventario y Alarmas (022).

---

### User Story 5 - Ver en "Correcciones" el ciclo completo de un intento, no solo cuando la alarma se resuelve (Priority: P5)

Miquel quiere que "Correcciones" deje de limitarse a "la alarma ya no
está" (su alcance desde 2026-08-10) y muestre también los intentos de
remediación que no llegaron a resolver nada — pendientes de
aprobación, rechazados, fallidos, o parados por cortacircuito — para
cualquier tipo de acción (logs, contenedores, y los agentes que añade
este feature), no solo los que sí funcionaron.

**Why this priority**: Amplía algo que ya está en producción y ya es
útil — no bloquea el resto del feature, pero cierra un hueco real de
precisión del dashboard (Principio XII): hoy un intento rechazado o
fallido sobre una alarma que sigue activa es invisible en Correcciones
hasta que esa alarma desaparece por otro motivo.

**Independent Test**: Puede probarse forzando un intento rechazado,
fallido o parado por cortacircuito sobre una alarma que sigue activa,
y comprobando que aparece en Correcciones con su estado real, sin
esperar a que la alarma se resuelva.

**Acceptance Scenarios**:

1. **Given** un intento de remediación pendiente de aprobación sobre
   una alarma activa, **When** Miquel abre Correcciones, **Then** lo
   ve con su estado real ("pendiente"), no solo una vez resuelta.
2. **Given** un intento rechazado o fallido, **When** Miquel abre
   Correcciones, **Then** lo ve reflejado con ese desenlace, incluso
   si la alarma original sigue activa.
3. **Given** una alarma que se resuelve sin ningún intento de
   remediación de por medio (declarada a mano, o resuelta sola),
   **When** se resuelve, **Then** Correcciones la sigue mostrando
   exactamente como hoy — esta ampliación no cambia ningún
   comportamiento ya existente.

---

### Edge Cases

- ¿Qué pasa si el label de un LaunchAgent/LaunchDaemon caído no está
  en la lista de 43 candidatos reconocidos (renombrado, eliminado, o
  nuevo)? El sistema NO evalúa ni actúa sobre labels desconocidos —
  mismo criterio que un contenedor fuera de la lista de no críticos en
  021.
- ¿Qué pasa si el propio LaunchAgent que ejecuta la remediación
  (`amsterdam9.remediacion.comprobar`/`amsterdam9.remediacion.comprobar-contenedores`)
  está entre los caídos? Se evalúa igual que cualquier otro — decisión
  ya confirmada con Miquel (2026-08-16): sin excepción especial, mismo
  patrón de bajo riesgo que el resto (un reinicio no destruye nada).
- ¿Qué pasa si un reinicio no resuelve el problema (el proceso vuelve
  a caer enseguida)? Queda registrado el intento con su desenlace real;
  no hay reintento inmediato — el siguiente ciclo de comprobación lo
  vuelve a evaluar desde cero, sujeto al mismo cortacircuito que el
  resto de acciones.
- ¿Qué pasa con `Relay: X` (los 10 hallazgos derivados de
  `socat_relays.json` que observan la misma conectividad que ya vigila
  su LaunchAgent/LaunchDaemon por otro camino)? Esta feature no
  resuelve esa duplicidad de identidad — el reinicio actúa sobre el
  proceso real con independencia de si el inventario ya los empareja;
  la brecha de `Relay: X` puede seguir apareciendo aparte hasta que se
  resuelva esa duplicidad en otra feature.
- ¿Qué pasa en Remediaciones si un componente `com.homeassistant.*`
  aparece clasificado `IA` pero el permiso `sudoers` de la User Story 2
  todavía no está instalado en la máquina? Remediaciones DEBE
  distinguirlo — no mostrarlo como si ya funcionara (FR-023).
- ¿Qué pasa en Correcciones si el mismo componente acumula varios
  intentos seguidos (por ejemplo, rechazado y luego, tras otra
  evaluación, ejecutado)? Debe quedar visible la secuencia real, no
  solo el último estado — el detalle exacto de cómo se agrupan o
  listan varios intentos del mismo componente se resuelve en
  `/speckit-plan`, no aquí.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE reunir evidencia real de un LaunchAgent
  o LaunchDaemon que no tiene un proceso activo, reutilizando el mismo
  origen de evidencia que ya construyó el motor de diagnóstico para
  agentes (feature 016) — nunca una copia nueva.
- **FR-002**: El sistema DEBE diagnosticar primero y decidir después:
  preguntar a DeepSeek, con la evidencia real reunida, si la única
  acción cerrada disponible (reiniciar) resuelve el caso — nunca
  reiniciar como respuesta automática al solo hecho de estar caído.
  "Ninguna acción de la lista cerrada aplica" (`sin_accion`) es una
  conclusión legítima y esperada de DeepSeek, no un caso residual —
  mismo patrón exacto que `reiniciar_contenedor` (021), independiente
  de si el motor de diagnóstico (007-018) ha concluido o no una causa
  probable para el mismo episodio.
- **FR-003**: Como ya estableció la feature 016, no existe ningún modo
  diferido para agentes — la evaluación se basa solo en el estado
  actual (proceso activo o no, último código de salida), sin ninguna
  serie histórica que consultar.
- **FR-004**: El sistema DEBE ejecutar el reinicio de un LaunchAgent de
  usuario (`amsterdam9.*`) sin requerir ningún privilegio elevado.
- **FR-005**: El sistema DEBE ejecutar el reinicio de un LaunchDaemon
  root (`com.homeassistant.*`) únicamente a través de un permiso
  acotado al comando exacto de cada relay conocido — nunca con
  credenciales de `sudo` de uso general ni compartidas fuera del
  mecanismo de secretos ya establecido.
- **FR-006**: El sistema DEBE verificar, tras ejecutar un reinicio,
  que el proceso vuelve a estar activo antes de marcarlo como éxito —
  mismo criterio que ya usa `docker_monitor.py` para contenedores
  ("verificado corriendo", no solo que el comando devolviera 0).
- **FR-007**: El sistema NO DEBE prometer ni implementar una operación
  de deshacer para un reinicio ya ejecutado — mismo precedente que
  `reiniciar_contenedor` (021): un reinicio de proceso no tiene vuelta
  atrás literal, solo la garantía de que no deja el agente peor de lo
  que ya estaba.
- **FR-008**: El sistema DEBE reutilizar el interruptor manual/
  automático por tipo de acción ya existente (`configuracion_accion`,
  019) — no crea un mecanismo de interruptor nuevo.
- **FR-009**: Si un LaunchAgent/LaunchDaemon acumula 3 intentos de
  reinicio en una ventana de 6 horas, el sistema DEBE dejar de
  reintentar y avisar por Telegram — cortacircuito, mismo umbral
  compartido que ya usan contenedores y logs, sin configuración nueva
  ni independiente para esta acción.
- **FR-010**: El sistema DEBE contabilizar el coste de las llamadas a
  DeepSeek para esta acción contra el mismo límite de gasto diario
  compartido que ya usan el diagnóstico (007) y la remediación de
  contenedores (021/022) — sin presupuesto aparte.
- **FR-011**: Si no queda presupuesto diario disponible, el sistema NO
  DEBE llamar a DeepSeek para un agente caído — el episodio queda "sin
  evaluar", distinguible de "DeepSeek dijo que ninguna acción aplica".
- **FR-012**: El sistema NO DEBE evaluar ni actuar sobre ningún
  LaunchAgent/LaunchDaemon cuyo label no esté en la lista reconocida
  de candidatos (`amsterdam9.*` o `com.homeassistant.*` ya vistos por
  el inventario) — evita actuar sobre algo desconocido o mal
  identificado.
- **FR-013**: `amsterdam9.health` (o el mecanismo que vigile y avise
  del estado de los LaunchAgents hoy) sigue siendo, sin ningún cambio,
  el único mecanismo de vigilancia y aviso de agentes caídos — esta
  feature solo añade la capa de decidir y actuar, igual que 021 hizo
  para `docker_monitor.py` y contenedores (Principio VII).
- **FR-014**: Un fallo persistente de esta feature para evaluar o
  actuar (sin presupuesto, sin respuesta de DeepSeek, permiso `sudo`
  no instalado) DEBE avisar por Telegram — mismo umbral compartido de
  3 casos consecutivos que ya usa FR-019 de 021, sin un contador
  aparte para agentes — contrapartida no negociable de ceder la
  decisión.
- **FR-015**: El sistema DEBE conectar el hallazgo "Beszel (hub)" del
  inventario (categoría `infra_monitorizacion`) al estado real del
  intento de remediación vigente del contenedor `beszel` — sin crear
  ninguna acción ni tabla nueva, reutilizando `reiniciar_contenedor`
  (021) tal cual.
- **FR-016**: El sistema NO DEBE ofrecer ni ejecutar ninguna acción
  sobre `cron: *` (jobs de Hermes), `host_externo`, ni ninguna entidad
  de Home Assistant individual — quedan fuera de esta feature (ver
  Assumptions).
- **FR-017**: El dashboard DEBE mostrar una pestaña nueva,
  "Remediaciones", distinta de "Inventario" y de "Correcciones", con
  únicamente los componentes cuya clasificación vigente (022, ampliada
  por FR-004/FR-005) sea `automática` o `IA` — nunca `manual` — sin
  mantener ninguna lista aparte de la ya calculada.
- **FR-018**: Para cada componente mostrado en Remediaciones, el
  dashboard DEBE mostrar la acción real que le corresponde
  (`rotar_log` / `reiniciar_contenedor` / `reiniciar_agente`) junto a
  su clasificación vigente.
- **FR-019**: Remediaciones DEBE ser de solo lectura — ningún control
  que ejecute, apruebe, rechace o cambie el modo desde ahí, mismo
  criterio que Inventario y Alarmas (FR-013 de 022).
- **FR-020**: El sistema DEBE ampliar "Correcciones" para mostrar,
  para cualquier intento de remediación (logs, contenedores, y los
  agentes de esta feature), su estado real completo —incluidos
  `pendiente`, `rechazado`, `fallido` y `cortacircuito`— y no
  únicamente cuando la alarma correspondiente ya se resolvió, que es
  su alcance actual desde 2026-08-10.
- **FR-021**: Esta ampliación de Correcciones NO DEBE cambiar el
  comportamiento ya existente para una alarma que se resuelve sin
  ningún intento de remediación de por medio (declarada a mano, o
  resuelta sola) — sigue exactamente igual que hoy.
- **FR-022**: Correcciones DEBE seguir siendo de solo lectura, mismo
  criterio que ya tiene hoy.
- **FR-023**: El sistema DEBE poder determinar si el permiso `sudoers`
  de un `com.homeassistant.*` concreto está instalado y operativo, y
  Remediaciones DEBE reflejar ese estado — un componente clasificado
  `IA` cuya ejecución está bloqueada por falta de permiso NO DEBE
  mostrarse igual que uno cuya acción ya puede ejecutarse de verdad
  (Principio XII, precisión del dashboard).

### Key Entities

- **Configuración de acción por agente**: el modo actual (`manual`/
  `automatico`) de la acción `reiniciar_agente`, reutilizando
  `configuracion_accion` (019) — no una tabla nueva.
- **Evaluación de DeepSeek sobre un agente**: evidencia entregada,
  acción recomendada (o ninguna), razonamiento, coste — mismo concepto
  que la evaluación de contenedores (021), aplicado a un label de
  LaunchAgent/LaunchDaemon en vez de a un nombre de contenedor.
- **Intento de reinicio de agente**: una propuesta o ejecución de
  `reiniciar_agente` — label, la evaluación que lo originó, modo en
  que se creó, estado (`pendiente`/`rechazado`/`ejecutado`/`fallido`/
  `cortacircuito`/`sin_evaluar`). Sin campo de rollback (FR-007).
- **Vista "Remediaciones"**: proyección de solo lectura de los
  componentes de Inventario cuya clasificación vigente es distinta de
  `manual` — no es una entidad persistida aparte, se calcula igual que
  la clasificación de 022, ampliada por esta feature. Para
  `com.homeassistant.*`, la proyección incluye si el permiso `sudoers`
  correspondiente está instalado y operativo (FR-023), no solo la
  clasificación.
- **Corrección** (extiende el concepto ya existente desde 2026-08-10):
  ahora puede representar un intento de remediación en cualquier
  estado del ciclo diagnosticar→decidir→actuar, no solo uno ya
  resuelto — reutiliza los mismos datos de `remediacion.db` que ya usa
  Alarmas (022), sin una fuente nueva.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cuando un agente de la lista reconocida queda sin
  proceso activo, existe una propuesta de reinicio razonada antes de
  que pase el siguiente ciclo de comprobación (5 minutos) — Miquel ya
  no tiene que enterarse por otra vía y traducir el aviso en un
  comando a mano.
- **SC-002**: El 100% de los 43 agentes candidatos (32 de usuario + 11
  LaunchDaemon root) tiene un intento evaluable la primera vez que
  aparece caído durante la vida de esta feature — ninguno queda fuera
  por no estar contemplado.
- **SC-003**: Ningún reinicio de agente se ejecuta sin pasar por el
  interruptor manual/automático vigente para esa acción.
- **SC-004**: El hallazgo "Beszel (hub)" deja de aparecer como "sin
  remediación real" — muestra el mismo estado que ya ve Miquel para el
  contenedor `beszel`.
- **SC-005**: Ningún caso de esta feature requiere que Miquel comparta
  una contraseña de `sudo` de uso general ni una credencial SSH fuera
  del mecanismo de secretos ya establecido en el proyecto.
- **SC-006**: Miquel puede identificar, sin filtrar manualmente los
  792 componentes de Inventario, cuáles tienen de verdad una acción de
  remediación asociada y cuál es.
- **SC-007**: Un intento de remediación rechazado, fallido o parado
  por cortacircuito es visible en Correcciones incluso si la alarma
  original sigue activa — hoy es invisible hasta que esa alarma
  desaparece por otro motivo.
- **SC-008**: Ningún componente `com.homeassistant.*` se muestra en
  Remediaciones como ejecutable de verdad si el permiso `sudoers`
  correspondiente todavía no está instalado — cero casos de "parecía
  automatizado y no lo estaba".

## Assumptions

- El permiso `sudoers` acotado para `com.homeassistant.*` (borrador
  completo en `CASUISTICA-026-acciones-reversibles.md`, un
  `NOPASSWD` por label, sin comodín) se instala como tarea de
  despliegue en la máquina — fuera del propio código de este repo, no
  algo que ejecute esta feature por sí sola.
- Esta feature reutiliza íntegramente la evidencia (016), el modelo de
  coste compartido (007) y el mecanismo de interruptor/cortacircuito
  (019/021) ya construidos — no duplica ninguno.
- `hermes cron run` (jobs de Hermes: `dreaming`, `noticias-ia`,
  `homelab-optimizer-weekly`, `gbrain-weekly-purge`) queda fuera de
  esta feature a propósito — es un mecanismo distinto (la CLI de
  Hermes, no `launchctl`), no la misma acción aplicada a otro target.
  Se aborda en una feature separada.
- El reinicio de `host_externo` (AdGuard en la Raspberry Pi, Uptime
  Kuma) por SSH queda fuera a propósito — Uptime Kuma está confirmado
  en Docker, pero el despliegue de AdGuard en la Pi sigue sin
  confirmar, y no hay todavía una clave SSH autorizada desde este Mac.
  Se aborda en una feature separada una vez resuelto el acceso.
- Los 3 enchufes inteligentes Tapo P115 (`switch.tapo_p115_mac_mini`,
  `switch.tapo_p115_datacenter`, `switch.tapo_p115_mini_pc`) no son
  alcanzados por esta feature en ningún caso — no son `integracion` ni
  LaunchAgent/LaunchDaemon. Se anota aquí solo como recordatorio para
  cualquier feature futura sobre `entidad_ha`: deben excluirse por
  nombre, no por categoría (uno de ellos controla la alimentación del
  Mac Mini que ejecuta todo el homelab).
- La duplicidad de identidad entre `Relay: X` (10 hallazgos derivados
  de `socat_relays.json`) y su LaunchAgent/LaunchDaemon subyacente no
  se resuelve en esta feature — es un problema de modelo de datos del
  inventario, no de la acción de reinicio en sí.
- Ampliar Correcciones (FR-020/FR-021) reutiliza los intentos ya
  existentes en `remediacion.db` para logs (019) y contenedores
  (021/022) — no requiere ningún cambio en esos features, solo en
  cómo el dashboard los lee. Confirmado con Miquel (2026-08-16): esta
  ampliación entra en el alcance de esta feature, no se deja aparte
  como `hermes cron run`/`host_externo`.
- "Remediaciones" (FR-017/FR-018/FR-019) es una vista calculada, no
  una tabla nueva — depende de que la clasificación de 022 ya esté
  ampliada por las User Stories 1 y 2 de esta misma feature para poder
  mostrar agentes, así que no puede entregarse antes que ellas pese a
  su prioridad más baja.
