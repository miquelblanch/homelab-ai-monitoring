# Feature Specification: Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Feature Branch**: `016-diagnostico-agentes`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (007, generalizado a discos en 009, HA en 010, backups en 011, relays en 012, inventario en 013, hosts externos en 014 y el hub de Beszel en 015) hoy no sabe diagnosticar nada de los LaunchAgents que ejecutan toda la automatización del homelab — los ~20 agentes amsterdam9.*, com.homeassistant.* y ai.hermes.*. Quiero que también pueda diagnosticar un agente concreto: reunir su estado real (si tiene un proceso activo, y su último código de salida) y formular hipótesis de causa probable cuando esté fallando, con el mismo rigor que los demás orígenes — varias hipótesis contrastadas, nunca inventar una causa, mismo límite de gasto diario compartido. A diferencia de todos los orígenes anteriores, este no tiene ningún modo diferido: no existe ningún historial real de LaunchAgents que consultar, ni en el propio fichero de estado (se sobreescribe cada 5 minutos) ni en su log (vacío) ni en ninguna base de datos del homelab — solo se puede diagnosticar el estado actual. No incluye el mecanismo relacionado de latidos de monitores (get_monitor_heartbeats()) — es una fuente de evidencia distinta, fuera de alcance de este feature. No incluye ninguna acción correctiva sobre ningún agente (reiniciarlo, recargarlo). No incluye mostrar este diagnóstico en el dashboard — sigue siendo solo por línea de comandos."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo un agente concreto (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna el
estado real de un LaunchAgent concreto (uno de los ~20 que ejecutan la
automatización del homelab) y formule hipótesis de causa probable
cuando esté fallando, igual que ya puede hacer con los demás orígenes.

**Why this priority**: Es el único valor que este feature entrega —
sin modo diferido posible (ver Assumptions), esta es la totalidad del
alcance, no solo el MVP.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquier agente y comprobando que el resultado
incluye su estado real (si tiene un proceso activo, su último código
de salida), no un texto genérico ni evidencia de otro agente.

**Acceptance Scenarios**:

1. **Given** un agente sano (con proceso activo, o inactivo pero con
   último código de salida normal), **When** Miquel pide
   diagnosticarlo, **Then** el motor reúne su estado real y concluye
   "no se puede diagnosticar" sin inventar una causa.
2. **Given** un agente sin proceso activo y con un último código de
   salida anómalo, **When** Miquel pide diagnosticarlo, **Then** el
   motor reúne su estado real y formula hipótesis de causa probable,
   con el mismo rigor que ya exige para los demás orígenes.
3. **Given** cualquier episodio de agente diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de cualquier otro origen —
   misma estructura, mismas garantías de la Central de Registro
   (Principio VIII).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un `label` que no corresponde a
  ningún agente real? El motor concluye que no se puede diagnosticar
  — mismo criterio que un identificador inexistente en cualquier otro
  origen.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege a los demás orígenes.
- ¿Por qué no hay ningún modo diferido, a diferencia de todos los
  orígenes anteriores? No es una decisión de alcance — es una
  limitación real de la evidencia disponible: el fichero de estado de
  los agentes se sobreescribe en cada ciclo (cada 5 min), su log no
  contiene ningún dato aprovechable, y no existe ninguna tabla
  histórica equivalente a `restart_history` para LaunchAgents en
  ninguna base de datos del homelab. Pedir un momento pasado no
  tendría ninguna evidencia real que ofrecer.
- ¿Qué pasa con `get_monitor_heartbeats()` (latidos de monitores)? Es
  un mecanismo relacionado pero distinto — queda fuera de este
  feature (ver Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de agente como
  entrada, identificado por su `label` — **únicamente en vivo**, sin
  ningún modo diferido (ver Assumptions).
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  agente, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007 para el propio episodio ya congelado (Principio XI se cumple
  para el episodio congelado, no para poder señalar un momento
  histórico distinto — ver Assumptions).
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis: si el agente tiene un proceso activo, y su último
  código de salida conocido.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de agente cuando la evidencia lo permita, con
  el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de agente con
  exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una
  causa sin evidencia que la respalde (mismo invariante que FR-007 de
  007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de agente DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a
  los demás orígenes.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ningún agente (reiniciarlo, recargarlo, modificar su plist) ni
  proponer una remediación nueva — mismo alcance estrictamente
  diagnóstico que los demás orígenes.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de agente en ningún sitio del dashboard — sigue siendo solo por
  línea de comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar el mecanismo de latidos
  de monitores (`get_monitor_heartbeats()`) — es una fuente de
  evidencia distinta, fuera de alcance de este feature.
- **FR-011**: El sistema NO DEBE ofrecer, aceptar, ni simular ningún
  argumento de diferido para este origen — no existe evidencia
  histórica real que reunir, así que el contrato del CLI no debe
  sugerir una capacidad que no tiene datos que respaldar.

### Key Entities

- **Episodio de agente**: la misma entidad "Episodio" que
  007/009/010/011/012/013/014/015 ya definen, generalizada para poder
  representar también un LaunchAgent — atributos relevantes: el
  `label` del agente, siempre en vivo (`en_vivo` siempre `True` para
  este origen), y el snapshot de evidencia congelado con su estado
  real (proceso activo, último código de salida).
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de agente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de agente ya
  congelado produce el mismo `conclusion_tipo` las dos veces, el 100%
  de las veces que se prueba — mismo criterio que SC-001 de 007,
  009-015, aplicado aquí al único modo posible (en vivo).
- **SC-002**: El 100% de los diagnósticos de agente con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de agente, sumado al
  del resto de orígenes, nunca supera el límite diario configurado.
- **SC-004**: Diagnosticar en vivo un agente sano concluye "no se
  puede diagnosticar" sin inventar una causa, el 100% de las veces que
  se prueba.

## Assumptions

- **Sin ningún modo diferido, a diferencia de los 8 orígenes
  anteriores — limitación real, no una decisión de alcance**:
  comprobado explícitamente antes de especificar: el fichero de estado
  de los agentes (`launchagents_raw.txt`) se sobreescribe cada 5 min
  sin ningún historial; su log asociado no contiene ningún dato
  aprovechable (9.392 líneas vacías, comprobado en vivo); no existe
  ninguna tabla histórica de LaunchAgents en ninguna base de datos del
  homelab (`docker_monitor.py` solo vigila contenedores). El Principio
  XI (Reproducibilidad Diferida) se cumple para el episodio ya
  congelado (SC-001), no para poder señalar un momento pasado
  distinto — documentado explícitamente como limitación real de la
  evidencia disponible, no oculta ni forzada con un mecanismo
  ficticio.
- **`Latidos de monitores` (`get_monitor_heartbeats()`) queda fuera de
  este feature** — es un mecanismo relacionado (también "Automatización"
  en la Central de Alarmas) pero con su propia fuente de evidencia
  distinta (latidos de `heartbeat.py`, no el estado de `launchctl`).
  Encontrado como una inconsistencia real del propio histórico de
  `BRIEFING.md` (desapareció de la lista de orígenes restantes entre
  los materiales de 011 y 012 sin que ningún feature lo cerrara) — se
  documenta aquí en vez de ampliar el alcance de este feature sin que
  Miquel lo decida explícitamente (`BRIEFING.md`, "Feature 016 —
  material de partida").
- **Sin identificador equivalente a "agente crítico"** — igual que en
  009-015, este feature no propone ninguna acción sobre nada.
- **Cierra los 9 orígenes de la Central de Alarmas** que este proyecto
  se propuso generalizar — no queda ningún origen restante después de
  este feature.
