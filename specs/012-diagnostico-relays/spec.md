# Feature Specification: Generalizar el Diagnóstico a los Relays

**Feature Branch**: `012-diagnostico-relays`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (feature 007, generalizado a discos en 009, a Home Assistant en 010 y a backups en 011) hoy no sabe diagnosticar nada de los relays `socat` del homelab. Quiero que también pueda diagnosticar episodios de relay: en vivo, cuando un relay concreto (de los 10 que vigila `dump_socat_status.py`) está caído ahora mismo, reuniendo su estado real de `socat_relays.json` (nombre, descripción, si responde); en diferido, señalando un momento pasado dentro del histórico real (`dashboard-socat.log`, sin rotación, con datos desde el 29 de abril), reuniendo la evidencia agregada de esa ventana — cuántos de los relays vigilados estaban caídos y durante cuánto tiempo, sin poder decir cuál concretamente, porque ese detalle no se archivó nunca. Quiero que formule hipótesis de causa probable con el mismo rigor que ya tiene para los demás orígenes: varias hipótesis contrastadas, nunca inventar una causa ni inventar qué relay concreto falló cuando esa información no existe, el mismo límite de gasto diario compartido con el resto del motor. A diferencia de discos, HA y backups, aquí sí existe una línea base real desde el arranque del feature: 17 episodios de fallo reales desde el 29 de abril, agrupando fallos consecutivos del log agregado, incluida una caída sostenida de unas 10 horas el 24 de mayo. No incluye recuperar qué relay concreto falló en un episodio ya pasado — esa información no se archivó y no se puede reconstruir. No incluye ampliar la vigilancia a los relays de Home Assistant que `dump_socat_status.py` no comprueba hoy (HEOS, Marantz, ESPHome, Android TV, Tapo) — eso es cobertura nueva, no diagnóstico, y queda fuera de este feature. No incluye ninguna acción correctiva sobre ningún relay ni su LaunchAgent. No incluye generalizar a ningún otro origen de la Central de Alarmas (hosts externos, el hub de Beszel, agentes, inventario de cobertura) — eso queda para features posteriores, uno a uno. No incluye ninguna acción correctiva, ni mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le diera superficie visible."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo un relay concreto (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna el
estado real de un relay `socat` concreto (de los 10 que vigila
`dump_socat_status.py`) y formule hipótesis de causa probable — igual
que ya puede hacer con un contenedor caído, un disco lleno, un check
de HA o un backup fallido — tanto si ese relay está caído ahora mismo
como si quiere comprobar que uno sano está sano de verdad.

**Why this priority**: Es el valor central de este feature — sin esto,
un relay caído sigue teniendo la misma explicación estática que ya
daba la Central de Alarmas (006), sin ninguna pista sobre la causa
concreta de esa caída.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquiera de los 10 relays vigilados y
comprobando que el resultado incluye su estado real (nombre,
descripción, si responde), no un texto genérico ni evidencia de otro
relay ni de otro origen.

**Acceptance Scenarios**:

1. **Given** un relay sin ningún fallo (responde con normalidad),
   **When** Miquel pide diagnosticarlo, **Then** el motor reúne su
   estado real y concluye "no se puede diagnosticar" sin inventar una
   causa — no hay nada que explicar.
2. **Given** un relay caído ahora mismo, **When** Miquel pide
   diagnosticarlo, **Then** el motor reúne su estado real (nombre,
   descripción del relay, que no responde) y formula hipótesis de
   causa probable, con el mismo rigor que ya exige para los demás
   orígenes.
3. **Given** cualquier episodio de relay diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de contenedor, disco, HA o
   backup — misma estructura, mismas garantías de la Central de
   Registro (Principio VIII).

---

### User Story 2 - Diagnosticar un momento pasado de los relays, reproduciblemente (Priority: P2)

Miquel quiere poder señalar un momento pasado concreto, dentro del
histórico real conservado (`dashboard-socat.log`, sin rotación, desde
el 29 de abril), y diagnosticarlo más tarde, obteniendo siempre la
misma conclusión si repite el diagnóstico sobre el mismo momento — con
evidencia agregada (cuántos relays estaban caídos, durante cuánto
tiempo), nunca inventando qué relay concreto falló.

**Why this priority**: Depende de que el mecanismo en vivo (Historia
1) ya funcione. Menos urgente porque el valor central del feature —
diagnosticar un relay caído ahora mismo— ya lo cubre la Historia 1;
esta añade la capacidad de investigar los 17 episodios reales ya
identificados.

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado (dentro del histórico real) y comprobando que el
diagnóstico produce la misma conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado dentro del histórico real conservado,
   **When** Miquel pide diagnosticarlo en diferido, **Then** el motor
   reúne la evidencia agregada real de esa ventana (cuántos relays
   vigilados estaban caídos, durante cuánto tiempo) y formula
   hipótesis de causa probable sin nombrar ningún relay concreto como
   la causa, porque esa información no existe para episodios pasados.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007, 009, 010 y 011).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un relay que no está entre los 10
  que vigila `dump_socat_status.py`? El motor concluye que no se puede
  diagnosticar — mismo criterio que un `check_id`/`label` inexistente
  en orígenes anteriores.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege los diagnósticos de contenedor, disco, HA
  y backup — un diagnóstico de relay cuenta contra el mismo límite, no
  contra uno aparte.
- ¿Qué pasa si en diferido se le pide al motor que diga qué relay
  concreto falló? No puede saberlo — la evidencia agregada del log
  histórico no guarda ese detalle (se sobreescribía cada ciclo en
  `socat_relays.json`, nunca archivado) — el motor lo declara
  explícitamente como parte de por qué no se puede diagnosticar con
  certeza, en vez de inventar un nombre de relay.
- ¿Qué pasa si el momento pedido en diferido cae fuera del rango real
  del histórico conservado (antes del 29 de abril de 2026, o en el
  futuro)? No hay evidencia que reunir — el motor concluye que no se
  puede diagnosticar, mismo criterio que un momento sin datos en
  cualquier otro origen.
- ¿Qué pasa con los relays de Home Assistant que `dump_socat_status.py`
  no vigila (HEOS, Marantz, ESPHome, Android TV, Tapo)? Quedan fuera de
  alcance — no existe ninguna señal calculada que leer para ellos;
  ampliarles la vigilancia es trabajo del Frente 1 (cobertura), no de
  este feature de diagnóstico.
- ¿Qué pasa si `dashboard-socat.log` sigue creciendo sin ninguna
  rotación? Se acepta como estado real de la infraestructura — este
  feature solo lee ese log, no gestiona su rotación ni su tamaño.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de relay como
  entrada, tanto en vivo (un relay concreto, de los 10 que vigila
  `dump_socat_status.py`, en su estado actual) como en diferido (un
  momento pasado concreto, dentro del histórico real conservado, sin
  nombrar ningún relay) — mismas dos vías que ya existen para los
  demás orígenes, con la asimetría real de que en diferido no se
  identifica ningún relay concreto (ver Assumptions).
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  relay, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007.
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis, distinta según el modo: en vivo, el estado actual
  del relay pedido (nombre, descripción, si responde); en diferido, el
  recuento agregado del histórico real en una ventana alrededor del
  momento pedido — cuántos de los relays vigilados estaban caídos y
  durante cuánto tiempo, nunca el detalle de cuál en concreto.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de relay cuando la evidencia lo permita, con
  el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de relay con
  exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una causa
  sin evidencia que la respalde, y nunca nombrar un relay concreto como
  causa de un episodio en diferido, porque esa evidencia no existe
  (mismo invariante que FR-007 de 007, con esta restricción adicional
  específica de este origen).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de relay DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a
  los diagnósticos de contenedor, disco, HA y backup — un único límite
  compartido para todo el motor, no uno aparte por origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ningún relay ni su LaunchAgent, ni proponer una remediación
  nueva — mismo alcance estrictamente diagnóstico que 007, 009, 010 y
  011.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de relay en ningún sitio del dashboard — sigue siendo solo por línea
  de comandos en este feature.
- **FR-010**: El sistema NO DEBE ampliar la vigilancia a ningún relay
  que `dump_socat_status.py` no compruebe hoy (los relays de Home
  Assistant como HEOS, Marantz, ESPHome, Android TV o Tapo) — este
  feature diagnostica lo que ya se vigila, no añade vigilancia nueva
  (Frente 1, fuera de alcance).
- **FR-011**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (hosts externos, el hub de Beszel, agentes,
  inventario) — el alcance de este feature se limita a contenedores,
  discos, HA y backups (ya existentes) y relays.

### Key Entities

- **Episodio de relay**: la misma entidad "Episodio" que 007/009/010/011
  ya definen, generalizada para poder representar también un relay
  `socat` vigilado por `dump_socat_status.py` — atributos relevantes:
  qué relay (en vivo) o qué momento (en diferido, ya que no hay ningún
  relay concreto que nombrar), la ventana de tiempo, si es en vivo o en
  diferido, y el snapshot de evidencia congelado — con detalle real por
  relay en vivo, agregado sin detalle por relay en diferido.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de relay.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de relay (en
  vivo ya congelado, o en diferido) produce el mismo `conclusion_tipo`
  las dos veces, el 100% de las veces que se prueba — mismo criterio
  que SC-001 de 007, 009, 010 y 011.
- **SC-002**: El 100% de los diagnósticos de relay con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de relay, sumado al de
  contenedor, disco, HA y backup, nunca supera el límite diario
  configurado — verificable revisando el acumulado de cualquier día.
- **SC-004**: Diagnosticar en vivo un relay sano concluye "no se puede
  diagnosticar" sin inventar una causa, el 100% de las veces que se
  prueba.
- **SC-005**: Diagnosticar en diferido al menos uno de los episodios
  reales ya identificados en el histórico conservado concluye una
  causa probable o "no se puede diagnosticar" honesto — nunca
  nombrando un relay concreto como causa — medido contra esa línea
  base real (Principio IX), la primera vez en este proyecto con una
  línea base real disponible desde el arranque del feature, sin la
  salvedad que necesitaron 009, 010 y 011.

## Assumptions

- **Asimetría real entre vivo y diferido, decidida con Miquel
  (2026-08-12)**: en vivo, la evidencia tiene detalle real por relay
  (`socat_relays.json`, sobreescrito cada 5 minutos con el estado
  actual de los 10 relays vigilados). En diferido, la evidencia es el
  recuento agregado de `dashboard-socat.log` (sin rotación, histórico
  real desde el 2026-04-29) — nunca el detalle de qué relay concreto
  falló, porque esa información se sobreescribía cada ciclo y nunca se
  archivó. El motor declara esta limitación explícitamente en vez de
  inventar un nombre de relay para un episodio pasado.
- **Línea base real disponible desde el arranque**, a diferencia de
  009, 010 y 011: 17 episodios de fallo reales identificados agrupando
  fallos consecutivos en el histórico conservado, desde parpadeos de
  un solo ciclo hasta una caída sostenida de unas 10 horas el
  2026-05-24. La validación de este feature se apoya en esta línea
  base real, no solo en `congelar --vivo` contra el estado sano actual.
- Los relays de Home Assistant que `dump_socat_status.py` no vigila
  hoy (HEOS, Marantz ×3, ESPHome sal/toldos, Android TV ×2, Tapo ×3)
  quedan fuera de alcance: no existe ninguna señal calculada que leer
  para ellos — ampliarles la vigilancia es trabajo del Frente 1
  (Principio XIII), no de este feature de diagnóstico.
- No existe ningún concepto de "relay crítico" equivalente a la lista
  de contenedores críticos de 007 — igual que en 009, 010 y 011, este
  feature no propone ninguna acción sobre nada, así que no hace falta
  ese tratamiento especial.
- Los otros 4 orígenes restantes de la Central de Alarmas (hosts
  externos, el hub de Beszel, agentes, inventario) quedan fuera de
  este feature — cada uno necesita su propia investigación de qué
  constituye evidencia real, igual que se hizo aquí para relays
  (`BRIEFING.md`, "Feature 012 — material de partida").
