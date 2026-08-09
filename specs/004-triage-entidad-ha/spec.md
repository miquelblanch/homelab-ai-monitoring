# Feature Specification: Triaje de Brechas `entidad_ha` — Ajustes, Automatizaciones y Frigate

**Feature Branch**: `004-triage-entidad-ha`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "El inventario de cobertura marca ~165 entidades de Home Assistant como brecha (sin estado esperado declarado) que en realidad no necesitan una declaración individual: unas porque son ajustes o telemetría interna de la propia integración (entity_category config/diagnostic — botones 'identify', niveles de log, versión de la app, opciones de color...), y otras porque pertenecen a Frigate, cuyo estado esperado depende de si el contenedor está corriendo o no — hoy Frigate está pensado para estar permanentemente apagado, así que sus ~33 entidades no deberían contar como brecha mientras esté parado, pero si algún día se enciende y algo falla de verdad, sí debería avisar. Además, 17 automatizaciones domésticas (toldos, cerradura, luces, proyector, sirenas...) no tienen ninguna vigilancia de si siguen activadas — si una se desactiva sola, nadie se entera hasta que falla el efecto que se esperaba de ella. Quiero que las tres cosas se traten como corresponde: las de ajuste/diagnóstico dejan de contar como brecha; las de Frigate solo cuentan como brecha cuando Frigate está encendido y algo va mal de verdad; las automatizaciones domésticas pasan a tener un estado esperado (activada) que si se incumple sí es una brecha real. No incluye las 5 entidades de seguridad (batería de la cerradura, enchufes sobrecargados) ni el resto de la cola larga sin triar — esas quedan para un feature posterior."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dejar de contar como brecha lo que es ajuste, no salud (Priority: P1)

Miquel quiere que el inventario de cobertura deje de marcar como brecha
las entidades de Home Assistant que son ajustes de configuración
(botones "identify", nivel de log, comportamiento al encender) o
telemetría interna de una integración (versión de la app, opciones de
color disponibles) — no son señales de salud de nada, son mandos o
datos de depuración, y hoy infla el recuento de brechas con ruido que
nunca se va a "arreglar" porque no hay nada que arreglar.

**Why this priority**: Es la pieza de mayor impacto y menor riesgo — un
único criterio ya declarado por la propia Home Assistant
(`entity_category`), sin inventar nada, que cierra el mayor bloque de
brechas de golpe.

**Independent Test**: Se puede probar por completo relanzando el
inventario de cobertura y comprobando que ninguna entidad con
`entity_category` de ajuste o diagnóstico aparece en el listado de
brechas — salvo las excepciones explícitas de seguridad y las de
Frigate, que se tratan aparte (ver User Story 3 y Assumptions).

**Acceptance Scenarios**:

1. **Given** una entidad de Home Assistant marcada por la propia HA como
   ajuste o telemetría interna, **When** se relanza el inventario de
   cobertura, **Then** esa entidad no aparece como brecha.
2. **Given** una entidad de seguridad (batería crítica de la cerradura,
   enchufe sobrecargado) que también está marcada como telemetría
   interna por HA, **When** se relanza el inventario, **Then** esa
   entidad sigue apareciendo como brecha — el criterio de ajuste/
   diagnóstico no la debe absorber (fuera de alcance de este feature,
   ver Assumptions).
3. **Given** una entidad de Frigate marcada como ajuste (los switches de
   detección/grabación), **When** se relanza el inventario, **Then** esa
   entidad se trata con la lógica de la User Story 3, no con la regla
   genérica de esta historia.

---

### User Story 2 - Saber si una automatización doméstica se ha desactivado sola (Priority: P2)

Miquel quiere que el inventario de cobertura avise si alguna de las
automatizaciones domésticas (toldos, cerradura, luces, proyector,
sirenas de presencia...) aparece desactivada, en vez de enterarse solo
cuando el efecto que esperaba de ella no ocurre — por ejemplo, que el
toldo no baje solo al atardecer porque la automatización que lo hace
lleva semanas apagada sin que nadie lo note.

**Why this priority**: Cierra un tipo de fallo silencioso genuino — una
automatización que se desactiva no deja ningún rastro hoy — pero
depende de declarar un estado esperado nuevo (no reutiliza uno ya
calculado), así que va después de la User Story 1.

**Independent Test**: Se puede probar por completo desactivando a mano
una automatización doméstica no crítica y comprobando que el inventario
la marca como brecha, y volviendo a activarla para comprobar que deja
de estarlo — sin depender de que la User Story 1 esté terminada.

**Acceptance Scenarios**:

1. **Given** una automatización doméstica de las 17 en alcance está
   activada, **When** se relanza el inventario, **Then** no aparece
   como brecha.
2. **Given** esa misma automatización se desactiva (a mano, o porque
   falla al cargar tras un reinicio de Home Assistant), **When** se
   relanza el inventario, **Then** aparece como brecha real, no como
   "sin declaración".
3. **Given** una automatización se desactiva temporalmente por la propia
   lógica del hogar (por ejemplo, al activar el modo vacaciones), **When**
   se relanza el inventario durante esa ventana, **Then** puede aparecer
   como brecha igualmente — es una limitación aceptada, no un fallo de
   diseño (ver Assumptions).

---

### User Story 3 - Vigilar Frigate solo cuando está encendido (Priority: P3)

Miquel quiere que las entidades de Frigate (cámaras, detección de
movimiento y personas, snapshots, grabación) cuenten como brecha
únicamente cuando Frigate está corriendo y alguna de esas entidades no
está dando datos de verdad — mientras Frigate está parado (su estado
habitual), esas ~33 entidades no deberían aparecer como pendientes de
arreglar, igual que ya pasa con el propio contenedor `frigate`.

**Why this priority**: Depende de comprobar el estado en vivo del
contenedor además del estado de cada entidad — más trabajo que las
otras dos historias, y de menor frecuencia de uso real (Frigate está
pensado para permanecer apagado la mayor parte del tiempo).

**Independent Test**: Se puede probar por completo parando y arrancando
el contenedor `frigate` y comprobando que las ~33 entidades dejan de
contar como brecha cuando está parado, y que cuentan como brecha cuando
está corriendo y alguna entidad está `unavailable`/`unknown` — sin que
las otras dos historias tengan que estar terminadas primero.

**Acceptance Scenarios**:

1. **Given** el contenedor `frigate` está parado, **When** se relanza el
   inventario, **Then** ninguna de las entidades de Frigate cuenta como
   brecha, sea cual sea su estado en el registro de Home Assistant.
2. **Given** el contenedor `frigate` está corriendo y todas sus
   entidades reportan un valor válido, **When** se relanza el
   inventario, **Then** ninguna cuenta como brecha.
3. **Given** el contenedor `frigate` está corriendo pero alguna entidad
   está `unavailable` o `unknown`, **When** se relanza el inventario,
   **Then** esa entidad cuenta como brecha real.

---

### Edge Cases

- ¿Qué pasa si Home Assistant reclasifica en el futuro la
  `entity_category` de una entidad (por ejemplo, una actualización de
  una integración empieza a marcar algo como diagnóstico que antes no
  lo era)? El criterio se recalcula en cada ejecución del inventario a
  partir del registro real de HA — no es una lista fija copiada aquí,
  así que sigue el cambio automáticamente, para bien o para mal.
- ¿Qué pasa con una automatización doméstica que se desactiva a
  propósito por otra automatización (por ejemplo, "Modo Vacaciones ON"
  desactiva la automatización de toldos)? Puede aparecer como brecha
  durante esa ventana — se acepta como limitación de la v1 en vez de
  intentar modelar qué desactivaciones son "legítimas" (ver
  Assumptions).
- ¿Qué pasa si el contenedor `frigate` está en un estado intermedio
  (arrancando, parando) cuando se ejecuta el inventario? Se trata igual
  que "parado" a efectos de esta vigilancia — solo "corriendo" de
  verdad activa la comprobación de las entidades, nunca un estado
  transitorio ambiguo.
- ¿Qué pasa con las 5 entidades de seguridad (batería cerradura,
  enchufes sobrecargados) que hoy también están marcadas como
  diagnóstico? Quedan explícitamente fuera de la regla de la User
  Story 1 — siguen apareciendo como brecha igual que hoy, sin cambios,
  hasta que se aborden en un feature aparte.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El inventario de cobertura NO DEBE contar como brecha
  ninguna entidad de Home Assistant cuya `entity_category` sea de
  ajuste o de telemetría interna de la integración — salvo las
  excepciones explícitas de FR-002 y FR-003.
- **FR-002**: La regla de FR-001 NO DEBE aplicarse a las entidades de
  seguridad identificadas (batería crítica y en carga de la cerradura,
  estado "sobrecargado" de los enchufes) — estas siguen evaluándose
  como hoy, fuera del alcance de este feature.
- **FR-003**: La regla de FR-001 NO DEBE aplicarse a las entidades de
  Frigate — estas se rigen por FR-005 a FR-007, no por el criterio de
  ajuste/diagnóstico.
- **FR-004**: El inventario de cobertura DEBE contar como brecha
  cualquiera de las 17 automatizaciones domésticas en alcance que esté
  desactivada, usando su propio estado activada/desactivada como el
  estado esperado declarado (esperado: activada).
- **FR-005**: El inventario de cobertura NO DEBE contar como brecha
  ninguna entidad de Frigate mientras el contenedor `frigate` no esté
  corriendo.
- **FR-006**: El inventario de cobertura DEBE contar como brecha
  cualquier entidad de Frigate cuyo estado en Home Assistant sea
  `unavailable` o `unknown` mientras el contenedor `frigate` esté
  corriendo.
- **FR-007**: El inventario de cobertura NO DEBE contar como brecha una
  entidad de Frigate que, con el contenedor corriendo, tenga un valor
  válido — con independencia de cuál sea ese valor (una detección de
  movimiento en `on` no es un fallo).
- **FR-008**: Este feature NO DEBE ejecutar ninguna acción correctiva
  sobre Home Assistant, Frigate, ni ninguna automatización — es
  exclusivamente de evaluación de cobertura.
- **FR-009**: Este feature NO DEBE modificar la configuración de ninguna
  automatización, entidad o del propio Frigate — todos los cambios de
  configuración relacionados (relays de red de Frigate, limpieza de
  automatizaciones redundantes) ya se hicieron fuera de este feature.

### Key Entities

- **Entidad de ajuste/diagnóstico**: cualquier entidad de Home Assistant
  con `entity_category` de configuración o diagnóstico, excepto las
  excepciones de seguridad y las de Frigate. Atributo relevante: la
  propia `entity_category`, tal como la declara el registro de HA.
- **Automatización doméstica en alcance**: una de las 17 automatizaciones
  identificadas que no tienen ya vigilancia por otra vía. Atributo
  relevante: si está activada o desactivada.
- **Entidad de Frigate**: cualquiera de las ~33 entidades vinculadas al
  contenedor `frigate` (cámaras, detección, snapshots, grabación).
  Atributos relevantes: su valor en Home Assistant (`unavailable`,
  `unknown`, o un valor válido), y si el contenedor `frigate` está
  corriendo en el momento de la comprobación.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El número de brechas de categoría `entidad_ha` baja de las
  309 actuales en al menos 115 tras desplegar este feature (comprobable
  relanzando el inventario de cobertura), sin que ninguna de las 5
  excepciones de seguridad deje de aparecer.
- **SC-002**: Miquel puede saber, sin revisar Home Assistant a mano, si
  alguna de las 17 automatizaciones domésticas en alcance se ha
  desactivado — hoy esa información no está en ningún sitio salvo
  abriendo Home Assistant y mirando una por una.
- **SC-003**: Con Frigate parado, ninguna de sus ~33 entidades aparece
  como brecha. Con Frigate corriendo y las cámaras dando datos reales
  (mismo estado verificado en vivo el 2026-08-09), tampoco.
- **SC-004**: Si Frigate está corriendo y alguna de sus entidades deja de
  dar datos de verdad, el inventario lo refleja como brecha — no se
  pierde cobertura real a cambio de eliminar el ruido cuando está
  parado.

## Assumptions

- Las 5 entidades de seguridad (batería crítica/en carga de la
  cerradura, 3 enchufes "sobrecargado") quedan fuera de alcance a
  propósito — siguen contando como brecha exactamente igual que hoy;
  instrumentarlas con su propio estado esperado es trabajo de un
  feature posterior.
- El resto de la cola larga de brechas `entidad_ha` no cubierta por
  ninguna de las tres historias (~134 entidades: localización de
  iPhones/MacBook, sensores de temperatura/energía por habitación,
  luces Zigbee individuales, scripts, helpers, estado de backups en
  HA...) queda fuera de alcance — no se toca ni se declara nada sobre
  ellas en este feature.
- Una automatización que se desactiva por la lógica legítima de otra
  automatización (p. ej. modo vacaciones) puede generar una brecha
  transitoria durante esa ventana — se acepta como limitación conocida
  de la v1 en vez de modelar qué desactivaciones son "esperadas"; el
  coste de una brecha ocasional y explicable es menor que el de no
  detectar una automatización realmente rota.
- El estado "corriendo" del contenedor `frigate` se lee del mismo mecanismo
  que ya usa el resto del inventario para el estado en vivo de
  contenedores (feature 001) — este feature no introduce una segunda
  vía de comprobar si un contenedor está arriba.
- Los cambios de infraestructura que motivaron este feature (relays de
  red para que Frigate alcance las cámaras, eliminación de las 22
  automatizaciones redundantes con avisos que este proyecto ya manda)
  ya se hicieron en producción antes de escribir esta especificación —
  este feature parte de ese estado, no lo reproduce.
