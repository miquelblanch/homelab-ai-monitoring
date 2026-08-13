# Feature Specification: Remediación Automática — Primera Pieza (Rotación de Logs)

**Feature Branch**: `019-remediacion-automatica`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "El proyecto tiene diagnóstico cerrado en los 10 orígenes (007-017) pero remediación automática nunca empezó (Principios IV-VIII, Modelo Operacional B). Quiero un sistema de remediación con un interruptor manual/automático por tipo de acción (no por componente individual), que Miquel controla siempre él mismo desde un CLI (sin autopromoción ni barrera de aciertos mínimos, aunque el sistema le enseña el historial de aciertos/fallos de cada tipo al decidir). Por defecto toda acción nueva empieza en modo manual: el sistema propone y espera aprobación explícita antes de ejecutar; en modo automático, ejecuta directamente y registra el resultado para revisión posterior — igual en ambos modos: solo actúa dentro de una lista cerrada de acciones reversibles con rollback escrito (Principios V/VI), nunca sobre un componente crítico. La v1 actúa sobre condiciones deterministas verificables en el momento, sin depender de que el motor DeepSeek (007-017) confirme una causa — hoy ese motor no ha producido nunca un causa_probable real, así que no hay ningún caso contra el que validar esa vía todavía. El único tipo de acción de esta primera feature: rotar (nunca borrar) un log que ha crecido por encima de un umbral sin que nada lo rote — problema real y activo hoy mismo. No incluye ningún otro tipo de acción del barrido de agosto. No incluye notificar por Telegram ni mostrar nada en el dashboard — el CLI es la única superficie."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detectar y proponer, en modo manual por defecto (Priority: P1)

Miquel ejecuta una comprobación y el sistema detecta que un log
vigilado ha crecido por encima de su umbral sin que nada lo rote.
Como el tipo de acción "rotar log" empieza en modo manual, el sistema
registra una propuesta con el detalle exacto (fichero, tamaño,
umbral) y espera su aprobación explícita — no rota nada todavía.

**Why this priority**: Es el comportamiento por defecto y más seguro
— toda acción nueva empieza aquí. Sin esto no hay ninguna base sobre
la que construir el resto.

**Independent Test**: Se puede probar por completo comprobando un log
de prueba por encima del umbral, y verificando que se crea una
propuesta pendiente sin que el fichero cambie.

**Acceptance Scenarios**:

1. **Given** un log vigilado por encima de su umbral de tamaño, **When**
   Miquel ejecuta la comprobación, **Then** el sistema registra una
   propuesta pendiente con el fichero, su tamaño y el umbral, y el
   fichero del log no se toca.
2. **Given** un log vigilado por debajo de su umbral, **When** Miquel
   ejecuta la comprobación, **Then** no se registra ninguna propuesta.
3. **Given** un fichero que no está en la lista de logs vigilados,
   **When** se ejecuta la comprobación, **Then** se ignora — nunca se
   propone una acción sobre algo fuera de la lista cerrada.

---

### User Story 2 - Aprobar o rechazar una propuesta pendiente (Priority: P1)

Miquel revisa las propuestas pendientes y decide, para cada una,
aprobarla (se ejecuta la rotación y se registra el resultado) o
rechazarla (queda registrada como rechazada, el fichero no se toca).

**Why this priority**: Es lo que completa el ciclo de modo manual —
sin esto, una propuesta se queda pendiente para siempre y el sistema
no tiene ningún valor real.

**Independent Test**: Se puede probar aprobando una propuesta de
prueba y comprobando que el log se rota (fichero original vacío,
contenido anterior conservado en el fichero rotado); y rechazando
otra, comprobando que el fichero no cambia.

**Acceptance Scenarios**:

1. **Given** una propuesta pendiente de rotar un log, **When** Miquel
   la aprueba, **Then** el log se rota (el contenido anterior se
   conserva en un fichero nuevo, el original queda vacío) y la
   propuesta pasa a "ejecutado" con la fecha real.
2. **Given** una propuesta pendiente, **When** Miquel la rechaza,
   **Then** el fichero no se toca y la propuesta pasa a "rechazado".
3. **Given** una propuesta ya resuelta (aprobada o rechazada), **When**
   Miquel intenta resolverla otra vez, **Then** el sistema lo rechaza
   sin ejecutar nada dos veces.

---

### User Story 3 - Cambiar el modo de un tipo de acción, con su historial visible (Priority: P1)

Miquel quiere poder pasar "rotar log" de manual a automático (y
viceversa) desde el CLI, viendo antes cuántas propuestas de ese tipo
se aprobaron y cuántas se rechazaron — la decisión es siempre suya,
el sistema nunca cambia el modo por su cuenta.

**Why this priority**: Es el pedido original de esta feature — sin
esto, todo lo demás es remediación de un único modo fijo, no el
sistema de confianza gradual que se pidió.

**Independent Test**: Se puede probar cambiando el modo de "rotar
log" a automático, comprobando que una comprobación posterior ejecuta
directamente sin crear una propuesta pendiente, y volviendo a manual
para comprobar que vuelve a proponer.

**Acceptance Scenarios**:

1. **Given** el tipo de acción "rotar log" en modo manual (su valor
   por defecto), **When** Miquel pide ver su historial, **Then** ve el
   recuento de aprobadas, rechazadas y fallidas hasta ese momento.
2. **Given** ese historial visible, **When** Miquel decide pasar el
   tipo de acción a automático, **Then** el cambio se aplica
   inmediatamente, sin ninguna condición adicional que cumplir.
3. **Given** un tipo de acción en automático, **When** Miquel decide
   volver a manual, **Then** el cambio se aplica igual de inmediato.

---

### User Story 4 - Modo automático: ejecuta directo, se registra igual (Priority: P2)

Con "rotar log" en modo automático, una comprobación que detecta un
log por encima del umbral rota el fichero directamente, sin esperar
aprobación — y el resultado queda registrado exactamente igual que en
modo manual, para que Miquel pueda revisarlo después.

**Why this priority**: Depende de que US1 y US3 ya funcionen — es la
otra mitad del interruptor, la razón de ser de la feature, pero no
tiene sentido antes de que exista el modo manual que compararla.

**Independent Test**: Se puede probar poniendo "rotar log" en
automático, comprobando un log de prueba por encima del umbral, y
verificando que se rota sin ninguna aprobación intermedia, con un
registro de "ejecutado" idéntico en forma al de una aprobación manual.

**Acceptance Scenarios**:

1. **Given** "rotar log" en modo automático y un log por encima del
   umbral, **When** Miquel ejecuta la comprobación, **Then** el log se
   rota inmediatamente y queda un registro de "ejecutado", sin ningún
   estado "pendiente" intermedio.
2. **Given** ese mismo registro, **When** Miquel lo compara con uno
   creado por aprobación manual (User Story 2), **Then** tiene la
   misma forma — mismo detalle, mismo procedimiento de rollback
   documentado.

---

### User Story 5 - Deshacer una rotación ya ejecutada (Priority: P2)

Para cualquier rotación ya ejecutada (manual o automática), Miquel
puede deshacerla — el log rotado vuelve a su nombre original, sin
perder nada de lo escrito después de la rotación.

**Why this priority**: Es lo que hace que "reversible" (Principio VI)
sea real y no solo una promesa en el spec — pero solo tiene sentido
una vez que ya existen ejecuciones que deshacer (depende de US2/US4).

**Independent Test**: Se puede probar rotando un log de prueba,
escribiendo algo nuevo en el fichero (ya vacío) tras la rotación, y
deshaciendo — el contenido anterior a la rotación debe quedar
disponible sin haberse perdido nunca.

**Acceptance Scenarios**:

1. **Given** una rotación ya ejecutada, **When** Miquel pide
   deshacerla, **Then** el procedimiento de rollback documentado se
   aplica y el fichero rotado queda disponible con su nombre original
   — nunca se sobreescribe lo que se haya escrito después de la
   rotación.
2. **Given** una propuesta rechazada o todavía pendiente, **When**
   Miquel intenta deshacerla, **Then** el sistema lo rechaza — no hay
   nada que deshacer de algo que nunca se ejecutó.

---

### Edge Cases

- ¿Qué pasa si el log a rotar ya no existe cuando se intenta ejecutar
  la aprobación (se borró o se movió entre medias)? Se registra como
  "fallido", con el motivo, sin lanzar ningún error sin explicar.
- ¿Qué pasa si dos comprobaciones seguidas detectan el mismo log por
  encima del umbral antes de resolver la primera propuesta? No se
  crea una segunda propuesta duplicada para el mismo fichero mientras
  quede una pendiente.
- ¿Qué pasa con un log que pertenece a un componente crítico? Fuera
  de alcance de la lista cerrada de esta feature — ningún log de la
  lista vigilada en v1 pertenece a un componente crítico (ver
  Assumptions); si en el futuro se añadiera uno, no podría entrar en
  modo automático sin una decisión explícita nueva.
- ¿Qué pasa si "rotar log" está en modo automático y la rotación
  falla (por ejemplo, sin permisos)? Se registra como "fallido", con
  el motivo — nunca se reintenta solo, ni se silencia el fallo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE mantener un modo (`manual` o
  `automatico`) por cada tipo de acción de la lista cerrada, no por
  componente individual — para esta feature, un único tipo:
  `rotar_log`.
- **FR-002**: Todo tipo de acción DEBE empezar en modo `manual` por
  defecto — nunca automático sin que Miquel lo haya activado
  explícitamente.
- **FR-003**: El sistema DEBE permitir a Miquel cambiar el modo de un
  tipo de acción, en cualquier momento, desde el CLI — sin ninguna
  condición previa que cumplir (ni número mínimo de aciertos, ni
  aprobación de un tercero).
- **FR-004**: El sistema DEBE mostrar, antes o junto con el cambio de
  modo, el historial de esa acción (aprobadas, rechazadas, fallidas)
  — informativo, nunca bloqueante.
- **FR-005**: El sistema DEBE evaluar la condición de "rotar log"
  (tamaño del fichero por encima de un umbral configurado) solo sobre
  una lista cerrada y conocida de logs — nunca sobre un fichero
  arbitrario.
- **FR-006**: En modo `manual`, el sistema DEBE registrar una
  propuesta pendiente cuando detecta la condición, y NO DEBE ejecutar
  ninguna rotación hasta que Miquel la apruebe explícitamente.
- **FR-007**: En modo `automatico`, el sistema DEBE ejecutar la
  rotación directamente al detectar la condición, sin ningún paso de
  aprobación intermedio.
- **FR-008**: El sistema NO DEBE crear una segunda propuesta pendiente
  para el mismo fichero mientras ya exista una sin resolver.
- **FR-009**: La acción de rotar un log DEBE ser reversible con un
  procedimiento de rollback escrito (Principio VI): renombrar el
  fichero, nunca truncar ni borrar su contenido — el rollback devuelve
  el fichero rotado a su nombre original.
- **FR-010**: El sistema DEBE permitir deshacer cualquier rotación ya
  ejecutada (manual o automática), y NO DEBE permitir deshacer una
  propuesta que nunca se ejecutó (pendiente o rechazada).
- **FR-011**: El sistema DEBE registrar cada propuesta y cada
  ejecución (aprobada, rechazada, ejecutada, fallida) con su detalle
  real y su desenlace, legible después (Principio VIII, extendido de
  hipótesis a acciones).
- **FR-012**: El sistema NO DEBE actuar nunca sobre un componente de
  la lista de contenedores/componentes críticos, en ningún modo.
- **FR-013**: El sistema NO DEBE depender de ningún diagnóstico del
  motor DeepSeek (`src/diagnostico/`, 007-017) para proponer o
  ejecutar esta acción — la condición se evalúa de forma determinista.
- **FR-014**: El sistema NO DEBE exponer ningún estado accionable en el
  dashboard — el CLI sigue siendo la única superficie de control de
  esta feature (la superficie de solo lectura de la feature 020 no
  cuenta como excepción, ver su propio spec). Enmendado el
  2026-08-13 (research.md §11, a petición explícita de Miquel): el
  sistema SÍ DEBE enviar un aviso por Telegram cuando una rotación en
  modo automático falla — y solo entonces. Un éxito nunca notifica; un
  fallo en modo manual tampoco, porque ya hay un humano mirando el
  resultado del propio comando que lo aprobó.

### Key Entities

- **Configuración de acción**: el modo actual (`manual`/`automatico`)
  de un tipo de acción — para esta feature, solo `rotar_log`.
- **Intento de remediación**: una propuesta o ejecución concreta —
  tipo de acción, componente (ruta del log), momento, modo en que se
  creó, estado (`pendiente`/`rechazado`/`ejecutado`/`fallido`/
  `deshecho`), detalle real, y el procedimiento de rollback
  aplicable si se ejecutó.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los tipos de acción nuevos empiezan en modo
  manual — nunca se observa una ejecución automática de un tipo de
  acción que Miquel no haya activado explícitamente.
- **SC-002**: El 100% de las propuestas y ejecuciones quedan
  registradas con su desenlace real, consultable después sin
  ambigüedad.
- **SC-003**: El 0% de las rotaciones de log destruye contenido — todo
  fichero rotado sigue existiendo íntegro, en cualquier momento
  verificado.
- **SC-004**: El 100% de las rotaciones ya ejecutadas se pueden
  deshacer sin pérdida de datos, verificado contra al menos un caso
  real.
- **SC-005**: El cambio de modo de un tipo de acción se aplica el
  100% de las veces sin ninguna condición adicional más allá de la
  propia decisión de Miquel.

## Assumptions

- **Ningún log de la lista vigilada pertenece a un componente
  crítico** — comprobado antes de especificar, y de nuevo al ampliar
  la lista de 2 a 17 el mismo día (research.md §7): todos son logs de
  monitores/automatizaciones propias del homelab
  (`amsterdam9.*`), no de `homeassistant`/`vaultwarden`/`nextcloud*`/
  `immich*`/`pangolin-server`/`gerbil`/`traefik` (la lista de críticos
  del `CLAUDE.md` general).
- **Sin dependencia del motor DeepSeek en v1** — decisión explícita
  (`BRIEFING.md`, "Feature 019 — material de partida"): los 36
  diagnósticos reales producidos hasta hoy por 007-017 son todos
  `no_diagnosticable`, así que atar esta feature a un `causa_probable`
  real la dejaría sin ningún caso contra el que validarla. Un puente
  futuro entre ambos sistemas queda fuera de alcance de esta feature.
- **"Diagnóstico" en el sentido del Principio IV se cumple aquí en su
  sentido genérico** (una causa conocida y verificada: el fichero
  supera el umbral porque nada lo rota), no en el sentido específico
  del artefacto `Diagnostico`/`Hipotesis` de `src/diagnostico/` — la
  distinción se documenta explícitamente en el plan (Constitution
  Check), mismo criterio que ya aclaró el alcance real del Principio
  XI en el feature 016.
- **Umbral de tamaño configurable, con un valor por defecto razonable
  sobre el estado real observado** — `health-docker.log` a 71 MB,
  `health-ha.log` a 11,6 MB al escribir este spec, ambos sin límite
  declarado. El valor exacto del umbral se fija en `research.md`
  (`/speckit-plan`), no aquí.
- **Ningún otro tipo de acción del barrido de agosto entra en esta
  feature** — los plists corruptos ya están arreglados y
  `beszel-agent.log` ya no existe (comprobado en vivo, 2026-08-13):
  ninguno de los dos es un problema real activo hoy.
- **Sin notificación ni superficie en el dashboard** — decisión
  explícita ya confirmada con Miquel: el CLI es la única interfaz en
  v1, mismo patrón que `diagnostico.cli` en sus primeras features.
