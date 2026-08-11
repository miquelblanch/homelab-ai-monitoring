# Feature Specification: Generalizar el Diagnóstico a Discos

**Feature Branch**: `009-diagnostico-discos`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (feature 007) hoy solo sabe diagnosticar contenedores caídos — se limitó a propósito a un solo origen para validar el enfoque antes de generalizar. Quiero que también pueda diagnosticar episodios de disco: cuando un disco cruza el umbral de aviso o crítico de uso, quiero poder pedirle al motor que reúna la evidencia real alrededor de ese momento (uso del disco en la ventana de tiempo relevante) y formule hipótesis de causa probable, con el mismo rigor y las mismas garantías que ya tiene para contenedores: varias hipótesis contrastadas, nunca inventar una causa sin evidencia, un límite de gasto diario compartido con el resto del motor. No incluye generalizar a ningún otro origen de la Central de Alarmas (Home Assistant, backups, relays, hosts externos, el hub de Beszel, agentes, inventario de cobertura) — eso queda para features posteriores, uno a uno. No incluye ninguna acción correctiva sobre el disco, ni mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le diera superficie visible."

## Clarifications

### Session 2026-08-11

- Q: Si el disco que se está diagnosticando es el mismo donde vive la
  base de datos de diagnósticos, y está tan lleno que no queda espacio
  para escribir el resultado, ¿qué debe pasar? → A: Opción A — se
  acepta el riesgo tal cual, sin ningún mecanismo de respaldo nuevo. Si
  la escritura falla, el intento se pierde sin más — mismo
  comportamiento que cualquier fallo de escritura por disco lleno. El
  umbral de "disco crítico" (90%, feature 006) ya avisa con margen
  antes de llegar a 0 bytes libres.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar un episodio de disco en vivo (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna la
evidencia real del uso actual de un disco y formule hipótesis de causa
probable — igual que ya puede hacer con un contenedor caído — tanto si
hay un aviso de disco activo ahora mismo como si quiere comprobar un
disco que hoy está sano.

**Why this priority**: Es el valor central de este feature. Sin esto,
el motor de diagnóstico sigue limitado a contenedores y la promesa de
"generalizar" no se cumple para ningún caso real.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquiera de los tres discos del homelab y
comprobando que el resultado incluye evidencia real de uso de disco,
no evidencia de contenedor ni un error.

**Acceptance Scenarios**:

1. **Given** un disco con uso por debajo de cualquier umbral de aviso,
   **When** Miquel pide diagnosticarlo, **Then** el motor reúne su
   evidencia real (uso reciente) y concluye "no se puede diagnosticar"
   sin inventar una causa — no hay nada que explicar.
2. **Given** un disco con un aviso de uso activo, **When** Miquel pide
   diagnosticarlo, **Then** el motor reúne la evidencia real alrededor
   de ese momento y formula hipótesis de causa probable, con el mismo
   rigor que ya exige para contenedores (más de una hipótesis cuando la
   evidencia lo permite, cada una contrastada).
3. **Given** cualquier episodio de disco diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de contenedor — misma
   estructura, mismas garantías de la Central de Registro (Principio
   VIII).

---

### User Story 2 - Diagnosticar un episodio de disco en diferido, reproduciblemente (Priority: P2)

Miquel quiere poder señalar un momento pasado concreto de un disco
(por ejemplo, un pico de uso que ya bajó) y diagnosticarlo más tarde,
obteniendo siempre la misma conclusión si repite el diagnóstico sobre
el mismo momento.

**Why this priority**: Depende de que el mecanismo en vivo (User Story
1) ya funcione — es la misma tubería aplicada a un momento pasado en
vez de al presente. Menos urgente que la Historia 1 porque, a
diferencia de los contenedores (con 49 reinicios reales de `beszel`
como corpus), hoy no existe ningún incidente real de disco que
diagnosticar en diferido — se valida el mecanismo, no un caso real
todavía.

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado de un disco y comprobando que el diagnóstico produce la
misma conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado conocido del uso de un disco, **When**
   Miquel pide diagnosticarlo en diferido, **Then** el motor reúne la
   evidencia real de ese momento (no la actual) y concluye igual que lo
   haría en vivo con esos mismos datos.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007).
3. **Given** un momento pasado para el que ya no quedan datos de disco
   (fuera de la retención disponible), **When** Miquel pide
   diagnosticarlo, **Then** el motor concluye que no se puede
   diagnosticar por falta de evidencia — nunca inventa una causa por no
   tener datos.

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un disco que no existe o no se
  vigila? El motor concluye que no se puede diagnosticar — mismo
  criterio que un contenedor inexistente.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege los diagnósticos de contenedor (feature
  007, FR-009/FR-010) — un diagnóstico de disco cuenta contra el mismo
  límite, no contra uno aparte.
- ¿Qué pasa si no hay ningún incidente real de disco disponible para
  validar el feature contra un caso conocido, a diferencia de `beszel`
  para contenedores? Se acepta como limitación conocida de este
  feature — la validación se apoya en diagnósticos en vivo contra el
  estado sano actual de los tres discos reales, y contra cualquier
  aviso real de disco que aparezca mientras se desarrolla.
- ¿Qué pasa si el disco diagnosticado es el mismo donde vive el
  registro de diagnósticos, y no queda espacio para escribir el
  resultado? **Resuelto en Clarifications (2026-08-11)**: se acepta el
  riesgo tal cual, sin ningún mecanismo de respaldo — si la escritura
  falla, el intento se pierde, mismo comportamiento que cualquier
  fallo de escritura por disco lleno.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de disco como
  entrada, tanto en vivo (el estado actual de un disco vigilado) como
  en diferido (un momento pasado concreto de ese disco) — mismas dos
  vías que ya existen para episodios de contenedor (feature 007).
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  disco, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007 para contenedores.
- **FR-003**: El sistema DEBE reunir evidencia real de uso del disco
  (no de ningún contenedor) alrededor del momento del episodio, antes
  de formular ninguna hipótesis.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de disco cuando la evidencia lo permita, con
  el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de disco con
  exactamente uno de dos resultados — una causa probable con evidencia,
  o que no se puede diagnosticar — nunca presentar una causa sin
  evidencia que la respalde (mismo invariante que FR-007 de 007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de disco DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a los
  diagnósticos de contenedor — un único límite compartido para todo el
  motor de diagnóstico, no uno aparte por origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ningún disco, ni proponer una remediación nueva — mismo alcance
  estrictamente diagnóstico que 007.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de disco en ningún sitio del dashboard — sigue siendo solo por línea
  de comandos en este feature (la superficie visible, si llega, es un
  feature posterior, igual que lo fue 008 para contenedores).
- **FR-010**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (Home Assistant, backups, relays, hosts externos,
  el hub de Beszel, agentes, inventario) — el alcance de este feature
  se limita a contenedores (ya existente) y discos.

### Key Entities

- **Episodio de disco**: la misma entidad "Episodio" que 007 ya define,
  generalizada para poder representar también un disco, no solo un
  contenedor — atributos relevantes: qué disco, la ventana de tiempo,
  si es en vivo o en diferido, y el snapshot de evidencia congelado.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de disco.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de disco (en
  vivo ya congelado, o en diferido) produce el mismo `conclusion_tipo`
  las dos veces, el 100% de las veces que se prueba — mismo criterio
  que SC-001 de 007.
- **SC-002**: El 100% de los diagnósticos de disco con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de disco, sumado al de
  los de contenedor, nunca supera el límite diario configurado —
  verificable revisando el acumulado de cualquier día.
- **SC-004**: Diagnosticar en vivo cualquiera de los tres discos reales
  del homelab en su estado sano actual concluye "no se puede
  diagnosticar" sin inventar una causa, el 100% de las veces que se
  prueba.

## Assumptions

- No existe hoy ningún concepto de "disco crítico" equivalente a la
  lista de contenedores críticos de 007 (`es_critico`) — ningún disco
  tiene un tratamiento especial de "no proponer acciones" porque este
  feature, como 007, no propone acciones sobre ningún disco en absoluto
  (FR-008). Si en el futuro se añade remediación (fuera de alcance de
  este feature y del propio 007), esa sería la ocasión de decidir si
  algún disco necesita un tratamiento equivalente.
- Un episodio de disco en diferido se identifica por el disco y un
  momento concreto en el tiempo, no por el id de una fila en una tabla
  de eventos — a diferencia de `restart_history_id` para contenedores,
  no existe ninguna tabla de eventos discretos de disco en
  `homelab.db`; el propio momento es el identificador natural del
  episodio.
- La validación de este feature contra un caso real (equivalente a los
  49 reinicios de `beszel` para 007) no es posible hoy por falta de
  incidentes de disco registrados — se deja constancia de esta
  limitación en vez de inventar un caso sintético que aparente ser
  real.
- Los otros 7 orígenes de la Central de Alarmas (Home Assistant,
  backups, relays, hosts externos, el hub de Beszel, agentes,
  inventario) quedan fuera de este feature — cada uno necesita su
  propia investigación de qué constituye evidencia real, igual que se
  hizo aquí para discos (`BRIEFING.md`, "Feature 009 — material de
  partida").
