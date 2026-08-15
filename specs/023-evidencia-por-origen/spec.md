# Feature Specification: Evidencia de Diagnóstico Organizada por Origen

**Feature Branch**: `023-evidencia-por-origen`

**Created**: 2026-08-15

**Status**: Draft

**Input**: User description: "Partir la evidencia de diagnóstico en piezas independientes por origen. Hoy los diez orígenes de evidencia que reconoce el sistema de diagnóstico (contenedor, disco, Home Assistant, backup, relay, inventario, host externo, hub Beszel, agente y latido) viven todos juntos en un único lugar de 1.864 líneas, mezclados entre sí salvo por un pequeño núcleo de funciones realmente compartidas (conexión a la base de datos, inspección de Docker). Consecuencia: para tocar o verificar el comportamiento de un solo origen hay que orientarse dentro de un contenido diez veces mayor del que le corresponde, y nada impide que un cambio pensado para un origen afecte por accidente al código de otro con el que no tiene relación."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Revisar el comportamiento de un solo origen (Priority: P1)

Quien mantiene el sistema de diagnóstico necesita revisar o verificar cómo se
congela la evidencia de un origen concreto (por ejemplo, disco, o backup) sin
tener que orientarse dentro del contenido de los otros nueve orígenes, que no
tienen relación con el que le ocupa.

**Why this priority**: Es el problema central que motiva el cambio — hoy
revisar un origen obliga a moverse dentro de un contenido diez veces mayor
del que le corresponde. Sin esto no hay refactor.

**Independent Test**: Se puede probar eligiendo cualquiera de los diez
orígenes y comprobando que su comportamiento se puede leer y verificar por
completo sin abrir ni ejecutar el contenido de ningún otro origen (salvo el
mecanismo compartido, explícitamente distinto de los diez).

**Acceptance Scenarios**:

1. **Given** el origen "disco" y el origen "backup", **When** se modifica el
   comportamiento de "disco", **Then** el comportamiento de "backup" no se ve
   afectado y su verificación no requiere volver a ejecutarse por ese motivo.
2. **Given** cualquiera de los diez orígenes, **When** alguien necesita
   entender cómo congela su evidencia en vivo y en histórico, **Then** puede
   hacerlo revisando solo el contenido de ese origen y el mecanismo
   compartido, sin leer el de los otros nueve.

---

### User Story 2 - Añadir un origen de evidencia nuevo (Priority: P2)

Quien mantiene el sistema de diagnóstico necesita incorporar un origen de
evidencia nuevo (como se ha hecho nueve veces ya) sin modificar el código de
ninguno de los orígenes ya existentes.

**Why this priority**: Es la garantía de que la partición resuelve el
problema hacia adelante, no solo hoy — el sistema seguirá creciendo con
nuevos orígenes.

**Independent Test**: Se puede probar incorporando un origen de evidencia de
prueba y comprobando que ningún fichero de los diez orígenes existentes
cambia como consecuencia — solo el mecanismo compartido (si el origen nuevo
lo necesita) y el propio origen nuevo.

**Acceptance Scenarios**:

1. **Given** los diez orígenes existentes ya organizados, **When** se añade
   un origen de evidencia nuevo, **Then** ningún origen existente requiere
   modificación para que el nuevo funcione.

---

### User Story 3 - Confirmar que no hay comportamiento observable roto (Priority: P3)

Quien mantiene el sistema de diagnóstico necesita confirmar que, tras
reorganizar el código, los consumidores actuales de la evidencia (el punto
que decide qué origen congelar según el episodio, la remediación de
contenedores que consulta evidencia en vivo, y la validación que rechaza una
hipótesis de causa probable que nombre un relay sin evidencia real) siguen
comportándose exactamente igual que antes.

**Why this priority**: Es la condición de "no romper nada" — sin ella el
refactor no es seguro de desplegar, aunque las otras dos historias se
cumplan.

**Independent Test**: Se puede probar ejecutando la suite de pruebas
existente antes y después del cambio y comprobando que el resultado (qué
pasa y qué falla) es idéntico.

**Acceptance Scenarios**:

1. **Given** el comportamiento actual de los consumidores de evidencia,
   **When** se completa la reorganización, **Then** ambos consumidores
   obtienen exactamente la misma evidencia, en la misma forma, que antes del
   cambio.
2. **Given** la suite de pruebas que hoy verifica los diez orígenes, **When**
   se ejecuta tras el cambio, **Then** verifica la misma cobertura por origen
   que antes, sin casos perdidos ni renombrados sin más.

---

### Edge Cases

- ¿Qué pasa con el mecanismo compartido (por ejemplo, conexión a la base de
  datos o inspección de Docker) que hoy usan varios orígenes a la vez? Debe
  seguir siendo accesible desde los diez sin duplicarse en cada uno y sin
  convertirse él mismo en un origen más. Qué función concreta cuenta como
  "compartida" se decide por uso real verificado (más de un origen la usa
  hoy), no por cómo suene su nombre — algo que hoy solo usa un origen no es
  compartido aunque parezca genérico.
- ¿Qué pasa si un origen nuevo necesita, además del mecanismo compartido
  existente, algo que hoy solo usa un origen concreto? Ese algo debe poder
  promocionarse al mecanismo compartido sin tocar el resto de orígenes ya
  existentes.
- ¿Qué pasa con los dos orígenes que no tienen variante histórica (agente y
  latido, que solo existen "en vivo")? La reorganización no debe forzarlos a
  tener una variante histórica que no existe de verdad.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE permitir identificar y revisar el
  comportamiento de cualquiera de los diez orígenes de evidencia sin
  necesidad de leer o ejecutar el código de otro origen.
- **FR-002**: El sistema DEBE seguir ofreciendo a los consumidores actuales
  (el punto de decisión que congela evidencia según el episodio, la
  remediación de contenedores, y la validación que rechaza una hipótesis de
  causa probable que nombre un relay sin evidencia real) exactamente el mismo
  comportamiento observable que antes del cambio.
- **FR-003**: El sistema DEBE permitir incorporar un origen de evidencia
  nuevo modificando únicamente el código de ese origen y, si aplica, el
  mecanismo compartido — nunca el código de un origen ya existente.
- **FR-004**: El mecanismo compartido entre orígenes (por ejemplo, conexión a
  la base de datos o inspección de Docker — la pertenencia exacta de cada
  función se decide por uso real verificado, no por su nombre) DEBE seguir
  siendo accesible desde los orígenes que de verdad lo necesiten, sin
  duplicarse en cada uno.
- **FR-005**: La suite de pruebas existente DEBE seguir verificando, tras el
  cambio, la misma cobertura por origen que verificaba antes, sin reducir ni
  renombrar sin más los casos existentes.
- **FR-006**: El sistema DEBE tratar el mecanismo compartido de FR-004 como
  una pieza explícitamente distinta de los diez orígenes, de la que estos
  dependen — nunca como un origen más. Modificar el mecanismo compartido no
  cuenta como "tocar otro origen" a efectos de FR-001 y FR-003, pero sí
  requiere atención porque afecta a más de un origen a la vez.
- **FR-007**: Los casos de prueba existentes DEBEN reorganizarse siguiendo la
  misma partición por origen que el código, de modo que FR-001 (revisar el
  comportamiento de un origen sin tocar el resto) se cumpla también para su
  verificación, y no solo para su código.

### Key Entities

- **Origen de evidencia**: un dominio de fallo que el sistema de diagnóstico
  vigila (contenedor, disco, Home Assistant, backup, relay, inventario, host
  externo, hub Beszel, agente, latido). Cada uno sabe congelar su propia
  evidencia en vivo y, salvo agente y latido, también en un momento pasado
  concreto (histórico).
- **Mecanismo compartido**: lo que dos o más orígenes usan de verdad hoy y no
  pertenece a ninguno en particular (por ejemplo, acceso a la base de datos
  de métricas). Qué entra aquí se decide comprobando el uso real de cada
  función, no por cómo de genérico suene su nombre — ver FR-004.
- **Consumidor**: quien usa la evidencia ya congelada de un origen, o
  consulta directamente el catálogo de nombres de un origen para validar
  otra cosa. Son tres: el punto que decide qué origen congelar según el
  episodio a diagnosticar; la remediación de contenedores, que consulta
  evidencia en vivo de un contenedor concreto; y la validación de hipótesis
  de causa probable, que consulta específicamente el catálogo de nombres de
  relay del origen "relay" para rechazar una hipótesis que nombre uno sin
  evidencia real en la ventana.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ninguna incorporación futura de un origen de evidencia nuevo
  requiere modificar el código de un origen ya existente — verificable
  revisando qué cambia en cada incorporación.
- **SC-002**: El 100% de los casos de prueba que hoy verifican el
  comportamiento de los diez orígenes sigue pasando tras el cambio, sin
  alterar su intención.
- **SC-003**: Revisar o verificar el comportamiento de un origen concreto no
  requiere inspeccionar más contenido que el de ese origen y el del mecanismo
  compartido — nunca el de otro origen.
- **SC-004**: Los tres consumidores actuales de la evidencia (el punto de
  decisión por episodio, la remediación de contenedores, y la validación de
  hipótesis que consulta el catálogo de nombres de relay) obtienen, antes y
  después del cambio, resultados idénticos ante los mismos casos.

## Assumptions

- Los diez orígenes de evidencia y el mecanismo compartido descritos en
  `REFACTOR-evidencia.md` (raíz del repo) son la partición correcta y
  completa a fecha de esta especificación; no se han detectado orígenes
  adicionales sin identificar.
- No existen más consumidores del comportamiento actual aparte de los tres
  documentados (el punto de decisión por episodio, la remediación de
  contenedores, y la validación de hipótesis que consulta el catálogo de
  nombres de relay).
- El cambio es puramente de organización interna: no añade ni retira ningún
  origen de evidencia hoy soportado, ni cambia lo que cada uno reporta.
- Los tres `_homelab_bridge.py` y su relación con
  `remediacion/deepseek_contenedores.py` quedan fuera de esta especificación
  — es un refactor distinto, ya identificado por separado.
