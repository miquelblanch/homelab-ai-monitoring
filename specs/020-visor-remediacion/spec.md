# Feature Specification: Visor de Remediación en el Dashboard

**Feature Branch**: `020-visor-remediacion`

**Created**: 2026-08-13

**Status**: Draft

**Input**: User description: "La feature 019 (remediación automática) dejó el CLI como única superficie. Quiero ver en el dashboard la lista de los 17 logs vigilados con su tamaño actual, su umbral y si están por encima — de solo lectura, sin poder actuar desde ahí. El contenedor del dashboard no tiene acceso a ~/Library/Logs, así que remediacion.cli comprobar escribe un snapshot JSON a /data (mismo patrón que el resto del homelab), y un LaunchAgent nuevo lo dispara cada 15 minutos. No incluye aprobar, rechazar, deshacer ni cambiar el modo desde el dashboard — solo lectura. No incluye notificación por Telegram."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver el estado de los logs vigilados en el dashboard (Priority: P1)

Miquel abre el dashboard y ve, sin usar el CLI, los 17 logs que
vigila la remediación automática: su tamaño actual, su umbral, y si
está por encima (candidato a rotar).

**Why this priority**: Es el valor central del feature — sin esto, la
única forma de ver este estado sigue siendo el CLI, exactamente el
problema que este feature existe para resolver.

**Independent Test**: Se puede probar por completo abriendo el
dashboard y comprobando que la lista mostrada coincide con la salida
real de `remediacion.cli comprobar` para los mismos 17 logs.

**Acceptance Scenarios**:

1. **Given** los 17 logs vigilados con sus tamaños reales, **When**
   Miquel abre la sección de remediación del dashboard, **Then** ve
   cada log con su nombre, tamaño actual y umbral.
2. **Given** un log por encima de su umbral, **When** Miquel mira esa
   fila, **Then** se distingue visualmente de los que están por
   debajo (candidato a rotar).
3. **Given** el snapshot JSON no existe o no se puede leer, **When**
   Miquel abre el dashboard, **Then** el resto del dashboard se sigue
   viendo con normalidad — sin ninguna sección rota ni un error
   visible.

---

### User Story 2 - El snapshot se mantiene fresco sin intervención manual (Priority: P1)

El estado mostrado en el dashboard se actualiza solo, cada 15
minutos, sin que Miquel tenga que ejecutar `comprobar` a mano para
que la vista no esté desfasada.

**Why this priority**: Sin esto, User Story 1 mostraría un estado
potencialmente viejo — el mismo tipo de riesgo de precisión que el
Principio XII prohíbe para el resto del dashboard.

**Independent Test**: Se puede probar comprobando que el snapshot JSON
lleva una marca de tiempo, y que esa marca avanza cada 15 minutos sin
ejecutar nada manualmente (LaunchAgent real).

**Acceptance Scenarios**:

1. **Given** el LaunchAgent nuevo instalado y activo, **When** pasan
   15 minutos, **Then** el snapshot JSON tiene una marca de tiempo más
   reciente que antes.
2. **Given** el snapshot con su marca de tiempo, **When** Miquel mira
   el dashboard, **Then** puede ver de cuándo es el dato (nunca se
   presenta como "ahora mismo" sin más).

---

### User Story 3 - Ver el modo vigente de la acción, sin poder cambiarlo (Priority: P2)

En la misma sección, Miquel ve si `rotar_log` está en modo manual o
automático — informativo, sin ningún control para cambiarlo desde el
dashboard.

**Why this priority**: Complementa a User Story 1 con contexto útil
(saber si lo que ve podría llegar a ejecutarse solo), pero no es
imprescindible para el valor central de ver los tamaños.

**Independent Test**: Cambiar el modo por CLI (`remediacion.cli modo
rotar_log --automatico`) y comprobar que, tras el siguiente
`comprobar`, el dashboard refleja el cambio.

**Acceptance Scenarios**:

1. **Given** `rotar_log` en modo manual, **When** Miquel mira la
   sección, **Then** ve "manual" junto a la lista de logs.
2. **Given** el modo cambiado a automático por CLI, **When** se
   ejecuta el siguiente `comprobar` (hasta 15 min después) y Miquel
   recarga el dashboard, **Then** ve "automático".
3. **Given** esa misma sección, **When** Miquel la revisa, **Then**
   no encuentra ningún botón ni control para aprobar, rechazar,
   deshacer o cambiar el modo — es estrictamente de lectura.

---

### Edge Cases

- ¿Qué pasa si el LaunchAgent nuevo no ha corrido todavía (recién
  instalado)? El dashboard no muestra la sección, o la muestra vacía
  con un mensaje claro — nunca un error ni datos inventados.
- ¿Qué pasa si un log de la lista no existe en el momento de
  `comprobar` (por ejemplo, se roto y el LaunchAgent que lo genera
  todavía no ha vuelto a escribir en él)? Se refleja igual en el
  snapshot, con tamaño 0 o "sin datos" — nunca se omite en silencio.
- ¿Qué pasa si Miquel aprueba una rotación por CLI entre dos
  ejecuciones del LaunchAgent? El dashboard muestra el estado del
  último snapshot, con su fecha visible — no se actualiza al instante,
  mismo criterio de honestidad que el resto del dashboard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE escribir, en cada ejecución de
  `remediacion.cli comprobar`, un snapshot JSON con el estado de los
  17 logs vigilados: nombre, tamaño actual en bytes, umbral en bytes,
  si está por encima, y el modo vigente de `rotar_log`.
- **FR-002**: El snapshot DEBE incluir el momento en que se generó,
  visible en el dashboard — nunca se presenta como el estado "ahora
  mismo" sin decir de cuándo es.
- **FR-003**: El sistema DEBE ejecutar `comprobar` automáticamente
  cada 15 minutos, sin intervención manual de Miquel.
- **FR-004**: El dashboard DEBE mostrar, para cada log vigilado, su
  nombre, tamaño actual, umbral, y si está por encima — en una sección
  de solo lectura.
- **FR-005**: El dashboard DEBE mostrar el modo vigente de
  `rotar_log`.
- **FR-006**: El dashboard NO DEBE ofrecer ningún control para
  aprobar, rechazar, deshacer, cambiar el modo, o disparar `comprobar`
  desde el navegador — estrictamente de lectura.
- **FR-007**: Si el snapshot no existe o no se puede leer, el
  dashboard NO DEBE dejar de mostrar el resto de sus secciones — se
  comporta como si la sección de remediación no tuviera datos
  todavía.
- **FR-008**: El sistema NO DEBE enviar ninguna notificación (Telegram
  u otro canal) como parte de este feature.
- **FR-009**: El sistema NO DEBE requerir montar `~/Library/Logs` (ni
  ningún otro volumen nuevo) en el contenedor del dashboard — el
  snapshot JSON es la única vía de datos.

### Key Entities

- **Snapshot de remediación**: el JSON que escribe `comprobar` —
  momento de generación, y por cada log vigilado su nombre, tamaño,
  umbral, y si supera el umbral; más el modo vigente de `rotar_log`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los 17 logs vigilados aparecen en la sección
  del dashboard, con su tamaño y umbral reales.
- **SC-002**: El snapshot mostrado nunca tiene más de ~20 minutos de
  antigüedad en condiciones normales (cadencia de 15 min + margen).
- **SC-003**: El 0% de las cargas del dashboard falla o muestra un
  error cuando el snapshot no existe o está corrupto.
- **SC-004**: El 100% de las veces que se revisa la sección, no
  existe ningún control interactivo que ejecute una acción — solo
  lectura, verificado contra el HTML/JS servido.

## Assumptions

- **Mismo patrón JSON-a-`/data` que el resto del homelab** — decisión
  explícita para no montar `~/Library/Logs` en el contenedor
  (`BRIEFING.md`, "Feature 020 — material de partida").
- **Cadencia de 15 min** — misma que otros monitores ligeros del
  homelab (`ha_monitor.py`); no hace falta más frecuencia para una
  sección informativa de solo lectura.
- **Sin ningún control de acción en el dashboard** — el CLI sigue
  siendo la única forma de aprobar, rechazar, deshacer o cambiar el
  modo (spec.md de 019, FR-014, sin cambios).
- **Todo el código del LaunchAgent y del dashboard vive fuera de este
  repositorio** — mismo patrón que 002/006/008/018. Este repo solo
  contiene spec, plan, contratos, y el cambio en
  `remediacion.cli comprobar` (que sí vive aquí).
