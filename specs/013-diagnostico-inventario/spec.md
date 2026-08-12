# Feature Specification: Generalizar el Diagnóstico al Inventario de Cobertura

**Feature Branch**: `013-diagnostico-inventario`

**Created**: 2026-08-12

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios (feature 007, generalizado a discos en 009, a Home Assistant en 010, a backups en 011 y a relays en 012) hoy no sabe diagnosticar nada del propio inventario de cobertura del homelab — el sistema que audita, componente a componente, si tiene un estado esperado declarado, si se vigila y si un fallo llegaría al dashboard. Quiero que también pueda diagnosticar episodios de inventario: cuando aparece una brecha de cobertura real — un componente que se queda sin declaración, sin vigilancia, o cuyo fallo no llegaría al dashboard — quiero poder pedirle al motor que reúna la evidencia real de ese momento, tanto en vivo como en un punto pasado concreto ya registrado en el histórico del inventario, y formule hipótesis de causa probable con el mismo rigor que ya tiene para los demás orígenes: varias hipótesis contrastadas, nunca inventar una causa sin evidencia, el mismo límite de gasto diario compartido con el resto del motor. No incluye diagnosticar el tipo de brecha \"condición incumplida\" de una entidad de Home Assistant: ese tipo concreto es el propio inventario re-detectando un fallo que el origen de Home Assistant (feature 010) ya diagnostica, así que no aporta nada nuevo validarlo aquí también. No incluye ninguna acción correctiva sobre ninguna brecha (declarar un estado esperado nuevo, añadir vigilancia, etc.). No incluye generalizar a ningún otro origen de la Central de Alarmas (hosts externos, el hub de Beszel, agentes) — eso queda para features posteriores, uno a uno. No incluye mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le diera superficie visible."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnosticar en vivo una brecha de cobertura activa (Priority: P1)

Miquel quiere poder pedirle al motor de diagnóstico que reúna la
evidencia real de una brecha de cobertura activa ahora mismo —un
componente sin declaración, sin vigilancia, cuyo fallo no llegaría al
dashboard, o un canal de entrega con riesgo concentrado— y formule
hipótesis de causa probable, igual que ya puede hacer con un
contenedor caído, un disco lleno, un check de HA, un backup fallido o
un relay caído.

**Why this priority**: Es el valor central de este feature — sin
esto, una brecha de cobertura sigue teniendo la misma explicación
estática que ya da la Central de Alarmas (006), sin ninguna pista
sobre por qué el propio sistema de monitorización perdió esa
declaración, esa vigilancia o esa llegada al dashboard.

**Independent Test**: Se puede probar por completo pidiendo un
diagnóstico en vivo de cualquier brecha activa de tipo
`sin_declaracion`, `declaracion_caducada`, `sin_vigilancia`,
`no_llega_a_dashboard` o `riesgo_concentrado_telegram`, y comprobando
que el resultado incluye su evidencia real (qué componente, qué tipo
de brecha, desde cuándo), no un texto genérico ni evidencia de otro
componente ni de otro origen.

**Acceptance Scenarios**:

1. **Given** el inventario sin ninguna brecha activa de los 5 tipos en
   alcance, **When** Miquel pide diagnosticar el estado actual,
   **Then** el motor concluye "no se puede diagnosticar" sin inventar
   una causa — no hay nada que explicar.
2. **Given** un componente con una brecha activa de uno de los 5 tipos
   en alcance, **When** Miquel pide diagnosticarlo, **Then** el motor
   reúne su evidencia real (componente, categoría, tipo de brecha,
   contexto) y formula hipótesis de causa probable, con el mismo rigor
   que ya exige para los demás orígenes.
3. **Given** cualquier episodio de inventario diagnosticado, **When**
   se revisa el registro resultante, **Then** queda igual de legible
   después que un registro de episodio de contenedor, disco, HA,
   backup o relay — misma estructura, mismas garantías de la Central
   de Registro (Principio VIII).

---

### User Story 2 - Diagnosticar en diferido una ejecución pasada del inventario, reproduciblemente (Priority: P2)

Miquel quiere poder señalar una ejecución pasada concreta del
inventario, dentro del histórico ya registrado, y diagnosticar una
brecha que existió en ese momento, obteniendo siempre la misma
conclusión si repite el diagnóstico sobre la misma ejecución — con la
evidencia de qué cambió entre esa ejecución y la anterior en la que el
componente todavía no tenía esa brecha.

**Why this priority**: Depende de que el mecanismo en vivo (Historia
1) ya funcione. Menos urgente porque el valor central del feature —
diagnosticar una brecha activa ahora mismo— ya lo cubre la Historia 1;
esta añade la capacidad de investigar las brechas reales ya
identificadas en el histórico del inventario, con su causa y
resolución ya conocidas.

**Independent Test**: Se puede probar señalando dos veces la misma
ejecución pasada y comprobando que el diagnóstico produce la misma
conclusión las dos veces.

**Acceptance Scenarios**:

1. **Given** una ejecución pasada del inventario donde un componente
   tenía una brecha activa de uno de los 5 tipos en alcance, **When**
   Miquel pide diagnosticarla en diferido, **Then** el motor reúne la
   evidencia real de esa ejecución (el hallazgo del componente en ese
   momento) más lo que cambió respecto a la ejecución inmediatamente
   anterior en la que ese componente no tenía la brecha, y formula
   hipótesis de causa probable.
2. **Given** la misma ejecución pasada, **When** se diagnostica una
   segunda vez, **Then** produce el mismo `conclusion_tipo` que la
   primera (Principio XI, mismo criterio que ya exige FR-002/SC-001 de
   007, 009, 010, 011 y 012).

---

### Edge Cases

- ¿Qué pasa si se pide diagnosticar una brecha de tipo
  `condicion_incumplida`? El motor concluye que no se puede
  diagnosticar por estar fuera de alcance — ese tipo de brecha solo
  ocurre hoy en componentes `entidad_ha` y es el propio inventario
  re-detectando, con otras palabras, un fallo que el origen `ha`
  (feature 010) ya diagnostica; mismo criterio que ya excluyó los
  backups de HA en el origen `backups` (011).
- ¿Qué pasa si se pide diagnosticar un componente o una ejecución que
  no existen en `inventario.db`? El motor concluye que no se puede
  diagnosticar — mismo criterio que un `check_id`/`label`/relay
  inexistente en orígenes anteriores.
- ¿Qué pasa con el límite de gasto diario? Es el mismo acumulado
  compartido que ya protege los diagnósticos de contenedor, disco, HA,
  backup y relay — un diagnóstico de inventario cuenta contra el mismo
  límite, no contra uno aparte.
- ¿Qué pasa si en diferido no existe una ejecución anterior en la que
  el componente todavía no tuviera la brecha (por ejemplo, es la
  primera ejecución registrada)? El motor reúne solo el hallazgo de
  esa ejecución, sin comparación, y lo declara explícitamente en vez
  de inventar un "antes" que no se registró.
- ¿Qué pasa si se pide diagnosticar una brecha de tipo
  `declaracion_caducada`? Se acepta como tipo en alcance, pero hoy no
  existe ningún caso real: los 859 componentes con `last_reviewed_at`
  están todos fechados a 2026-08-08, y el umbral de caducidad son 90
  días, así que el primer caso real no puede aparecer antes de
  aproximadamente el 2026-11-06 (ver Assumptions) — el motor debe
  poder diagnosticarlo si aparece, pero este feature no puede
  validarlo contra un caso real todavía.
- ¿Qué pasa si el momento pedido en diferido cae fuera del histórico
  real conservado en `inventario.db` (antes de la primera ejecución
  registrada, o en el futuro)? No hay evidencia que reunir — el motor
  concluye que no se puede diagnosticar, mismo criterio que un momento
  sin datos en cualquier otro origen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE aceptar un episodio de inventario como
  entrada, tanto en vivo (una brecha activa ahora mismo, de los 5
  tipos en alcance) como en diferido (una ejecución pasada concreta ya
  registrada en el histórico del inventario, donde un componente tenía
  una brecha activa de uno de esos 5 tipos) — mismas dos vías que ya
  existen para los demás orígenes.
- **FR-002**: El sistema DEBE, al elegir diagnosticar un episodio de
  inventario, congelar un snapshot de su evidencia en ese momento, con
  la misma garantía de reproducibilidad diferida que ya exige FR-002
  de 007.
- **FR-003**: El sistema DEBE reunir evidencia real antes de formular
  ninguna hipótesis: el hallazgo del componente en el momento del
  episodio (categoría, tipo de brecha, contexto) y, cuando exista, lo
  que cambió respecto a la ejecución inmediatamente anterior en la que
  ese componente no tenía esa brecha.
- **FR-004**: El sistema DEBE formular más de una hipótesis de causa
  probable por episodio de inventario cuando la evidencia lo permita,
  con el mismo rigor que ya exige FR-004 de 007.
- **FR-005**: El sistema DEBE contrastar cada hipótesis contra la
  evidencia real reunida, y registrar cada una con su comprobación y
  desenlace, legible después — mismas garantías que FR-005/FR-006 de
  007 (Principio VIII).
- **FR-006**: El sistema DEBE concluir cada diagnóstico de inventario
  con exactamente uno de dos resultados — una causa probable con
  evidencia, o que no se puede diagnosticar — nunca presentar una
  causa sin evidencia que la respalde (mismo invariante que FR-007 de
  007).
- **FR-007**: El gasto en DeepSeek de un diagnóstico de inventario
  DEBE contar contra el mismo acumulado de gasto diario que ya protege
  a los diagnósticos de contenedor, disco, HA, backup y relay — un
  único límite compartido para todo el motor, no uno aparte por
  origen.
- **FR-008**: El sistema NO DEBE ejecutar ninguna acción correctiva
  sobre ninguna brecha de cobertura (declarar un estado esperado
  nuevo, añadir vigilancia, corregir qué llega al dashboard), ni
  proponer una remediación nueva — mismo alcance estrictamente
  diagnóstico que 007, 009, 010, 011 y 012.
- **FR-009**: El sistema NO DEBE mostrar el diagnóstico de un episodio
  de inventario en ningún sitio del dashboard — sigue siendo solo por
  línea de comandos en este feature.
- **FR-010**: El sistema NO DEBE diagnosticar brechas de tipo
  `condicion_incumplida` — ese tipo concreto queda fuera de alcance
  por duplicar el origen `ha` (feature 010); un episodio que apunte a
  una brecha de ese tipo concluye "no se puede diagnosticar" por estar
  fuera de alcance, no un intento de diagnóstico real.
- **FR-011**: El sistema NO DEBE diagnosticar ningún otro origen de la
  Central de Alarmas (hosts externos, el hub de Beszel, agentes) — el
  alcance de este feature se limita a contenedores, discos, HA,
  backups y relays (ya existentes) y al inventario de cobertura.

### Key Entities

- **Episodio de inventario**: la misma entidad "Episodio" que
  007/009/010/011/012 ya definen, generalizada para poder representar
  también una brecha de cobertura del inventario — atributos
  relevantes: qué componente, qué categoría, qué tipo de brecha (de
  los 5 en alcance), la ejecución del inventario en la que se
  detectó (en vivo, la más reciente; en diferido, una ejecución
  pasada concreta), y el snapshot de evidencia congelado, incluyendo
  lo que cambió respecto a la ejecución anterior sin esa brecha,
  cuando exista.
- **Hipótesis / Diagnóstico / Gasto diario**: las mismas entidades ya
  definidas en 007 (Key Entities) — sin cambios en su forma, ahora
  también aplicables a episodios de inventario.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Diagnosticar dos veces el mismo episodio de inventario
  (en vivo ya congelado, o en diferido) produce el mismo
  `conclusion_tipo` las dos veces, el 100% de las veces que se prueba
  — mismo criterio que SC-001 de 007, 009, 010, 011 y 012.
- **SC-002**: El 100% de los diagnósticos de inventario con evidencia
  suficiente incluyen más de una hipótesis registrada con su
  comprobación.
- **SC-003**: El gasto real de los diagnósticos de inventario, sumado
  al de contenedor, disco, HA, backup y relay, nunca supera el límite
  diario configurado — verificable revisando el acumulado de
  cualquier día.
- **SC-004**: Diagnosticar en vivo el inventario sin ninguna brecha
  activa de los 5 tipos en alcance concluye "no se puede diagnosticar"
  sin inventar una causa, el 100% de las veces que se prueba.
- **SC-005**: Diagnosticar en diferido al menos una de las brechas
  reales ya identificadas en el histórico del inventario (ejecuciones
  #19, #28, #31 y #52) concluye una causa probable o "no se puede
  diagnosticar" honesto, medido contra esa línea base real (Principio
  IX) — con su causa y resolución reales ya conocidas por los propios
  commits de los features 001-006.

## Assumptions

- **`condicion_incumplida` queda fuera de alcance por diseño, no por
  omisión**: de los 6 tipos de brecha que clasifica el inventario, ese
  es el único que hoy solo ocurre en componentes `entidad_ha`, y
  ocurre precisamente cuando el propio inventario detecta que el
  mecanismo de vigilancia declarado (`ha_monitor.py`) ya falló — es
  decir, es una segunda forma de ver el mismo fallo que el origen `ha`
  (feature 010) ya diagnostica desde su propia evidencia. Diagnosticar
  aquí también sería repetir trabajo ya hecho — mismo criterio que ya
  usó 011 para dejar fuera los backups de HA.
- **Línea base real disponible desde el arranque**, igual que 012 y a
  diferencia de 009, 010 y 011: cuatro ejecuciones históricas reales
  con brechas de los 5 tipos en alcance ya identificadas y ya
  resueltas — `hermes`/`telegram` (ejecución #19, 2026-08-08),
  `host_externo` (#28), `integracion` (#31) e `infra_monitorizacion`
  (#52, 2026-08-09) — todas cerradas por los propios features 001-006
  al ir declarando estado esperado y ampliando qué llega al dashboard.
  La validación de este feature se apoya en esta línea base histórica,
  no solo en `--vivo` contra el estado sano actual (que hoy no tiene
  ninguna brecha de estos 5 tipos que congelar en vivo).
- **`declaracion_caducada` no tiene ningún caso real todavía**: los
  859 componentes con `last_reviewed_at` no nulo están todos fechados
  a 2026-08-08, y el umbral de caducidad son 90 días, así que el
  primer caso real no puede aparecer antes de aproximadamente el
  2026-11-06. Mismo tipo de limitación ya aceptada en 009/010 (un
  subtipo sin caso real todavía) — se documenta, no se inventa un caso
  sintético.
- No existe ningún concepto de "componente crítico" equivalente a la
  lista de contenedores críticos de 007 — igual que en 009, 010, 011 y
  012, este feature no propone ninguna acción sobre nada, así que no
  hace falta ese tratamiento especial.
- Los otros 3 orígenes restantes de la Central de Alarmas (hosts
  externos, el hub de Beszel, agentes) quedan fuera de este feature —
  cada uno necesita su propia investigación de qué constituye
  evidencia real, igual que se hizo aquí para el inventario
  (`BRIEFING.md`, "Feature 013 — material de partida").
