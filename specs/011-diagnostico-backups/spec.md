# Feature Specification: Generalizar el Diagnóstico a los Backups

**Feature Branch**: `011-diagnostico-backups`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (feature 007, generalizado a discos en 009 y a Home Assistant en 010) hoy no sabe diagnosticar nada de los backups del homelab. Quiero que también pueda diagnosticar episodios de backup: cuando el rsync nocturno (`backup_diario_nvme.sh`) falla o queda parcial, o cuando algún dump de base de datos del catálogo de `verify_backups.py` falla o queda atrasado, quiero poder pedirle al motor que reúna la evidencia real de esa ejecución — el log completo de esa noche, con el estado de cada dump y el código de rsync ya interpretado — y formule hipótesis de causa probable, con el mismo rigor que ya tiene para contenedores, discos y HA: varias hipótesis contrastadas, nunca inventar una causa sin evidencia, el mismo límite de gasto diario compartido con el resto del motor. A diferencia de HA y discos, aquí la evidencia es texto libre (un log por ejecución), no una tabla ni una API, y la retención es de solo 7 días — el diagnóstico en diferido solo puede mirar dentro de esa ventana. No existe hoy ningún incidente real dentro de esos 7 días que usar como línea base — los 8 logs retenidos están todos limpios; el incidente real conocido (huérfanos root del 27-07) ya cayó fuera de la ventana de retención — la validación se apoya en `congelar --vivo` contra el estado sano actual y contra cualquier fallo real que aparezca mientras se desarrolla. No incluye los backups automáticos de Home Assistant como caso aparte: su frescura ya la diagnostica el feature 010 (`ha_backup_reciente`), y que sobrevivan al rsync ya lo cubre este mismo mecanismo sin tratamiento especial. No incluye ejecutar ningún backup nuevo, tocar `backup_diario_nvme.sh`, ni ninguna acción sobre `/Volumes/Storage/backup/`. No incluye generalizar a ningún otro origen de la Central de Alarmas (relays, hosts externos, el hub de Beszel, agentes, inventario de cobertura) — eso queda para features posteriores, uno a uno. No incluye ninguna acción correctiva, ni mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le diera superficie visible."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo el backup más reciente (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna la
evidencia real de la última ejecución del backup nocturno (el log
completo de esa noche: dumps de base de datos, salida de rsync, código
ya interpretado) y formule hipótesis de causa probable — igual que ya
puede hacer con un contenedor caído, un disco lleno o un check de HA —
tanto si el backup de anoche falló como si quiere comprobar que uno
sano está sano de verdad.

**Why this priority**: Es el valor central de este feature — sin esto,
un fallo real del backup nocturno sigue teniendo la misma explicación
estática que ya daba la Central de Alarmas (006), sin ninguna pista
sobre la causa concreta de esa noche.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo del backup más reciente y comprobando que el
resultado incluye evidencia real de ese log concreto (dumps, rsync,
duración), no un texto genérico ni evidencia de otro origen.

**Acceptance Scenarios**:

1. **Given** el log de backup más reciente sin ningún fallo (rsync
   completo, todos los dumps correctos), **When** Miquel pide
   diagnosticarlo, **Then** el motor reúne su evidencia real y concluye
   "no se puede diagnosticar" sin inventar una causa — no hay nada que
   explicar.
2. **Given** el log de backup más reciente con algún fallo real (rsync
   parcial, o algún dump de base de datos fallido), **When** Miquel
   pide diagnosticarlo, **Then** el motor reúne la evidencia real de
   esa ejecución y formula hipótesis de causa probable, con el mismo
   rigor que ya exige para contenedores, discos y HA.
3. **Given** cualquier episodio de backup diagnosticado, **When** se
   revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de contenedor, disco o HA —
   misma estructura, mismas garantías de la Central de Registro
   (Principio VIII).

---

### User Story 2 - Diagnosticar un backup pasado, reproduciblemente (Priority: P2)

Miquel quiere poder señalar un momento pasado concreto, dentro de los
últimos 7 días (la ventana real de logs retenidos), y diagnosticarlo
más tarde, obteniendo siempre la misma conclusión si repite el
diagnóstico sobre el mismo momento.

**Why this priority**: Depende de que el mecanismo en vivo (Historia 1)
ya funcione — es la misma tubería aplicada a un log ya escrito. Menos
urgente porque, a diferencia de contenedores, hoy no existe ningún
incidente real dentro de la ventana de 7 días con el que validar el
diagnóstico en diferido contra un caso conocido.

**Independent Test**: Se puede probar señalando dos veces el mismo
momento pasado (dentro de los 7 días retenidos) y comprobando que el
diagnóstico produce la misma conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** un momento pasado dentro de la ventana de 7 días
   retenidos, **When** Miquel pide diagnosticarlo en diferido, **Then**
   el motor reúne la evidencia real del log de esa noche (no la del
   backup más reciente) y concluye igual que lo haría en vivo con esos
   mismos datos.
2. **Given** el mismo momento pasado, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007, 009 y 010).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar un momento sin ningún log retenido
  (fuera de la ventana de 7 días, o antes del primer backup)? El motor
  concluye que no se puede diagnosticar — mismo criterio que un
  episodio inexistente en 007/009/010.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege los diagnósticos de contenedor, disco y HA
  — un diagnóstico de backup cuenta contra el mismo límite, no contra
  uno aparte.
- ¿Qué pasa si rsync devuelve el código 24 (algún fichero desapareció
  durante la copia, en un sistema vivo)? El propio
  `backup_diario_nvme.sh` ya lo clasifica como éxito ("rsync
  completo") — el motor hereda ese mismo criterio, no lo trata como un
  fallo a explicar.
- ¿Qué pasa si el rsync general tuvo éxito pero algún dump de base de
  datos individual falló? Es evidencia real dentro del mismo log — el
  motor la ve igual que cualquier otro dato de esa ejecución, sin
  necesidad de un tipo de episodio distinto.
- ¿Qué pasa con los backups automáticos de Home Assistant? Quedan
  fuera de alcance como caso aparte: su frescura ya la diagnostica el
  feature 010 (`ha_backup_reciente`), y que sobrevivan al rsync
  nocturno ya lo cubre este mismo mecanismo genérico — comprobado que
  su carpeta no está en la lista de exclusiones del rsync (ver
  Assumptions).
- ¿Qué pasa si no hay ningún incidente histórico real disponible para
  validar el feature contra un caso conocido? Se acepta como
  limitación conocida de este feature, igual que ya lo aceptaron 009 y
  010 — la validación se apoya en diagnósticos en vivo contra el
  estado sano actual, y contra cualquier fallo real que aparezca
  mientras se desarrolla.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de backup como
  entrada, tanto en vivo (el log de la ejecución más reciente de
  `backup_diario_nvme.sh`) como en diferido (un log de una ejecución
  pasada, dentro de la ventana de retención real) — mismas dos vías
  que ya existen para episodios de contenedor, disco y HA.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  backup, congelar un snapshot de su evidencia en ese momento, con la
  misma garantía de reproducibilidad diferida que ya exige FR-002 de
  007.
- **FR-003**: El sistema DEBE reunir evidencia real del log completo de
  esa ejecución antes de formular ninguna hipótesis — el estado de
  cada dump de base de datos, la salida de rsync, el código de rsync
  ya interpretado por el propio script, y la duración de la ejecución.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de backup cuando la evidencia lo permita, con
  el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de backup con
  exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una causa
  sin evidencia que la respalde (mismo invariante que FR-007 de 007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de backup DEBE
  contar contra el mismo acumulado de gasto diario que ya protege a los
  diagnósticos de contenedor, disco y HA — un único límite compartido
  para todo el motor, no uno aparte por origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre el backup ni sobre `/Volumes/Storage/backup/`, ni proponer una
  remediación nueva — mismo alcance estrictamente diagnóstico que 007,
  009 y 010. En particular, NO DEBE tocar `backup_diario_nvme.sh` de
  ninguna forma ni ejecutar un backup nuevo.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de backup en ningún sitio del dashboard — sigue siendo solo por
  línea de comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (relays, hosts externos, el hub de Beszel,
  agentes, inventario) — el alcance de este feature se limita a
  contenedores, discos y HA (ya existentes) y backups.

### Key Entities

- **Episodio de backup**: la misma entidad "Episodio" que 007/009/010
  ya definen, generalizada para poder representar también una
  ejecución nocturna de `backup_diario_nvme.sh`, no solo un
  contenedor, un disco o un check de HA — atributos relevantes: qué
  ejecución (identificada por el momento en que corrió), la ventana de
  tiempo, si es en vivo o en diferido, y el snapshot de evidencia
  congelado — el contenido completo del log de esa noche, a diferencia
  de los orígenes anteriores, que leen de una tabla o una API.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de backup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de backup (en
  vivo ya congelado, o en diferido) produce el mismo `conclusion_tipo`
  las dos veces, el 100% de las veces que se prueba — mismo criterio
  que SC-001 de 007, 009 y 010.
- **SC-002**: El 100% de los diagnósticos de backup con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de backup, sumado al
  de contenedor, disco y HA, nunca supera el límite diario configurado
  — verificable revisando el acumulado de cualquier día.
- **SC-004**: Diagnosticar en vivo un backup sano (rsync completo, sin
  ningún dump fallido) concluye "no se puede diagnosticar" sin
  inventar una causa, el 100% de las veces que se prueba.

## Assumptions

- No existe hoy ningún incidente real dentro de la ventana de 7 días
  de retención que usar como línea base — los 8 logs reales retenidos
  al escribir este documento (5–12 de agosto de 2026) están todos
  limpios. El incidente real conocido (ficheros huérfanos por un
  `sudo` indebido, 2026-07-27) ya cayó fuera de esa ventana. La
  validación de este feature se apoya en `congelar --vivo` contra el
  estado sano actual, y contra cualquier fallo real que aparezca
  mientras se desarrolla — misma limitación aceptada que ya tuvieron
  009 y 010.
- Un episodio de backup se identifica por el log completo de una
  ejecución nocturna — una noche es un episodio, no cada uno de los
  ~12 checks de `verify_backups.py` por separado. A diferencia de HA,
  aquí no existe un registro de checks con identificador propio sobre
  el que dividir episodios; el log de cada ejecución ya es la unidad
  natural, y todas las comprobaciones de esa noche (dumps de base de
  datos, rsync) son evidencia dentro del mismo episodio, no episodios
  distintos.
- La ventana de retención real de los logs de backup es de 7 días
  (`RETENTION_DAYS` en `backup_diario_nvme.sh`), notablemente más
  corta que los 30 días de `container_metrics`/`disk_metrics` — el
  diagnóstico en diferido solo puede alcanzar hasta donde llegue esa
  retención real.
- No existe ningún concepto de "backup crítico" equivalente a la lista
  de contenedores críticos de 007 — igual que en 009 y 010, este
  feature no propone ninguna acción sobre nada, así que no hace falta
  ese tratamiento especial.
- Los backups automáticos de Home Assistant no reciben ningún
  tratamiento aparte en este feature: su frescura ya la diagnostica el
  feature 010 (`ha_backup_reciente`), y que sobrevivan al rsync
  nocturno ya lo cubre este mismo mecanismo genérico — comprobado que
  `docker/homeassistant/backups/` no está en la lista de exclusiones
  de `backup_diario_nvme.sh`.
- Los otros 5 orígenes restantes de la Central de Alarmas (relays,
  hosts externos, el hub de Beszel, agentes, inventario) quedan fuera
  de este feature — cada uno necesita su propia investigación de qué
  constituye evidencia real, igual que se hizo aquí para backups
  (`BRIEFING.md`, "Feature 011 — material de partida").
