# Feature Specification: Alarmas Ya Calculadas al Panel del Dashboard

**Feature Branch**: `002-alarmas-al-dashboard`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "El dashboard del homelab (http://homelab.amsterdam9.home/) ya recibe, cada 5 minutos, una alarma calculada por contenedor (docker_monitor.py: si está caído y desde cuándo) y, para los hosts físicos distintos del Mac Mini que vigila Beszel (Uptime Kuma, AdGuard Home), un estado calculado por Beszel — pero ninguna de las dos llega hoy al panel. Quiero que toda alarma real activa de estos dos orígenes aparezca en el dashboard, una sola vez y sin ausencias, sin construir ningún portal ni interfaz nueva — el dashboard ya existe. No incluye vigilar el propio Beszel ni los recordatorios de Nextcloud: esos no tienen todavía una señal calculada que mostrar."

## Clarifications

### Session 2026-08-08

- Q: Cuando un contenedor está caído en este instante (el estado en vivo del dashboard ya lo muestra) y además `docker_monitor.py` tiene calculado desde cuándo, ¿la alarma nueva se funde en la fila que ya existe del contenedor, o se reserva aparte solo para episodios ya recuperados? → A: Se funde siempre en la fila del contenedor — el estado en vivo se enriquece con "desde cuándo" cuando `docker_monitor.py` lo tiene. Un único sitio donde mirar cada contenedor, cumpliendo el Principio XII de forma directa sin abrir superficie nueva en el dashboard.
- Q: Si el mecanismo nuevo que lee el estado de Beszel para Kuma/AdGuard deja de funcionar (no el host vigilado — el propio lector), ¿debe tener su propio latido que se sume al panel "Estado de los monitores", o basta con que el dato se muestre como "sin evidencia" cuando esté obsoleto? → A: Sí, con latido propio — mismo patrón que `docker_monitor.py`, `ha_monitor.py`, `verify_backups.py`, `dns_pi_monitor.py` y `telegram_monitor.py`, sumado al panel "Estado de los monitores" que ya existe. Cierra el propio mecanismo nuevo dentro de la obligación de vigilancia del Principio XIII, en vez de dejarlo como el único monitor sin quien lo vigile.
- Q: ¿A partir de qué antigüedad del dato debe el dashboard dejar de mostrar el último estado conocido y pasar a "sin evidencia" — tanto para la alarma de `docker_monitor.py` como para el estado que viene de Beszel? → A: 15 minutos (3× el ciclo de 5 minutos de `docker_monitor.py`) — mismo umbral que ya usa `_TELEGRAM_HEARTBEAT_MAX_AGE_S` en `evaluate.py` (feature 001), por consistencia dentro del propio repo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver en el dashboard cuándo un contenedor estuvo caído (Priority: P1)

Miquel abre el dashboard y quiere saber, para cualquier contenedor, si en el
ciclo de vigilancia más reciente se detectó caído y desde cuándo — no solo si
en este instante `docker ps` lo ve corriendo. Hoy el panel de contenedores
solo refleja el estado en vivo; un contenedor que estuvo caído y ya se
recuperó entre dos visitas al dashboard no deja ningún rastro visible, pese a
que `docker_monitor.py` ya lo calculó y lo tiene guardado.

**Why this priority**: Es el caso que motivó el proyecto entero — 49
reinicios reales de un contenedor sin que ninguna alerta llegara a ningún
sitio. La señal ya existe (`docker_monitor.py` corre cada 5 minutos); lo que
falta es mostrarla, no calcularla, así que es la entrega de menor esfuerzo y
mayor valor del feature.

**Independent Test**: Se puede probar por completo provocando (o simulando)
que un contenedor no crítico quede caído entre dos ciclos de
`docker_monitor.py`, y comprobando que el dashboard refleja el episodio —
mientras persiste y también una vez recuperado, distinguible del resto de
contenedores que nunca fallaron — sin depender de ninguna otra parte de este
feature.

**Acceptance Scenarios**:

1. **Given** un contenedor no crítico que `docker_monitor.py` marcó caído en
   su ciclo más reciente, **When** Miquel abre el dashboard, **Then** ese
   contenedor aparece marcado como caído, con la información de desde cuándo
   ya calculada por `docker_monitor.py`.
2. **Given** un contenedor que estuvo caído y ya se recuperó antes de que
   Miquel mirara el dashboard, **When** Miquel lo abre, **Then** puede ver
   que hubo un episodio reciente, sin tener que haber estado mirando en el
   momento exacto en que ocurrió.
3. **Given** un contenedor corriendo con normalidad, **When** Miquel abre el
   dashboard, **Then** no aparece ninguna marca de alarma para ese
   contenedor.

---

### User Story 2 - Ver en el dashboard el estado de los hosts que vigila Beszel (Priority: P2)

Miquel quiere ver en el dashboard si el host que aloja Uptime Kuma o el host
que aloja AdGuard Home (DNS primario) están caídos, usando el estado que
Beszel ya calcula sobre ellos — sin tener que abrir la interfaz de Beszel por
separado ni consultar su base de datos a mano. Es el cierre del Caso 3 de
`BRIEFING.md`: Beszel vigila estos dos sistemas, pero ese resultado hoy no
llega a ningún sitio que Miquel mire por costumbre.

**Why this priority**: Cierra una brecha real y ya diagnosticada, pero
depende de exponer un dato que hoy vive dentro del volumen del hub de
Beszel — más trabajo de integración que la User Story 1, y por eso va
después.

**Independent Test**: Se puede probar por completo comprobando que el estado
de ambos hosts en el dashboard coincide con el estado que muestra Beszel
para esos mismos sistemas en un momento dado, sin que la User Story 1 tenga
que estar terminada primero.

**Acceptance Scenarios**:

1. **Given** Beszel tiene registrado un host (Uptime Kuma o AdGuard Home)
   como caído, **When** Miquel abre el dashboard, **Then** ese host aparece
   marcado como caído.
2. **Given** ambos hosts están arriba según Beszel, **When** Miquel abre el
   dashboard, **Then** ninguno de los dos aparece marcado como alarma.
3. **Given** el propio mecanismo que lee el estado de Beszel no puede
   obtener un dato fresco (por ejemplo, el hub de Beszel no responde),
   **When** Miquel abre el dashboard, **Then** el host se muestra como "sin
   evidencia reciente", nunca como "arriba" por defecto — un silencio no es
   una confirmación de salud (Principio II de la constitución).

---

### Edge Cases

- ¿Qué pasa si `docker_monitor.py` marca un contenedor caído y, al mismo
  tiempo, el propio `docker ps` en vivo que ya consulta el dashboard también
  lo ve parado? Se funde en una sola fila: el estado en vivo del contenedor
  se enriquece con el "desde cuándo" de `docker_monitor.py` cuando existe,
  nunca se muestra como una segunda alarma separada (ver Clarifications).
- ¿Qué pasa con un contenedor marcado `NEVER_RESTART` (`frigate`) o con un
  contenedor crítico que ya tiene su propio tratamiento en
  `docker_monitor.py`? La alarma se muestra igual que para cualquier otro —
  este feature solo expone lo que `docker_monitor.py` ya decidió, no cambia
  ninguna clasificación existente.
- ¿Qué pasa si `docker_monitor_state.json` o el fichero equivalente para los
  hosts externos no existe o no se puede leer (proceso caído, fichero
  corrupto)? El panel afectado se muestra como "sin evidencia", nunca se cae
  el resto del dashboard ni se oculta en silencio (mismo principio "a prueba
  de fallos" que el resto de monitores del homelab).
- ¿Qué pasa con un host externo que Beszel no ha vigilado nunca (dato
  ausente, no solo caducado)? Se distingue de "arriba" y de "caído": es
  "sin evidencia", igual que un contenedor sin healthcheck no es lo mismo
  que un contenedor sano.
- ¿Qué pasa con Beszel (hub) mismo o con los recordatorios de Nextcloud?
  Quedan fuera de este feature — no tienen hoy ninguna señal calculada que
  mostrar; instrumentarlos es un feature aparte (ver Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El dashboard DEBE mostrar, para cada contenedor Docker, si
  `docker_monitor.py` lo marcó caído en su ciclo de vigilancia más reciente y
  desde cuándo, usando el dato que `docker_monitor.py` ya calcula — sin
  reimplementar esa lógica.
- **FR-002**: El dashboard DEBE mostrar, para el host que aloja Uptime Kuma y
  para el host que aloja AdGuard Home (DNS primario), el estado que Beszel ya
  calcula sobre ellos.
- **FR-003**: Ninguna condición de alarma real DEBE aparecer duplicada en el
  dashboard cuando dos mecanismos la reportan a la vez (Principio XII) — ver
  Edge Cases para el caso concreto de contenedores.
- **FR-004**: Cuando el estado de un host externo (Kuma, AdGuard) no esté
  disponible, o tenga más de 15 minutos de antigüedad, o el latido del
  mecanismo que lo lee (`FR-008`) esté ausente, el dashboard DEBE mostrarlo
  como "sin evidencia", nunca como "sano" por omisión ni como "caído" sin
  fundamento (Principio II). Para contenedores, esta misma garantía ya la
  da el latido existente de `docker_monitor.py` (30 min, ya vigilado en el
  panel "Estado de los monitores") — este feature no introduce un segundo
  mecanismo de frescura para un dato que ya tiene el suyo. *(Precisión
  añadida en `/speckit-plan`, 2026-08-08: la redacción original de este FR
  aplicaba un único umbral de 15 min a ambos orígenes por igual; el propio
  código muestra que `docker_monitor.py` ya tiene su latido con umbral
  distinto — 30 min — desde antes de este feature, así que duplicarlo
  habría sido inconsistente con lo que ya existe. Ver `research.md`.)*
- **FR-005**: Este feature NO DEBE construir ningún portal ni interfaz nueva:
  toda la información se entrega dentro del dashboard que ya existe
  (`http://homelab.amsterdam9.home/`).
- **FR-006**: Este feature NO DEBE ejecutar ninguna acción correctiva sobre
  ningún componente — es exclusivamente de visualización, igual que el resto
  del dashboard.
- **FR-007**: El estado mostrado para cada host externo (Kuma, AdGuard) DEBE
  reflejar el ciclo de vigilancia más reciente disponible sin exigir que
  Miquel consulte Beszel por separado ni la base de datos de su hub a mano.
- **FR-008**: El mecanismo que lee el estado de Beszel para exponerlo en el
  dashboard DEBE registrar su propio latido, con el mismo patrón que ya usan
  `docker_monitor.py`, `ha_monitor.py`, `verify_backups.py`,
  `dns_pi_monitor.py` y `telegram_monitor.py`, y ese latido DEBE sumarse al
  panel "Estado de los monitores" que ya existe — este feature no puede
  introducir el único monitor del homelab sin que nadie vigile si sigue
  funcionando (Principio XIII).

### Key Entities

- **Alarma de contenedor**: derivada de `docker_monitor_state.json`.
  Atributos: contenedor afectado, si está caído, desde cuándo (si aplica).
  Ya calculada hoy; este feature solo la expone.
- **Estado de host externo**: derivado del estado que Beszel calcula sobre
  Uptime Kuma y AdGuard Home. Atributos: host afectado, arriba/caído/sin
  evidencia, momento del último dato disponible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Miquel puede ver, sin salir del dashboard, si algún contenedor
  estuvo caído en el ciclo de vigilancia más reciente de `docker_monitor.py`
  — hoy esa información no es visible en ningún sitio salvo Telegram en el
  momento exacto en que se envió.
- **SC-002**: Miquel puede ver, sin salir del dashboard, el estado de los dos
  hosts físicos que vigila Beszel — hoy requiere abrir la interfaz de Beszel
  por separado.
- **SC-003**: Ninguna de las 4 brechas de cobertura reales que el inventario
  de feature 001 identificó en las categorías `contenedor` y `host_externo`
  sigue apareciendo como brecha tras desplegar este feature (comprobable
  relanzando `python3 -m inventory.cli --gaps`).
- **SC-004**: Ante un fallo del propio mecanismo de lectura (el fichero de
  `docker_monitor.py` no existe, o no se puede leer el estado de Beszel), el
  dashboard sigue funcionando para el resto de paneles y muestra el elemento
  afectado como "sin evidencia" en vez de fallar en silencio o mostrar un
  falso "sano".
- **SC-005**: Si el mecanismo que lee el estado de Beszel deja de funcionar,
  Miquel se entera por el panel "Estado de los monitores" — no solo porque,
  días después, note que el dato de Kuma/AdGuard no se ha movido.

## Assumptions

- Este feature no incluye vigilar el propio Beszel (hub) ni los recordatorios
  de Tareas/Calendario de Nextcloud: ninguno de los dos tiene hoy una señal
  calculada que simplemente exponer — instrumentarlos exige decidir primero
  qué significa "sano" para cada uno, que es trabajo de `clarify`/`plan`
  propio y queda para un feature posterior (ver `BRIEFING.md`, sección
  "Feature 002 — material de partida").
- El dashboard ya existe (`http://homelab.amsterdam9.home/`) y ya lee
  ficheros de estado que otros monitores del homelab escriben (por ejemplo
  `ha_monitor_state.json`, incorporado el 2026-08-08); este feature sigue el
  mismo patrón en vez de introducir uno nuevo.
- El estado de Uptime Kuma y AdGuard Home que Beszel calcula vive hoy dentro
  del volumen de datos del hub de Beszel, no en un fichero ya accesible
  desde donde corre el dashboard — exponerlo implica un paso intermedio
  (cómo exactamente, se decide en el plan, no aquí), no leerlo en vivo desde
  el propio panel. Ese paso intermedio es el componente que necesita latido
  propio (FR-008): es código nuevo del homelab, y por tanto hereda la
  obligación de vigilancia del Principio XIII igual que cualquier otro.
- La cobertura y la vigilancia de los propios contenedores no cambian: este
  feature no toca `docker_monitor.py` ni su lógica de reinicio, solo expone
  lo que ya calcula.
