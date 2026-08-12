# Feature Specification: Generalizar el Diagnóstico a Home Assistant

**Feature Branch**: `010-diagnostico-ha`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (feature 007, generalizado a discos en 009) hoy no sabe diagnosticar nada de Home Assistant. Quiero que también pueda diagnosticar episodios de HA: cuando un check de `ha_monitor.py` sobre una entidad falla (batería, entidad no disponible, estado inesperado) o cuando falla el check del recorder de HA corrupto, quiero poder pedirle al motor que reúna la evidencia real alrededor de ese momento — para checks de entidad, el historial de esa entidad en el recorder de Home Assistant; para el recorder corrupto, los ficheros de corrupción y los logs del contenedor — y formule hipótesis de causa probable, con el mismo rigor que ya tiene para contenedores y discos: varias hipótesis contrastadas, nunca inventar una causa sin evidencia, el mismo límite de gasto diario compartido con el resto del motor. No existe hoy ningún incidente histórico real de ninguno de los dos tipos de check que usar como línea base (a diferencia de los 49 reinicios de `beszel` en 007) — la validación se apoya en `congelar --vivo` contra el estado sano actual de cada tipo, y contra cualquier episodio real que aparezca mientras se desarrolla. No incluye diagnosticar los episodios de la cerradura de la puerta (batería/conectividad): su causa ya se investigó a mano esta sesión y es un problema del dispositivo físico, no del homelab, así que no hay nada nuevo que validar ahí. No incluye generalizar a ningún otro origen de la Central de Alarmas (backups, relays, hosts externos, el hub de Beszel, agentes, inventario de cobertura) — eso queda para features posteriores, uno a uno. No incluye ninguna acción correctiva sobre HA, ni mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le diera superficie visible."

## Clarifications

### Session 2026-08-12

- Q: El check `ha_api` de `ha_monitor.py` (tipo `api_ping`, sin entidad
  asociada — hace ping directo a `/api/`) no encaja en ninguna de las
  dos categorías de evidencia que define FR-003 (checks de entidad vs.
  el check del recorder corrupto). ¿Este feature debe diagnosticar
  también episodios de `ha_api`, y con qué evidencia? → A: Sí, entra en
  el alcance de este feature; su evidencia son los logs recientes del
  contenedor `homeassistant` — el mismo mecanismo ya previsto para el
  check del recorder corrupto, sin fuente nueva que construir. Un fallo
  de `/api/` normalmente refleja un problema del propio proceso HA
  (caída, reinicio, cuelgue), no de una entidad concreta, así que no
  hay historial de recorder que consultar para este check.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo un episodio de entidad de Home Assistant (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna la
evidencia real del historial de una entidad de Home Assistant (batería,
disponibilidad, estado) y formule hipótesis de causa probable — igual
que ya puede hacer con un contenedor caído o un disco lleno — tanto si
hay un aviso activo de esa entidad ahora mismo como si quiere comprobar
una entidad que hoy está sana.

**Why this priority**: Es el valor central de este feature para el
origen HA, y el tipo de check más numeroso de `ha_monitor.py` (checks
de entidad). Sin esto, la promesa de "generalizar" no cubre el caso más
común de este origen.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquiera de los checks de entidad de HA y
comprobando que el resultado incluye evidencia real del historial de
esa entidad en el recorder de Home Assistant, no evidencia de
contenedor ni de disco ni un error.

**Acceptance Scenarios**:

1. **Given** un check de entidad de HA sin ningún aviso activo, **When**
   Miquel pide diagnosticarlo, **Then** el motor reúne su evidencia real
   (historial reciente de esa entidad en el recorder) y concluye "no se
   puede diagnosticar" sin inventar una causa — no hay nada que
   explicar.
2. **Given** un check de entidad de HA con un aviso activo, **When**
   Miquel pide diagnosticarlo, **Then** el motor reúne la evidencia real
   del historial de esa entidad alrededor de ese momento y formula
   hipótesis de causa probable, con el mismo rigor que ya exige para
   contenedores y discos.
3. **Given** cualquier episodio de entidad de HA diagnosticado, **When**
   se revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de contenedor o de disco — misma
   estructura, mismas garantías de la Central de Registro (Principio
   VIII).

---

### User Story 2 - Diagnosticar en vivo un episodio de recorder de HA corrupto (Priority: P2)

Miquel quiere poder pedirle al motor de diagnóstico que reúna la
evidencia real de una corrupción del recorder de Home Assistant
(ficheros de corrupción, logs del contenedor) y formule hipótesis de
causa probable, con la misma garantía de nunca inventar una causa sin
evidencia.

**Why this priority**: Depende del mismo mecanismo base que la Historia
1 (congelar episodio, formular hipótesis, registrar desenlace), pero
con una fuente de evidencia completamente distinta — no hay historial
de un valor numérico o de estado que consultar, solo la presencia de
ficheros de corrupción y logs. Menos urgente que la Historia 1 porque
es un solo check, no una familia de checks.

**Independent Test**: Se puede probar simulando una corrupción del
recorder (crear un fichero `*.corrupt.*` en el volumen del recorder,
mismo mecanismo ya usado para probar el check de `ha_monitor.py`) y
pidiendo un diagnóstico, comprobando que la evidencia reunida incluye
el fichero de corrupción y los logs del contenedor `homeassistant`.

**Acceptance Scenarios**:

1. **Given** el check del recorder de HA sin ningún fichero de
   corrupción presente, **When** Miquel pide diagnosticarlo, **Then**
   el motor concluye "no se puede diagnosticar" sin inventar una causa.
2. **Given** el check del recorder de HA con un fichero de corrupción
   presente, **When** Miquel pide diagnosticarlo, **Then** el motor
   reúne la evidencia real (fichero de corrupción, logs recientes del
   contenedor) y formula hipótesis de causa probable.

---

### User Story 3 - Diagnosticar un episodio de HA en diferido, reproduciblemente (Priority: P3)

Miquel quiere poder señalar un momento pasado concreto de un episodio
de HA (de cualquiera de los dos tipos) y diagnosticarlo más tarde,
obteniendo siempre la misma conclusión si repite el diagnóstico sobre
el mismo momento.

**Why this priority**: Depende de que el mecanismo en vivo (Historias 1
y 2) ya funcione — es la misma tubería aplicada a un momento pasado.
Menos urgente porque, a diferencia de los contenedores, hoy no existe
ningún incidente histórico real de HA con un registro reutilizable que
diagnosticar en diferido — se valida el mecanismo, no un caso real
todavía.

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado de un episodio de HA y comprobando que el diagnóstico
produce la misma conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado conocido de un episodio de HA, **When**
   Miquel pide diagnosticarlo en diferido, **Then** el motor reúne la
   evidencia real de ese momento (no la actual) y concluye igual que lo
   haría en vivo con esos mismos datos.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007 y 009).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un check de HA que no existe o no se
  vigila? El motor concluye que no se puede diagnosticar — mismo
  criterio que un contenedor o disco inexistente.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege los diagnósticos de contenedor y disco
  (feature 007, FR-009/FR-010) — un diagnóstico de HA cuenta contra el
  mismo límite, no contra uno aparte.
- ¿Qué pasa si el recorder de HA está corrupto justo en el momento en
  que se intenta consultar su historial para diagnosticar un check de
  entidad? El motor lo trata como evidencia insuficiente para ese
  episodio de entidad (no puede leer el historial) y lo dice
  explícitamente, sin inventar un historial ni fallar de forma opaca.
- ¿Qué pasa con los episodios de la cerradura (batería/conectividad)?
  Quedan fuera de alcance — su causa ya se investigó a mano y es un
  problema del dispositivo físico, no del homelab (ver Assumptions).
- ¿Qué pasa con el check `ha_api` (ping directo a la API de HA, sin
  entidad asociada)? Entra en el alcance de este feature — su evidencia
  son los logs recientes del contenedor `homeassistant`, el mismo
  mecanismo ya usado para el check del recorder corrupto, porque no hay
  una entidad concreta cuyo historial consultar (Clarifications
  2026-08-12, FR-003).
- ¿Qué pasa si no hay ningún incidente histórico real de HA disponible
  para validar el feature contra un caso conocido, a diferencia de
  `beszel` para contenedores? Se acepta como limitación conocida de
  este feature, igual que ya lo aceptó 009 para discos — la validación
  se apoya en diagnósticos en vivo contra el estado sano actual, y
  contra cualquier episodio real que aparezca mientras se desarrolla.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de HA como entrada,
  tanto en vivo (un check de `ha_monitor.py` en su estado actual) como
  en diferido (un momento pasado concreto de ese check) — mismas dos
  vías que ya existen para episodios de contenedor y disco.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  HA, congelar un snapshot de su evidencia en ese momento, con la misma
  garantía de reproducibilidad diferida que ya exige FR-002 de 007.
- **FR-003**: El sistema DEBE reunir evidencia real alrededor del
  momento del episodio antes de formular ninguna hipótesis, distinta
  según el tipo de check: para checks de entidad, el historial de esa
  entidad en el recorder de Home Assistant; para el check del recorder
  corrupto, los ficheros de corrupción presentes y los logs del
  contenedor `homeassistant`; para el check de disponibilidad de la API
  de HA (`ha_api`, sin entidad asociada), los logs recientes de ese
  mismo contenedor — no hay historial de recorder que consultar porque
  no hay una entidad concreta detrás de este check (Clarifications
  2026-08-12).
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de HA cuando la evidencia lo permita, con el
  mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de HA con
  exactamente uno de dos resultados — una causa probable con evidencia,
  o que no se puede diagnosticar — nunca presentar una causa sin
  evidencia que la respalde (mismo invariante que FR-007 de 007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de HA DEBE contar
  contra el mismo acumulado de gasto diario que ya protege a los
  diagnósticos de contenedor y disco — un único límite compartido para
  todo el motor, no uno aparte por origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre HA ni sobre ningún dispositivo físico, ni proponer una
  remediación nueva — mismo alcance estrictamente diagnóstico que 007 y
  009.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de HA en ningún sitio del dashboard — sigue siendo solo por línea de
  comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar episodios relacionados con
  la cerradura de la puerta (batería, conectividad) — su causa ya se
  investigó a mano y es un problema del dispositivo físico, fuera del
  alcance de este feature.
- **FR-011**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (backups, relays, hosts externos, el hub de
  Beszel, agentes, inventario) — el alcance de este feature se limita a
  contenedores y discos (ya existentes) y HA.

### Key Entities

- **Episodio de HA**: la misma entidad "Episodio" que 007/009 ya
  definen, generalizada para poder representar también un check de
  `ha_monitor.py` (de entidad, de disponibilidad de la API `ha_api`, o
  de recorder corrupto), no solo un contenedor o un disco — atributos
  relevantes: qué check, la ventana de tiempo, si es en vivo o en
  diferido, y el snapshot de evidencia congelado (distinto según el
  tipo de check).
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de HA.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de HA (en vivo
  ya congelado, o en diferido) produce el mismo `conclusion_tipo` las
  dos veces, el 100% de las veces que se prueba — mismo criterio que
  SC-001 de 007 y 009.
- **SC-002**: El 100% de los diagnósticos de HA con evidencia suficiente
  incluyen más de una hipótesis registrada con su comprobación.
- **SC-003**: El gasto real de los diagnósticos de HA, sumado al de los
  de contenedor y disco, nunca supera el límite diario configurado —
  verificable revisando el acumulado de cualquier día.
- **SC-004**: Diagnosticar en vivo cualquier check de HA sano (de
  entidad o de recorder) concluye "no se puede diagnosticar" sin
  inventar una causa, el 100% de las veces que se prueba.

## Assumptions

- No existe hoy ningún incidente histórico real de ningún tipo de check
  de HA con un registro reutilizable (equivalente a `restart_history`
  para contenedores) — ni para checks de entidad ni para el check de
  recorder corrupto, que además es un check nuevo (añadido el
  2026-08-11) sin ningún historial anterior a su propia existencia. Una
  primera versión de este material daba por bueno un incidente de
  recorder corrupto en `alarm_history.json` como línea base; resultó
  ser un artefacto de una prueba de integración (13 segundos entre
  aparición y resolución) y se ha eliminado del registro de producción.
  La validación de este feature se apoya en `congelar --vivo` contra el
  estado sano actual de cada tipo de check, y contra cualquier episodio
  real que aparezca mientras se desarrolla — misma limitación aceptada
  que ya tuvo 009 para discos.
- Los episodios de la cerradura de la puerta (batería, conectividad)
  quedan fuera de alcance: su causa ya se investigó a mano en una
  sesión anterior y es un problema de hardware/batería de un
  dispositivo físico (Nuki Smart Lock Ultra), no de infraestructura del
  homelab — diagnosticarlos con el motor no aportaría nada nuevo sobre
  lo que ya se sabe.
- El recorder de Home Assistant es fiable como fuente de evidencia
  desde el 2026-08-11 (fecha del fix que lo movió de un bind mount a un
  volumen Docker nativo); antes de esa fecha se corrompía
  periódicamente, así que la profundidad histórica hacia atrás del
  recorder es irregular por diseño, no un defecto de este feature.
- No existe hoy ningún concepto de "check de HA crítico" equivalente a
  la lista de contenedores críticos de 007 (`es_critico`) — igual que
  en 009, este feature no propone ninguna acción sobre nada (FR-008),
  así que no hace falta ese tratamiento especial todavía.
- Los otros 6 orígenes restantes de la Central de Alarmas (backups,
  relays, hosts externos, el hub de Beszel, agentes, inventario) quedan
  fuera de este feature — cada uno necesita su propia investigación de
  qué constituye evidencia real, igual que se hizo aquí para HA
  (`BRIEFING.md`, "Feature 010 — material de partida").
