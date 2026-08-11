# Feature Specification: Visor de Diagnósticos en Alarmas

**Feature Branch**: `008-visor-diagnosticos-correcciones`

> **Nota sobre el nombre**: el directorio se creó como
> "...-correcciones" antes de descubrir que la pestaña correcta es
> "Alarmas", no "Correcciones" (ver Clarifications y Assumptions). No
> se renombra el directorio — mismo criterio ya aplicado en
> `specs/006-central-alarmas` para un desajuste de numeración similar
> (`BRIEFING.md`): documentar el desajuste en vez de reescribir
> historial.

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "El motor de diagnóstico de episodios de contenedor (feature 007) ya funciona y ya tiene diagnósticos reales guardados, pero solo se pueden leer por línea de comandos — no hay ningún sitio en el dashboard del homelab donde ver qué se ha diagnosticado. Quiero que la pestaña \"Correcciones\" que ya existe en el dashboard (feature 006, unifica las alarmas activas del homelab) muestre, para una alarma de contenedor que ya tenga un episodio diagnosticado asociado, su conclusión (una causa probable con evidencia, o que no se pudo diagnosticar) y el detalle de cada hipótesis que se consideró — qué se propuso, cómo se contrastó, y en qué quedó. También quiero ver cuánto llevo gastado hoy en el presupuesto de DeepSeek. Es solo un visor de solo lectura: no incluye poder lanzar un diagnóstico nuevo desde el navegador, eso sigue siendo solo por línea de comandos. No incluye diagnosticar nada que no sean contenedores, ni una pestaña nueva en el dashboard."

## Clarifications

### Session 2026-08-11

- Q: Cuando el diagnóstico más reciente de un contenedor corresponda a
  una caída distinta de la que está activa ahora mismo, ¿cómo debe
  comportarse el visor? → A: Opción A — mostrar el episodio más
  reciente sin más, pero con su fecha siempre visible junto al
  diagnóstico. Miquel remarcó explícitamente que mostrar fechas es
  importante — se aplica no solo a la fecha del episodio, sino también
  a la del intento de diagnóstico (por si un mismo episodio se
  diagnosticó varias veces en momentos distintos, FR-005).
- Q (post-plan, mismo día): al preparar `/speckit-plan` se descubrió
  que "Correcciones" es el historial de alarmas ya **resueltas**, no
  las activas — la pestaña de alarmas activas es "Alarmas", separada.
  Con esa distinción clara, ¿dónde debe vivir el visor? → A: en
  **"Alarmas"** (activas ahora mismo), no en "Correcciones" — más
  accionable (ver el diagnóstico mientras el contenedor sigue caído,
  no después de que ya se resolvió solo) y coincide con el caso de uso
  que 007 ya validó de verdad (diagnóstico en vivo de un contenedor
  crítico mientras seguía activo, Escenario 4 de su `quickstart.md`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver la conclusión de un diagnóstico sin salir del dashboard (Priority: P1)

Miquel está mirando la pestaña "Alarmas" — las condiciones de fallo
activas ahora mismo en el homelab (feature 006) — y ve un contenedor
caído. Ese contenedor ya se diagnosticó por línea de comandos en algún
momento durante esta misma caída (`diagnostico.cli diagnosticar`).
Miquel quiere ver la conclusión de ese diagnóstico — una causa probable
con su explicación, o que no se pudo diagnosticar y por qué —
directamente junto a la alarma, sin abrir una terminal.

**Why this priority**: Es el valor central del feature. Sin esto, el
trabajo de diagnóstico de 007 sigue siendo invisible fuera de la línea
de comandos, exactamente el problema que este feature existe para
resolver.

**Independent Test**: Se puede probar por completo diagnosticando en
vivo un contenedor caído por CLI, abriendo la pestaña Alarmas, y
comprobando que esa alarma muestra la conclusión.

**Acceptance Scenarios**:

1. **Given** una alarma de un contenedor caído cuya caída actual ya se
   diagnosticó con conclusión `causa_probable`, **When** Miquel abre la
   pestaña, **Then** ve la causa probable y su texto junto a la alarma,
   junto con la fecha del episodio diagnosticado.
2. **Given** una alarma de un contenedor caído cuya caída actual se
   diagnosticó y concluyó `no_diagnosticable`, **When** Miquel abre la
   pestaña, **Then** ve explícitamente que no se pudo diagnosticar y el
   motivo (evidencia insuficiente, límite de gasto alcanzado, o fallo
   de DeepSeek).
3. **Given** una alarma de contenedor sin ningún episodio diagnosticado
   de esta caída, **When** Miquel abre la pestaña, **Then** la alarma
   se ve exactamente igual que antes de este feature — sin ninguna
   sección de diagnóstico vacía o rota.
4. **Given** un contenedor con un episodio diagnosticado de una caída
   **anterior**, ya resuelta, y una alarma activa nueva de una caída
   **distinta** todavía sin diagnosticar, **When** Miquel abre la
   pestaña, **Then** la alarma nueva no muestra el diagnóstico de la
   caída anterior — se trata como si no tuviera ningún diagnóstico
   asociado (Q1/Q2, Clarifications).

---

### User Story 2 - Ver el detalle de cada hipótesis considerada (Priority: P2)

Para un diagnóstico ya visible (User Story 1), Miquel quiere poder ver
también el razonamiento completo: qué hipótesis se formularon, cómo se
contrastó cada una contra la evidencia real, y en qué quedó cada una —
no solo la conclusión final.

**Why this priority**: Depende de que la conclusión ya sea visible
(User Story 1) — el detalle de hipótesis es una ampliación de ese
mismo dato, no algo que tenga sentido mostrar antes que la conclusión.

**Independent Test**: Se puede probar comparando lo que se ve en el
dashboard, para un diagnóstico concreto, con la salida de
`diagnostico.cli mostrar EPISODIO_ID` para ese mismo episodio — deben
coincidir en número de hipótesis, descripción, comprobación y
desenlace.

**Acceptance Scenarios**:

1. **Given** un diagnóstico visible en Alarmas con varias hipótesis
   consideradas, **When** Miquel pide ver el detalle, **Then** ve cada
   hipótesis con su descripción, cómo se contrastó, y su desenlace
   (confirmada / descartada / sin evidencia suficiente).
2. **Given** el mismo diagnóstico, **When** se compara con
   `diagnostico.cli mostrar` para ese episodio, **Then** la información
   mostrada en el dashboard no omite ninguna hipótesis ni desenlace que
   la CLI sí muestre.

---

### User Story 3 - Ver el gasto diario acumulado de DeepSeek (Priority: P3)

Miquel quiere ver, desde el propio dashboard, cuánto se ha gastado hoy
en el presupuesto de DeepSeek del motor de diagnóstico, sin tener que
consultar la base de datos a mano.

**Why this priority**: Es independiente de las otras dos historias —
no depende de ninguna alarma concreta ni de que haya diagnósticos que
mostrar hoy — pero tiene menos urgencia porque el cortacircuitos de
gasto (feature 007, FR-010) ya protege contra el riesgo real aunque
nadie mire este dato.

**Independent Test**: Se puede probar comparando el valor mostrado en
el dashboard con el acumulado real de la tabla `gasto_diario` para el
día en curso.

**Acceptance Scenarios**:

1. **Given** que hoy se ha gastado una cantidad determinada en
   diagnósticos, **When** Miquel mira la pestaña Alarmas, **Then** ve
   ese gasto acumulado y el límite diario configurado.
2. **Given** que hoy todavía no se ha ejecutado ningún diagnóstico,
   **When** Miquel mira la pestaña, **Then** ve el gasto en `0` (no un
   hueco vacío ni un error).

---

### Edge Cases

- ¿Qué pasa si un contenedor tiene más de un episodio diagnosticado
  cuyo momento podría corresponder a la caída actual? Se muestra el
  episodio cuyo momento esté más próximo al inicio de la caída actual
  (ver Assumptions).
- ¿Qué pasa si un mismo episodio se diagnosticó más de una vez
  (`diagnosticar` ejecutado varias veces sobre el mismo episodio, por
  ejemplo para comprobar reproducibilidad)? Se muestra el intento más
  reciente (ver Assumptions).
- ¿Qué pasa si la base de datos de diagnósticos no existe todavía, o no
  se puede leer? Las alarmas se siguen mostrando con normalidad, sin
  ninguna sección de diagnóstico — nunca un error visible ni una
  pestaña rota (mismo principio "a prueba de fallos" que ya sigue el
  resto de este dashboard).
- ¿Qué pasa si el único episodio diagnosticado de un contenedor es de
  una caída **anterior**, ya resuelta, distinta de la que está activa
  ahora mismo? **Resuelto en Clarifications (Q1/Q2, 2026-08-11)**: no
  se muestra — un episodio de antes de que empezara la caída actual no
  cuenta como diagnóstico de esta caída (mismo criterio que "sin
  episodio asociado"). Y en el caso general, la fecha del episodio
  mostrado siempre es visible, para que Miquel pueda juzgar la
  correspondencia él mismo (Principio XII, precisión del dashboard).
- ¿Qué pasa con las alarmas de los otros 8 orígenes de la Central de
  Alarmas (Home Assistant, backups, relays, discos...)? No obtienen
  ninguna sección de diagnóstico en este feature — solo las de
  contenedor.
- ¿Qué pasa si más de 5 contenedores caen a la vez y la Central de
  Alarmas los agrupa en una sola entrada (feature 006, FR-013)? Esa
  entrada agrupada no tiene un contenedor individual con el que
  emparejar un episodio — no muestra ningún diagnóstico, para no dar a
  entender que corresponde a uno solo de los contenedores del grupo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE, para cada alarma de contenedor caído
  mostrada en la pestaña "Alarmas", comprobar si existe un episodio
  diagnosticado (feature 007) del mismo contenedor cuyo momento
  corresponda a la caída que está causando esa alarma ahora mismo —
  nunca a una caída anterior ya resuelta.
- **FR-002**: Cuando exista un episodio diagnosticado que corresponda,
  el sistema DEBE mostrar su conclusión junto a la alarma: una causa
  probable con su texto, o que no se pudo diagnosticar junto con el
  motivo — sin que Miquel tenga que salir del dashboard.
- **FR-003**: El sistema DEBE poder mostrar, para el diagnóstico
  mostrado, el detalle de cada hipótesis considerada: su descripción,
  cómo se contrastó contra la evidencia, y su desenlace.
- **FR-004**: Cuando haya más de un episodio diagnosticado del mismo
  contenedor que podría corresponder a la caída actual, el sistema
  DEBE mostrar el más próximo en el tiempo al inicio de esa caída,
  siempre con su fecha visible — nunca se muestra un diagnóstico sin
  decir de cuándo es (Clarifications, Q1). Un episodio de una caída
  anterior ya resuelta NUNCA se muestra como si fuera de la caída
  actual (Clarifications, Q2) — se trata igual que "sin episodio
  asociado" (FR-007).
- **FR-005**: Cuando un episodio tenga más de un intento de
  diagnóstico, el sistema DEBE mostrar el intento más reciente, junto
  con la fecha de ese intento siempre visible, mismo criterio que
  FR-004.
- **FR-006**: El sistema DEBE mostrar, en algún punto visible de la
  pestaña "Alarmas", el gasto acumulado del día en curso en DeepSeek y
  el límite diario configurado.
- **FR-007**: Cuando una alarma de contenedor no tenga ningún episodio
  diagnosticado de la caída actual, el sistema DEBE seguir mostrando
  esa alarma exactamente igual que antes de este feature.
- **FR-008**: Si los datos de diagnóstico no están disponibles o no se
  pueden leer, el sistema NO DEBE dejar de mostrar las alarmas — se
  comporta como si ningún contenedor tuviera diagnóstico asociado.
- **FR-009**: El sistema NO DEBE ofrecer ninguna forma de lanzar un
  diagnóstico nuevo desde el dashboard — es estrictamente de lectura
  sobre lo que `diagnostico.cli` ya haya producido.
- **FR-010**: El sistema NO DEBE modificar ni escribir nunca los datos
  de diagnóstico — solo lectura.
- **FR-011**: El sistema DEBE limitar esta funcionalidad a alarmas de
  contenedor — ninguno de los otros orígenes de la Central de Alarmas
  obtiene una sección de diagnóstico en este feature.
- **FR-012**: El sistema NO DEBE mostrar ningún diagnóstico en una
  alarma agrupada (feature 006, FR-013) — una entrada que resume varios
  contenedores caídos a la vez no tiene un único contenedor con el que
  emparejar un episodio.

### Key Entities

- **Alarma de contenedor caído**: ya existente (feature 006) — un
  contenedor que no está corriendo ahora mismo, activo desde un
  momento conocido. Este feature le añade, cuando aplica, un
  diagnóstico asociado a esta caída en concreto.
- **Episodio diagnosticado**: ya existente (feature 007) — el vínculo
  con una alarma se hace por nombre de contenedor más proximidad
  temporal al inicio de la caída actual, no por un identificador
  compartido (no existe ninguno hoy entre las dos features).
- **Diagnóstico / Hipótesis**: ya existentes (feature 007) — se leen
  tal cual, sin transformarlos.
- **Gasto diario de DeepSeek**: ya existente (feature 007) — se lee tal
  cual para el día en curso.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las alarmas de contenedor caído con un
  episodio diagnosticado de la caída actual muestran su conclusión en
  el dashboard, sin que Miquel necesite ejecutar ningún comando.
- **SC-002**: El detalle de hipótesis mostrado en el dashboard, para
  cualquier diagnóstico dado, coincide exactamente con el que devuelve
  `diagnostico.cli mostrar` para ese mismo episodio — cero pérdida de
  información entre la CLI y el dashboard.
- **SC-003**: El gasto diario mostrado en el dashboard coincide, en
  cualquier momento verificado, con el acumulado real de la tabla
  `gasto_diario` para el día en curso.
- **SC-004**: Una alarma de contenedor sin diagnóstico de la caída
  actual se sigue viendo, antes y después de este feature, exactamente
  igual — cero regresiones sobre la pestaña "Alarmas" ya existente.
- **SC-005**: El 100% de los diagnósticos mostrados en el dashboard
  llevan visible la fecha del episodio y la fecha del intento de
  diagnóstico — nunca se muestra una conclusión sin decir de cuándo es
  (Clarifications, Q1).
- **SC-006**: El 0% de los diagnósticos mostrados corresponde a una
  caída anterior ya resuelta, distinta de la que está causando la
  alarma mostrada (Clarifications, Q2).

## Assumptions

- **Corrección sobre una premisa del borrador inicial de este spec**
  (encontrada al preparar `/speckit-plan`, 2026-08-11, y ajustada de
  nuevo el mismo día tras revisarlo con Miquel): "Correcciones" no es
  la lista de alarmas activas — es el historial de alarmas ya
  **resueltas** (`get_alarm_corrections()`). La pestaña de alarmas
  activas, correcta para este feature, es "Alarmas"
  (`get_active_alarms()`, feature 006). Ver Clarifications Q2 para la
  decisión final. No cambia el resto de decisiones ya tomadas con
  Miquel (visor de solo lectura, sin pestaña nueva).
- El vínculo entre una alarma de contenedor y un episodio diagnosticado
  se hace por nombre de contenedor y proximidad temporal al momento en
  que la caída actual comenzó — no existe hoy ningún identificador
  compartido entre las dos features. Si ningún episodio del contenedor
  corresponde razonablemente a la caída actual (por ejemplo, todos son
  de caídas anteriores ya resueltas), se trata como si no hubiera
  ninguno asociado. Si el episodio elegido tiene varios intentos de
  diagnóstico, se muestra el intento más reciente (FR-004/FR-005).
- Los datos de diagnóstico ya son accesibles desde donde corre el
  dashboard — no se necesita ningún cambio de infraestructura nuevo
  para leerlos, solo el código que los lee y los muestra.
- No se añade ningún control para lanzar diagnósticos nuevos desde el
  dashboard — sigue siendo exclusivamente por línea de comandos,
  decidido explícitamente con Miquel antes de escribir este spec.
- El alcance se limita a alarmas de contenedor — el resto de orígenes
  de la Central de Alarmas (Home Assistant, backups, relays, hosts
  externos, el propio hub de monitorización, agentes, discos,
  inventario) no se tocan en este feature.
- No se persiste ningún dato nuevo — este feature es de solo lectura
  sobre lo que las features 006 y 007 ya calculan y persisten.
