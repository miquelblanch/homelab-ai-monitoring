# Feature Specification: Generalizar el Diagnóstico a los Latidos de Monitores

**Feature Branch**: `017-diagnostico-latidos`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (007, generalizado a discos en 009, HA en 010, backups en 011, relays en 012, inventario en 013, hosts externos en 014, el hub de Beszel en 015 y los LaunchAgents en 016) hoy no sabe diagnosticar el mecanismo de latidos de monitores (get_monitor_heartbeats()), dejado explícitamente fuera de 016 por ser una fuente de evidencia distinta. Quiero que también pueda diagnosticar el latido de un job concreto de los 8 vigilados hoy por el dashboard: reunir su estado real (si ha latido, hace cuánto, y su último detalle) y formular hipótesis de causa probable cuando esté rancio o ausente, con el mismo rigor que los demás orígenes — varias hipótesis contrastadas, nunca inventar una causa, mismo límite de gasto diario compartido. Igual que los LaunchAgents en 016, este origen no tiene ningún modo diferido: cada latido se sobreescribe en cada ciclo y no existe ninguna tabla histórica, así que solo se puede diagnosticar el estado actual. No incluye corregir la inconsistencia real encontrada entre la lista de jobs del dashboard y la de heartbeat.py — es un defecto del homelab, no de este proyecto. No incluye ninguna acción correctiva sobre ningún monitor (relanzarlo). No incluye mostrar este diagnóstico en el dashboard — sigue siendo solo por línea de comandos."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo el latido de un job concreto (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna el
estado real del latido de un job concreto (uno de los 8 monitores del
homelab vigilados hoy por `app.py::get_monitor_heartbeats()`) y
formule hipótesis de causa probable cuando esté rancio o ausente,
igual que ya puede hacer con los demás orígenes.

**Why this priority**: Es el único valor que este feature entrega —
sin modo diferido posible (ver Assumptions), esta es la totalidad del
alcance, no solo el MVP.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo del latido de cualquier job y comprobando que el
resultado incluye su estado real (si ha latido, hace cuánto, su último
detalle), no un texto genérico ni evidencia de otro job.

**Acceptance Scenarios**:

1. **Given** un job con latido reciente y estado normal, **When**
   Miquel pide diagnosticarlo, **Then** el motor reúne su estado real
   y concluye "no se puede diagnosticar" sin inventar una causa.
2. **Given** un job cuyo latido está rancio (más viejo que su umbral
   propio) o nunca ha latido, **When** Miquel pide diagnosticarlo,
   **Then** el motor reúne su estado real y formula hipótesis de causa
   probable, con el mismo rigor que ya exige para los demás orígenes.
3. **Given** cualquier episodio de latido diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de cualquier otro origen —
   misma estructura, mismas garantías de la Central de Registro
   (Principio VIII).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un `job` que no corresponde a
  ninguno de los 8 monitores vigilados? El motor concluye que no se
  puede diagnosticar — mismo criterio que un identificador inexistente
  en cualquier otro origen.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege a los demás orígenes.
- ¿Por qué no hay ningún modo diferido, igual que en 016? No es una
  decisión de alcance — es una limitación real de la evidencia
  disponible: cada fichero de latido (`<job>.json`) se sobreescribe en
  cada ciclo y no existe ninguna tabla histórica equivalente en
  ninguna base de datos del homelab. Pedir un momento pasado no
  tendría ninguna evidencia real que ofrecer.
- ¿Qué pasa con la inconsistencia real encontrada entre la lista de 8
  jobs del dashboard (`app.py::MONITOR_JOBS`) y los 7 del manifiesto de
  `heartbeat.py` (`DEFAULT_MANIFEST`)? Es un defecto real del homelab
  —tres jobs escriben su latido pero son invisibles para
  `heartbeat.py --report` y el informe de Telegram— pero queda fuera
  de este feature: no es un defecto de este proyecto, y corregirlo
  requeriría tocar `heartbeat.py`/`app.py`, fuera del repo público (ver
  Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de latido como
  entrada, identificado por su `job` — **únicamente en vivo**, sin
  ningún modo diferido (ver Assumptions).
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  latido, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007 para el propio episodio ya congelado (Principio XI se cumple
  para el episodio congelado, no para poder señalar un momento
  histórico distinto — ver Assumptions).
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis: si el job ha latido alguna vez, hace cuánto tiempo
  desde su último latido, su umbral de antigüedad máxima propio, y el
  último detalle registrado.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de latido cuando la evidencia lo permita, con
  el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de latido con
  exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una
  causa sin evidencia que la respalde (mismo invariante que FR-007 de
  007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de latido DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a
  los demás orígenes.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ningún monitor (relanzarlo, forzar un ciclo) ni proponer una
  remediación nueva — mismo alcance estrictamente diagnóstico que los
  demás orígenes.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de latido en ningún sitio del dashboard — sigue siendo solo por
  línea de comandos en este feature.
- **FR-010**: El sistema NO DEBE corregir ni ocultar la inconsistencia
  real entre la lista de jobs de `app.py::MONITOR_JOBS` y la de
  `heartbeat.py::DEFAULT_MANIFEST` — es un defecto del homelab, fuera
  de alcance de este proyecto (ver Assumptions).
- **FR-011**: El sistema NO DEBE ofrecer, aceptar, ni simular ningún
  argumento de diferido para este origen — no existe evidencia
  histórica real que reunir, así que el contrato del CLI no debe
  sugerir una capacidad que no tiene datos que respaldar.

### Key Entities

- **Episodio de latido**: la misma entidad "Episodio" que
  007/009/010/011/012/013/014/015/016 ya definen, generalizada para
  poder representar también el latido de un job de monitor —
  atributos relevantes: el `job`, siempre en vivo (`en_vivo` siempre
  `True` para este origen), y el snapshot de evidencia congelado con
  su estado real (si ha latido, edad del último latido, umbral propio,
  último detalle).
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de latido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de latido ya
  congelado produce el mismo `conclusion_tipo` las dos veces, el 100%
  de las veces que se prueba — mismo criterio que SC-001 de 007,
  009-016, aplicado aquí al único modo posible (en vivo).
- **SC-002**: El 100% de los diagnósticos de latido con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de latido, sumado al
  del resto de orígenes, nunca supera el límite diario configurado.
- **SC-004**: Diagnosticar en vivo un job con latido reciente y sano
  concluye "no se puede diagnosticar" sin inventar una causa, el 100%
  de las veces que se prueba.

## Assumptions

- **Sin ningún modo diferido, igual que 016 — limitación real, no una
  decisión de alcance**: comprobado explícitamente antes de
  especificar: cada fichero `<job>.json` en
  `/Volumes/FastData/homelab/data/heartbeats/` se sobreescribe en cada
  ciclo sin ningún historial; no existe ninguna tabla histórica de
  latidos en ninguna base de datos del homelab. El Principio XI
  (Reproducibilidad Diferida) se cumple para el episodio ya congelado
  (SC-001), no para poder señalar un momento pasado distinto —
  documentado explícitamente como limitación real de la evidencia
  disponible, no oculta ni forzada con un mecanismo ficticio.
- **La lista de 8 jobs es la de `app.py::MONITOR_JOBS`, no la de
  `heartbeat.py::DEFAULT_MANIFEST`**: ambas existen en el homelab real
  y no coinciden (comprobado: 5 jobs en común, 3 solo en la del
  dashboard, 2 solo en la de `heartbeat.py`). Se elige la del dashboard
  porque es la que ya alimenta la Central de Alarmas real
  (`add("monitores", "monitor_sin_latido", ...)`) y la que
  literalmente ejecuta `get_monitor_heartbeats()`, el nombre por el
  que 016 excluyó este origen (`BRIEFING.md`, "Feature 017 — material
  de partida").
- **La inconsistencia entre ambas listas no se corrige en este
  feature** — es un defecto real del propio homelab (tres jobs con
  latido escrito pero invisibles para el informe de Telegram), fuera
  del repositorio de este proyecto y fuera de su alcance (Assumptions,
  `BRIEFING.md`).
- **Sin identificador equivalente a "monitor crítico"** — igual que en
  009-016, este feature no propone ninguna acción sobre nada.
- **Cierra el décimo y último mecanismo relacionado con la Central de
  Alarmas** que quedaba explícitamente pendiente desde 016 — no se
  conoce ningún otro origen ni mecanismo relacionado sin generalizar
  después de este feature.
