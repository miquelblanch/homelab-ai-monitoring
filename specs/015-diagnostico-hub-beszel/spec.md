# Feature Specification: Generalizar el Diagnóstico al Hub de Beszel

**Feature Branch**: `015-diagnostico-hub-beszel`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (007, generalizado a discos en 009, HA en 010, backups en 011, relays en 012, inventario en 013 y hosts externos en 014) hoy no sabe diagnosticar nada del propio hub de Beszel — la herramienta de observabilidad del homelab que vigila el Mac Mini y los 2 hosts externos. Quiero que también pueda diagnosticar si el hub sigue vigilando algo de verdad, distinto de si un host concreto está caído (eso ya lo cubre el origen anterior): en vivo, leyendo la antigüedad de todos los sistemas que el hub tiene registrados y si todos a la vez superan el umbral de frescura ya establecido; en diferido, señalando un momento pasado y consultando si todos los sistemas del hub dejaron de reportar datos de rendimiento a la vez en esa ventana — sin inventar un estado \"caído\" que la propia evidencia no sostenga si solo hay ausencia parcial. Mismo rigor que los demás orígenes: varias hipótesis contrastadas, nunca inventar una causa, mismo límite de gasto diario compartido. Como con los backups, no hace falta identificar ningún componente — solo hay un hub. No incluye diagnosticar un host externo concreto — eso es otro origen, ya cubierto. No incluye ninguna acción correctiva sobre Beszel. No incluye generalizar al último origen restante (agentes). No incluye mostrar este diagnóstico en el dashboard — sigue siendo solo por línea de comandos."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo si el hub sigue vigilando algo de verdad (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna el
estado real, ya calculado, del propio hub de Beszel — si todos los
sistemas que tiene registrados han dejado de reportar a la vez, no
solo uno — y formule hipótesis de causa probable, igual que ya puede
hacer con los demás orígenes.

**Why this priority**: Es el valor central de este feature — sin
esto, un hub colgado (que deja de vigilar absolutamente todo, no solo
un host) sigue sin ninguna explicación más allá de la alarma estática
ya existente.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo del hub y comprobando que el resultado incluye la
antigüedad real de cada sistema registrado, no un texto genérico.

**Acceptance Scenarios**:

1. **Given** al menos un sistema del hub reportando con normalidad,
   **When** Miquel pide diagnosticar el hub, **Then** el motor reúne
   la antigüedad real de todos los sistemas y concluye "no se puede
   diagnosticar" sin inventar una causa — el hub sigue vigilando algo.
2. **Given** todos los sistemas del hub sin reportar desde hace más
   del umbral de frescura ya establecido, **When** Miquel pide
   diagnosticarlo, **Then** el motor reúne esa evidencia real y
   formula hipótesis de causa probable, con el mismo rigor que ya
   exige para los demás orígenes.
3. **Given** cualquier episodio del hub diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de cualquier otro origen.

---

### User Story 2 - Diagnosticar un momento pasado del hub, reproduciblemente (Priority: P2)

Miquel quiere poder señalar un momento pasado concreto y diagnosticar
si todos los sistemas del hub dejaron de reportar datos de rendimiento
a la vez en una ventana alrededor de ese momento, obteniendo siempre
la misma conclusión si repite el diagnóstico sobre el mismo momento —
sin que la ausencia parcial (algunos sistemas sin datos, otros con
datos) se presente como si el hub entero estuviera caído.

**Why this priority**: Depende de que el mecanismo en vivo (Historia
1) ya funcione. Menos urgente porque el valor central del feature —
diagnosticar el hub colgado ahora mismo— ya lo cubre la Historia 1.

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado y comprobando que el diagnóstico produce la misma
conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado concreto, **When** Miquel pide
   diagnosticarlo en diferido, **Then** el motor reúne la evidencia
   real de si cada sistema del hub reportaba datos de rendimiento en
   una ventana alrededor de ese momento y formula hipótesis de causa
   probable, sin presentar una ausencia parcial como si todo el hub
   estuviera caído.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007, 009, 010, 011, 012, 013 y 014).

---

### Edge Cases

- ¿Qué pasa si solo algunos sistemas dejaron de reportar, no todos?
  Es ausencia parcial, no evidencia de que el hub entero esté caído —
  el motor la reúne igual (puede formular hipótesis sobre por qué ese
  subconjunto falla), pero nunca la presenta como "hub caído
  confirmado" sin más.
- ¿Qué pasa si no hay ningún sistema registrado en el hub (el fichero
  de estado está vacío o ausente)? Es evidencia real de que el hub no
  vigila nada — ausencia total, no un caso vacío que impida congelar.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege a los demás orígenes.
- ¿Qué pasa si en diferido no hay ninguna muestra de ningún sistema en
  la ventana, en ninguna resolución de retención? El motor lo declara
  honestamente como ausencia total comprobada — sigue sin ser, por sí
  sola, una prueba de que el hub estuviera "caído" en el sentido de un
  fallo del propio proceso, frente a otras causas posibles.
- ¿Qué pasa si la consulta al hub falla (Docker no disponible)? No es
  un error — el episodio se congela igual, con evidencia vacía, mismo
  criterio que una llamada de solo lectura fallida en cualquier otro
  origen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio del hub de Beszel
  como entrada, tanto en vivo (el estado actual de todos los sistemas
  registrados) como en diferido (un momento pasado concreto) — sin
  necesidad de identificar ningún componente, mismo criterio que ya
  usa el origen de backup (011): solo existe un hub.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio del
  hub, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007.
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis, distinta según el modo: en vivo, la antigüedad
  real de cada sistema que el hub tiene registrado, con el mismo
  umbral de frescura ya establecido para hosts externos; en diferido,
  si cada sistema tenía muestras de rendimiento registradas en una
  ventana alrededor del momento pedido.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio del hub cuando la evidencia lo permita, con el
  mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico del hub con
  exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una
  causa sin evidencia que la respalde (mismo invariante que FR-007 de
  007).
- **FR-006a**: El sistema NO DEBE presentar una ausencia parcial de
  datos (algunos sistemas sin reportar, otros sí) como prueba de que
  el hub entero está caído — mismo tipo de restricción que FR-006a de
  014, adaptada a que aquí la unidad de análisis es el conjunto de
  sistemas, no un host individual.
- **FR-007**: El gasto en DeepSeek de un diagnóstico del hub DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a
  los demás orígenes — un único límite compartido para todo el motor.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre Beszel ni proponer una remediación nueva — mismo alcance
  estrictamente diagnóstico que los demás orígenes.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  del hub en ningún sitio del dashboard — sigue siendo solo por línea
  de comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar un host externo concreto
  (Uptime Kuma, AdGuard Home) — ese es el origen #7 (014), ya cerrado;
  este feature diagnostica el hub como conjunto, no un host
  individual.
- **FR-011**: El sistema NO DEBE diagnosticar el último origen
  restante de la Central de Alarmas (agentes) — el alcance de este
  feature se limita a los orígenes ya existentes y al hub de Beszel.

### Key Entities

- **Episodio del hub de Beszel**: la misma entidad "Episodio" que
  007/009/010/011/012/013/014 ya definen, generalizada para poder
  representar también un episodio del propio hub — sin componente que
  identificar (mismo criterio que backup, 011); atributos relevantes:
  el momento o la ventana, si es en vivo o en diferido, y el snapshot
  de evidencia congelado — con la antigüedad de todos los sistemas en
  vivo, con presencia/ausencia de muestras por sistema en diferido.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios del hub.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio del hub (en
  vivo ya congelado, o en diferido) produce el mismo `conclusion_tipo`
  las dos veces, el 100% de las veces que se prueba — mismo criterio
  que SC-001 de 007, 009, 010, 011, 012, 013 y 014.
- **SC-002**: El 100% de los diagnósticos del hub con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos del hub, sumado al del
  resto de orígenes, nunca supera el límite diario configurado.
- **SC-004**: Diagnosticar en vivo el hub sano (al menos un sistema
  reportando con normalidad) concluye "no se puede diagnosticar" sin
  inventar una causa, el 100% de las veces que se prueba.
- **SC-005**: Diagnosticar en diferido un momento sin ninguna avería
  real conocida concluye "no se puede diagnosticar" honesto, medido
  contra el estado sano real (Principio IX) — sin línea base real de
  un episodio de "hub realmente caído" disponible desde el arranque de
  este feature (comprobado: la única avería real conocida en el
  periodo retenido, la del 2026-07-30 al 2026-08-07, nunca afectó a
  todos los sistemas del hub a la vez — ver Assumptions), mismo tipo
  de limitación ya aceptada en 009, 010 y 011.

## Assumptions

- **Sin línea base real de "hub realmente caído" disponible, a
  diferencia de 012/013/014** — comprobado explícitamente antes de
  planificar: la avería real conocida que validó el origen anterior
  (routing de contenedores roto, 2026-07-30 a 2026-08-07) nunca afectó
  al tercer sistema que vigila Beszel (`Mac Mini Server`, el propio
  Mac donde vive el hub) — su agente se comunica con el hub en local,
  sin pasar por el routing que se rompió. Durante toda esa avería, el
  hub siguió recibiendo datos de al menos un sistema, así que nunca
  estuvo "caído" según el criterio de este origen (todos a la vez).
  Se documenta como limitación aceptada, no se inventa un caso
  sintético — mismo criterio que 009/010/011 al arrancar sin línea
  base real.
- **Sin identificador de componente**, igual que backup (011): solo
  existe un hub, así que `--hub-beszel-vivo`/`--hub-beszel-historico
  MOMENTO_ISO` no necesitan ningún nombre.
- **El umbral de frescura es el mismo ya establecido para hosts
  externos** (`BESZEL_HOSTS_MAX_AGE_S`, 900s) — no se inventa un
  umbral nuevo para este origen, es la misma política ya usada por
  `app.py::get_beszel_hub_status()`.
- No existe ningún concepto de "hub crítico" — igual que en 009-014,
  este feature no propone ninguna acción sobre nada.
- El último origen restante de la Central de Alarmas (agentes) queda
  fuera de este feature — necesita su propia investigación de qué
  constituye evidencia real, igual que se hizo aquí para el hub de
  Beszel (`BRIEFING.md`, "Feature 015 — material de partida").
