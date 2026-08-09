# Feature Specification: Latido Propio — Recordatorios de Nextcloud y Beszel (Hub)

**Feature Branch**: `003-latidos-beszel-calendario`

**Created**: 2026-08-09

**Status**: Draft

**Input**: User description: "Dos piezas de la propia infraestructura de monitorización del homelab no tienen todavía una señal que confirme que siguen funcionando de verdad, más allá de que el proceso esté vivo. La primera: bautista-calendar.sh (recordatorios de Nextcloud, cron de las 10:00) no dice nunca si se ha ejecutado — ni cuando manda recordatorios, ni cuando calla porque hoy no hay eventos, ni cuando ya detecta y reporta un fallo real de los calendarios. La segunda: Beszel, la propia herramienta que vigila los hosts físicos de Uptime Kuma y AdGuard Home (y el Mac Mini), no tiene ninguna comprobación de si sigue reportando datos frescos sobre los tres — si el hub se queda colgado o deja de sincronizar, hoy no hay forma de saberlo salvo notarlo por casualidad. Quiero que las dos tengan un latido propio, visible en el panel 'Estado de los monitores' del dashboard que ya existe, con el mismo criterio de frescura que usa el resto de monitores del homelab. No incluye rediseñar cómo funcionan los recordatorios de Nextcloud ni la configuración de Beszel — solo instrumentar la vigilancia que les falta."

## Clarifications

### Session 2026-08-09

- Q: Cuando Beszel deja de tener datos frescos sobre uno de los tres sistemas que vigila (Mac Mini, Uptime Kuma, AdGuard Home) pero los otros dos siguen frescos, ¿cuenta como "el hub ha dejado de funcionar", o solo cuenta cuando los tres se quedan sin datos frescos a la vez? → A: Solo cuenta como fallo del hub cuando los tres pierden frescura a la vez. Un solo sistema sin datos frescos, con los otros dos bien, ya tiene su propia alarma (el panel de hosts externos de feature 002, o el resto de vigilancia del Mac Mini) — tratarlo también aquí como "el hub está roto" sería la misma condición reportada dos veces (Principio XII).
- Q: ¿Cuántos minutos sin dato fresco de Beszel antes de considerar que el hub ha dejado de reportar (los 3 sistemas a la vez)? → A: 15 minutos — mismo margen que ya usa `beszel-hosts` en `MONITOR_JOBS` (feature 002) para este mismo tipo de dato; consistencia entre features y de sobra frente al ciclo real de sondeo de Beszel (~1 minuto, comprobado en vivo el 2026-08-09).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Saber si los recordatorios de Nextcloud se han ejecutado hoy (Priority: P1)

Miquel quiere poder comprobar, sin esperar a que llegue un aviso de error a
Telegram, si el cron de recordatorios de las 10:00 se ha ejecutado hoy.
Hoy ese script no deja ningún rastro cuando termina bien — ni cuando manda
recordatorios de verdad, ni cuando calla a propósito porque no hay eventos
ese día. Solo se entera de que algo falló si el propio script llega a
detectar el fallo y manda un mensaje de error; si el script no llega a
ejecutarse en absoluto (por ejemplo, el LaunchAgent no se disparó, o falla
antes de leer los calendarios), no hay ninguna señal en ningún sitio.

**Why this priority**: Es la pieza más barata de las dos — el fallo de
fondo de los recordatorios (BRIEFING.md Caso 4) ya se diagnosticó y se
arregló en el barrido del 2026-08-07; a esta pieza solo le falta la
vigilancia de "¿se ejecutó?", no ningún cambio de comportamiento.

**Independent Test**: Se puede probar por completo dejando pasar un día
normal (con o sin eventos) y comprobando que el panel "Estado de los
monitores" refleja que el cron se ejecutó hoy, sin depender de si mandó
o no un mensaje por Telegram — y, provocando que el cron no llegue a
correr, comprobando que el panel lo refleja como caducado al cabo de un
tiempo razonable.

**Acceptance Scenarios**:

1. **Given** el cron de recordatorios se ejecuta hoy y manda uno o más
   recordatorios por Telegram, **When** Miquel abre el dashboard,
   **Then** el panel "Estado de los monitores" muestra que se ejecutó
   hoy.
2. **Given** el cron de recordatorios se ejecuta hoy pero no hay eventos
   (silencio intencionado, sin mensaje a Telegram), **When** Miquel abre
   el dashboard, **Then** el panel sigue mostrando que se ejecutó hoy —
   el silencio del canal de Telegram no se confunde con que el cron no
   corrió.
3. **Given** el cron no se ha ejecutado en más tiempo del esperado (el
   LaunchAgent no se disparó, o el script falla antes de completar su
   ciclo), **When** Miquel abre el dashboard, **Then** el panel muestra
   ese monitor como caducado/sin latido reciente.

---

### User Story 2 - Saber si Beszel (hub) ha dejado de vigilar de verdad (Priority: P2)

Miquel quiere poder comprobar, desde el dashboard del homelab, si Beszel
—la herramienta que vigila el estado de Uptime Kuma, AdGuard Home y el
propio Mac Mini— sigue recibiendo datos frescos de los tres, sin tener
que abrir la interfaz de Beszel ni consultar su base de datos a mano.
Hoy, si el hub se queda colgado o deja de sincronizar con todo lo que
vigila, nada lo distingue de que todo esté sano — ya pasó una vez
(BRIEFING.md Caso 3, 06-08-2026) y no se llegó a confirmar la causa
porque no había ninguna señal que consultar después del hecho.

**Why this priority**: Depende de decidir primero qué significa que el
hub "ha dejado de funcionar" en vez de "un sistema vigilado en concreto
está caído" (ver Clarifications) — más trabajo de diseño que la User
Story 1, y por eso va después.

**Independent Test**: Se puede probar por completo comprobando que el
panel del dashboard refleja el mismo estado de frescura de datos que se
ve consultando directamente la base de datos del hub de Beszel en un
momento dado, sin que la User Story 1 tenga que estar terminada primero.

**Acceptance Scenarios**:

1. **Given** Beszel tiene datos frescos sobre los tres sistemas que
   vigila, **When** Miquel abre el dashboard, **Then** el panel "Estado
   de los monitores" muestra el mecanismo de vigilancia del hub como
   sano.
2. **Given** Beszel deja de tener datos frescos (más de 15 minutos)
   sobre los tres sistemas a la vez (el hub se queda colgado o pierde la
   conexión con todos, o no hay ningún dato que leer todavía), **When**
   Miquel abre el dashboard, **Then** el panel lo refleja como no sano.
3. **Given** Beszel deja de tener datos frescos sobre un solo sistema,
   con los otros dos frescos, **When** Miquel abre el dashboard,
   **Then** el mecanismo de vigilancia del hub sigue mostrándose sano —
   esa condición ya tiene su propia alarma en otro sitio (ver
   Clarifications).

---

### Edge Cases

- ¿Qué pasa si `bautista-calendar.sh` falla antes de llegar siquiera a
  intentar registrar que se ejecutó (por ejemplo, no encuentra las
  credenciales de Telegram y sale de inmediato)? El latido de ese día no
  se registra, y por tanto envejece — es la señal correcta, no un caso
  especial que tratar aparte.
- ¿Qué pasa si el contenedor `beszel` (el hub) está parado del todo, no
  solo sin datos frescos? Ya lo vigila `docker_monitor.py` de forma
  genérica, como a cualquiera de los 40 contenedores — este feature no
  duplica esa comprobación; se centra en si el hub, estando arriba,
  sigue haciendo su trabajo de verdad.
- ¿Qué pasa si el propio mecanismo que comprueba la frescura de Beszel
  deja de correr (no el hub — el que lo vigila)? Debe reflejarse igual
  que cualquier otro latido caducado del panel "Estado de los
  monitores" — un mecanismo de vigilancia sin quien lo vigile repetiría
  el mismo error que motivó este proyecto entero.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE registrar que el cron de recordatorios de
  Nextcloud se ha ejecutado, tanto si manda recordatorios reales, como
  si calla porque no hay eventos ese día, como si detecta y reporta un
  fallo real de los calendarios.
- **FR-002**: El panel "Estado de los monitores" del dashboard DEBE
  mostrar ese registro, con el mismo criterio de frescura/caducidad que
  ya usa para el resto de monitores expuestos ahí.
- **FR-003**: El sistema DEBE comprobar periódicamente si Beszel tiene
  datos frescos sobre cada uno de los tres sistemas que vigila (Mac
  Mini, Uptime Kuma, AdGuard Home), y registrar que esa comprobación se
  ha realizado.
- **FR-004**: El sistema DEBE mostrar el mecanismo de vigilancia de
  Beszel como no sano únicamente cuando los tres sistemas lleven más de
  15 minutos sin dato fresco a la vez (Clarifications) — un solo sistema
  sin dato fresco, con los otros dos frescos, NO DEBE mostrarse como
  fallo del hub, es la misma condición reportada dos veces (Principio
  XII).
- **FR-005**: El panel "Estado de los monitores" DEBE mostrar el estado
  de vigilancia de Beszel, sin exigir que Miquel abra la interfaz de
  Beszel ni consulte su base de datos a mano.
- **FR-006**: Este feature NO DEBE ejecutar ninguna acción correctiva ni
  reiniciar nada — es exclusivamente de vigilancia y visualización,
  igual que el resto del panel "Estado de los monitores".
- **FR-007**: Este feature NO DEBE cambiar cómo funcionan los
  recordatorios de Nextcloud (el fallo de fondo ya se arregló,
  `BARRIDO-2026-08-07.md`) ni la configuración de Beszel — la brecha es
  exclusivamente de vigilancia, no de comportamiento.
- **FR-008**: Si el propio mecanismo que comprueba la frescura de datos
  de Beszel deja de ejecutarse, el panel "Estado de los monitores" DEBE
  reflejarlo igual que cualquier otro latido caducado — no puede ser un
  mecanismo de vigilancia sin nadie que lo vigile (Principio XIII).

### Key Entities

- **Latido de recordatorios de Nextcloud**: derivado de cada ejecución
  de `bautista-calendar.sh`. Atributos: si se ejecutó, cuándo, resultado
  (recordatorios enviados / silencio intencionado / error detectado).
  Ya calculado hoy solo en el caso de error (vía Telegram); este feature
  añade el registro que falta para los otros dos casos y lo expone.
- **Estado de vigilancia de Beszel (hub)**: derivado de la antigüedad
  del último dato que Beszel tiene registrado para cada uno de los tres
  sistemas a su cargo. Atributos: antigüedad por sistema, y si los tres
  están simultáneamente sin datos frescos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Miquel puede ver, sin salir del dashboard, si los
  recordatorios de Nextcloud se han ejecutado hoy — hoy esa información
  solo es visible cuando llega un mensaje de error a Telegram, nunca en
  el caso de éxito (con o sin eventos).
- **SC-002**: Miquel puede ver, sin salir del dashboard, si Beszel lleva
  más de 15 minutos sin reportar datos frescos de los tres sistemas a su
  cargo — hoy no hay ninguna señal salvo notarlo por casualidad, como
  pasó el 06-08-2026.
- **SC-003**: Ninguna de las 2 brechas de cobertura reales que quedaban
  tras feature 002 (`infra_monitorizacion` — Beszel hub, `integracion` —
  Recordatorios de Nextcloud) sigue apareciendo como brecha tras
  desplegar este feature (comprobable relanzando
  `python3 -m inventory.cli --gaps`).
- **SC-004**: Ante un fallo del propio mecanismo que comprueba la
  frescura de Beszel, el panel "Estado de los monitores" lo refleja como
  caducado en vez de fallar en silencio o mostrar un falso "sano".

## Assumptions

- El latido de recordatorios de Nextcloud se considera caducado a partir
  de un margen amplio sobre su ciclo diario (mismo criterio que ya usa
  `verify-backups` — otro cron de una vez al día — en `MONITOR_JOBS` de
  `app.py`); el número exacto se fija en el plan, no en este documento.
- Beszel vigila cada sistema a su cargo con un ciclo de sondeo del orden
  de un minuto (comprobado en vivo contra los datos históricos del
  propio hub, 2026-08-09); el umbral de "dato viejo" para considerar que
  el hub ha dejado de funcionar es 15 minutos (Clarifications) — más de
  10 veces ese ciclo, mismo margen que ya usa `beszel-hosts` en
  `MONITOR_JOBS` (feature 002).
- Un ciclo silencioso de recordatorios (sin eventos hoy) cuenta como
  ejecución correcta a efectos del latido — el silencio intencionado ya
  está distinguido del error real desde el barrido del 2026-08-07; este
  feature no cambia esa lógica, solo añade el registro que falta.
- El contenedor `beszel` en sí ya está vigilado de forma genérica por
  `docker_monitor.py`, como cualquiera de los 40 contenedores del
  homelab; este feature no duplica esa comprobación — se centra en si el
  hub, estando arriba, sigue haciendo su trabajo de verdad.
- No se rediseña cómo funcionan los recordatorios de Nextcloud ni la
  configuración de Beszel — la brecha que cierra este feature es
  exclusivamente de vigilancia (faltaba el latido/la comprobación), no
  de comportamiento del sistema vigilado.
