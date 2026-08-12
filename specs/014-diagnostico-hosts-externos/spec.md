# Feature Specification: Generalizar el Diagnóstico a los Hosts Externos

**Feature Branch**: `014-diagnostico-hosts-externos`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (007, generalizado a discos en 009, HA en 010, backups en 011, relays en 012 e inventario en 013) hoy no sabe diagnosticar nada de los hosts físicos externos que Beszel ya vigila — el host de Uptime Kuma y el de AdGuard Home (DNS primario), la infraestructura de observabilidad del propio homelab, distinta del Mac Mini. Quiero que también pueda diagnosticar episodios de host externo: en vivo, leyendo el estado ya calculado por el dashboard (arriba/caído/sin evidencia, con su misma política de frescura); en diferido, señalando un momento pasado y consultando directamente la base de datos del hub de Beszel para ver si ese host seguía reportando datos de rendimiento en esa ventana — sin inventar un estado \"caído\" que la propia evidencia no sostenga si solo hay ausencia de muestras, nunca un registro explícito de caída. Mismo rigor que los demás orígenes: varias hipótesis contrastadas, nunca inventar una causa, mismo límite de gasto diario compartido. No incluye diagnosticar el propio hub de Beszel (si deja de reportar sobre todos sus sistemas a la vez) — eso es otro origen, con otra investigación pendiente. No incluye ninguna acción correctiva sobre Beszel ni sobre los hosts. No incluye generalizar a los 2 orígenes restantes de la Central de Alarmas (el hub de Beszel, agentes). No incluye mostrar este diagnóstico en el dashboard — sigue siendo solo por línea de comandos."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo el estado actual de un host externo (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna el
estado real, ya calculado, de uno de los dos hosts físicos externos
que Beszel vigila (Uptime Kuma, AdGuard Home) y formule hipótesis de
causa probable — igual que ya puede hacer con un contenedor caído, un
disco lleno, un check de HA, un backup fallido, un relay caído o una
brecha de inventario.

**Why this priority**: Es el valor central de este feature — sin
esto, un host externo caído sigue teniendo la misma explicación
estática que ya da la Central de Alarmas (006), sin ninguna pista
sobre la causa concreta.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquiera de los 2 hosts vigilados y
comprobando que el resultado incluye su estado real (arriba, caído, o
sin evidencia), no un texto genérico ni evidencia del otro host.

**Acceptance Scenarios**:

1. **Given** un host sin ningún fallo (Beszel lo reporta "arriba"),
   **When** Miquel pide diagnosticarlo, **Then** el motor reúne su
   estado real y concluye "no se puede diagnosticar" sin inventar una
   causa — no hay nada que explicar.
2. **Given** un host caído o sin evidencia reciente, **When** Miquel
   pide diagnosticarlo, **Then** el motor reúne su estado real (el ya
   calculado por el mecanismo existente, con la misma política de
   frescura) y formula hipótesis de causa probable, con el mismo rigor
   que ya exige para los demás orígenes.
3. **Given** cualquier episodio de host externo diagnosticado, **When**
   se revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de cualquier otro origen —
   misma estructura, mismas garantías de la Central de Registro
   (Principio VIII).

---

### User Story 2 - Diagnosticar un momento pasado de un host externo, reproduciblemente (Priority: P2)

Miquel quiere poder señalar un momento pasado concreto y diagnosticar
si un host externo seguía reportando datos de rendimiento en una
ventana alrededor de ese momento, obteniendo siempre la misma
conclusión si repite el diagnóstico sobre el mismo momento — sin que
la mera ausencia de muestras se presente como prueba de que el host
estaba caído, porque puede deberse a otras causas (el propio agente de
monitorización, la red entre el hub y el host, el hub mismo).

**Why this priority**: Depende de que el mecanismo en vivo (Historia
1) ya funcione. Menos urgente porque el valor central del feature —
diagnosticar un host caído ahora mismo— ya lo cubre la Historia 1;
esta añade la capacidad de investigar episodios ya pasados, incluida
una avería real ya documentada e independientemente explicada
(routing roto de contenedores tras un reinicio, del 30 de julio al 7
de agosto de 2026).

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado y comprobando que el diagnóstico produce la misma
conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado concreto, **When** Miquel pide
   diagnosticarlo en diferido, **Then** el motor reúne la evidencia
   real de si el host reportaba datos de rendimiento en una ventana
   alrededor de ese momento y formula hipótesis de causa probable, sin
   presentar la mera ausencia de muestras como un hecho probado de que
   el host estaba caído.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007, 009, 010, 011, 012 y 013).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un host que no es ninguno de los 2
  vigilados (Uptime Kuma, AdGuard Home)? El motor concluye que no se
  puede diagnosticar — mismo criterio que un `check_id`/`label`/nombre
  de relay/componente de inventario inexistente en orígenes anteriores.
- ¿Qué pasa si el estado en vivo es "sin evidencia" (el propio
  mecanismo que lo calcula está caducado o sin latido reciente)? Es
  evidencia real por derecho propio — el motor la reúne igual y puede
  formular hipótesis sobre por qué la vigilancia misma quedó sin datos
  frescos, sin confundirlo con "el host está caído".
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege a los demás orígenes — un diagnóstico de
  host externo cuenta contra el mismo límite, no contra uno aparte.
- ¿Qué pasa si en diferido no hay ninguna muestra en la ventana, en
  ninguna resolución de retención? El motor lo declara honestamente
  como ausencia de datos — nunca como "host caído confirmado", porque
  esa conclusión exigiría descartar otras causas posibles (fallo del
  agente de Beszel en ese host, fallo de red entre el hub y el host, el
  propio hub sin registrar) que el motor no puede comprobar con esta
  evidencia.
- ¿Qué pasa si el momento pedido en diferido cae fuera del rango real
  conservado por el hub de Beszel? No hay evidencia que reunir — el
  motor concluye que no se puede diagnosticar, mismo criterio que un
  momento sin datos en cualquier otro origen.
- ¿Qué pasa si la consulta al hub de Beszel falla (Docker no
  disponible, el volumen no existe)? No es un error — el episodio se
  congela igual, con evidencia vacía, mismo criterio que una llamada
  de solo lectura fallida en cualquier otro origen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de host externo como
  entrada, tanto en vivo (uno de los 2 hosts vigilados, en su estado
  actual) como en diferido (un momento pasado concreto, para uno de
  los 2 hosts) — mismas dos vías que ya existen para los demás
  orígenes.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  host externo, congelar un snapshot de su evidencia en ese momento,
  con la misma garantía de reproducibilidad diferida que ya exige
  FR-002 de 007.
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis, distinta según el modo: en vivo, el estado ya
  calculado del host (arriba/caído/sin evidencia, con la misma
  política de frescura ya usada por el mecanismo existente); en
  diferido, si el host tenía muestras de rendimiento registradas en
  una ventana alrededor del momento pedido.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de host externo cuando la evidencia lo
  permita, con el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de host
  externo con exactamente uno de dos resultados — una causa probable
  con evidencia, o que no se puede diagnosticar — nunca presentar una
  causa sin evidencia que la respalde (mismo invariante que FR-007 de
  007).
- **FR-006a**: El sistema NO DEBE presentar la ausencia de muestras de
  rendimiento en una ventana como prueba concluyente de que el host
  estaba caído — debe describirla como lo que es (sin datos en esa
  ventana) y dejar abiertas, si la evidencia no permite descartarlas,
  otras causas posibles (fallo del agente de monitorización en ese
  host, fallo de red entre el hub y el host, el propio hub sin
  registrar).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de host externo
  DEBE contar contra el mismo acumulado de gasto diario que ya protege
  a los demás orígenes — un único límite compartido para todo el
  motor, no uno aparte por origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ningún host externo, sobre Beszel, ni proponer una remediación
  nueva — mismo alcance estrictamente diagnóstico que los demás
  orígenes.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de host externo en ningún sitio del dashboard — sigue siendo solo
  por línea de comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar el propio hub de Beszel
  (si deja de reportar sobre todos sus sistemas a la vez) — ese es un
  origen distinto de la Central de Alarmas, con su propia evidencia
  pendiente de investigar.
- **FR-011**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (agentes) — el alcance de este feature se limita
  a contenedores, discos, HA, backups, relays e inventario (ya
  existentes) y hosts externos.

### Key Entities

- **Episodio de host externo**: la misma entidad "Episodio" que
  007/009/010/011/012/013 ya definen, generalizada para poder
  representar también un host físico externo vigilado por Beszel —
  atributos relevantes: qué host (nombre canónico, en vivo o en
  diferido), el momento o la ventana, si es en vivo o en diferido, y
  el snapshot de evidencia congelado — con el estado ya calculado en
  vivo, con presencia/ausencia de muestras de rendimiento en diferido.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de host externo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de host externo
  (en vivo ya congelado, o en diferido) produce el mismo
  `conclusion_tipo` las dos veces, el 100% de las veces que se prueba
  — mismo criterio que SC-001 de 007, 009, 010, 011, 012 y 013.
- **SC-002**: El 100% de los diagnósticos de host externo con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de host externo, sumado
  al del resto de orígenes, nunca supera el límite diario configurado
  — verificable revisando el acumulado de cualquier día.
- **SC-004**: Diagnosticar en vivo un host sano (arriba) concluye "no
  se puede diagnosticar" sin inventar una causa, el 100% de las veces
  que se prueba.
- **SC-005**: Diagnosticar en diferido un momento dentro de la avería
  real ya documentada (routing de contenedores roto del 2026-07-30 al
  2026-08-07, la misma que describe el `CLAUDE.md` general del
  homelab) concluye una causa probable o "no se puede diagnosticar"
  honesto — medido contra esa línea base real, con causa raíz ya
  conocida de forma independiente (Principio IX), la primera vez en
  este proyecto con una causa raíz externa ya documentada, no solo con
  el hecho de que el episodio existió.

## Assumptions

- **Los 2 hosts en alcance son exactamente los que ya vigila
  `beszel_hosts_monitor.py`/el dashboard** ("Host de Uptime Kuma",
  "Host de AdGuard Home (DNS primario)") — mismos nombres canónicos ya
  usados en tres sitios del sistema existente (el propio monitor, el
  dashboard, el inventario de cobertura). Ningún host nuevo que
  vigilar — eso es cobertura (Frente 1), no diagnóstico.
- **La evidencia en vivo es el estado ya calculado, no recalculado**:
  el motor lee el mismo veredicto (arriba/caído/sin evidencia, con la
  misma política de frescura) que ya usa el mecanismo existente —
  mismo criterio que ya se aplicó al `ha_check_status` de HA (010): no
  tiene sentido que el motor vuelva a decidir algo que ya está
  decidido con la misma fuente de datos.
- **La evidencia en diferido es presencia/ausencia de muestras de
  rendimiento, nunca un registro explícito de "caído"**: no existe
  ningún registro histórico de estado por host (ni en los logs del
  propio mecanismo, comprobado en vivo, ni en las tablas de alertas de
  Beszel, vacías hoy) — la única señal histórica real es si el host
  seguía enviando datos de rendimiento a Beszel. Ausencia de muestras
  es evidencia real, pero no concluyente por sí sola (FR-006a).
- **Línea base real disponible desde el arranque, con causa raíz ya
  conocida** — a diferencia de todos los orígenes anteriores (009-013),
  aquí no solo se sabe *que* hubo una avería real, sino *por qué*: el
  routing roto de contenedores del 30 de julio al 7 de agosto de 2026,
  ya documentado y resuelto en el `CLAUDE.md` general del homelab. La
  validación de este feature se apoya en esa avería real, no solo en
  `--vivo` contra el estado sano actual.
- No existe ningún concepto de "host crítico" equivalente a la lista de
  contenedores críticos de 007 — igual que en 009-013, este feature no
  propone ninguna acción sobre nada, así que no hace falta ese
  tratamiento especial.
- Los otros 2 orígenes restantes de la Central de Alarmas (el hub de
  Beszel, agentes) quedan fuera de este feature — cada uno necesita su
  propia investigación de qué constituye evidencia real, igual que se
  hizo aquí para hosts externos (`BRIEFING.md`, "Feature 014 —
  material de partida").
