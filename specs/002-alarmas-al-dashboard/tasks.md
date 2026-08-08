---

description: "Task list for Alarmas Ya Calculadas al Panel del Dashboard"
---

# Tasks: Alarmas Ya Calculadas al Panel del Dashboard

**Input**: Design documents from `/specs/002-alarmas-al-dashboard/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ficheros.md, quickstart.md (todos presentes)

**Tests**: No se piden tests de contrato/integración explícitos en `spec.md`. `plan.md`
("Testing") sí pide el patrón `--selftest` de lógica pura ya usado por
`docker_monitor.py` y feature 001 para el script nuevo — se incluye como tarea de
implementación de ese script, no como fase de test aparte. El resto de verificación
es manual, vía `quickstart.md`.

**Organization**: Tareas agrupadas por historia de usuario (`spec.md`), en el orden
de prioridad P1 → P2, más una fase final de verificación cruzada.

**Nota de ubicación**: todo el código de este feature vive **fuera de este
repositorio**, en la máquina privada del homelab (`/Volumes/FastData/homelab/` —
mismo patrón que estableció feature 001, ver `plan.md` "Nota de límite del repo").
Los paths de las tareas son relativos a esa raíz privada, no a este repo público.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencia de una
  tarea sin terminar)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2)
- Cada tarea incluye la ruta exacta del fichero que toca

---

## Phase 1: Setup

Sin tareas. `plan.md` ("Project Structure", "Structure Decision") es explícito: no
hay proyecto nuevo que inicializar — un script nativo más sobre infraestructura que
ya existe y un parche a un servicio ya desplegado. El directorio de salida
(`docker/homelab-orchestrator/data/`) ya existe y ya está montado en `/data` dentro
del contenedor del dashboard (`data-model.md`).

---

## Phase 2: Foundational

Sin tareas bloqueantes. Las dos historias son independientes por diseño (`spec.md`,
"Independent Test" de cada una; `plan.md` no identifica ningún prerrequisito
compartido): US1 solo toca `get_containers()` en `app.py`; US2 es un script nuevo
más tres puntos de extensión en `app.py` que no dependen de lo que haga US1. Pueden
implementarse en cualquier orden o en paralelo — se listan P1 antes que P2 solo por
prioridad de entrega, no por dependencia técnica.

---

## Phase 3: User Story 1 - Ver en el dashboard cuándo un contenedor estuvo caído (Priority: P1) 🎯 MVP

**Goal**: El dashboard muestra, en la propia tarjeta de cada contenedor, si
`docker_monitor.py` lo marcó caído en su ciclo más reciente y desde cuándo — sin
crear ninguna fila ni sección nueva (Clarification 1, FR-001, FR-003).

**Independent Test**: Parar (o simular la caída de) un contenedor no crítico entre
dos ciclos de `docker_monitor.py` y comprobar que el dashboard refleja el episodio,
mientras persiste y también una vez recuperado — sin depender de ninguna otra parte
de este feature (`spec.md`, US1 "Independent Test"; `quickstart.md` §1).

### Implementation for User Story 1

- [X] T001 [US1] En `get_containers()` de `docker/homelab-dashboard/scripts/app.py`,
  leer `docker_monitor_state.json` (mismo directorio `/data` ya montado) y fusionar
  `down_since` en cada contenedor cruzando por la clave `container:<nombre>` — mismo
  nombre que ya expone `docker ps` (`data-model.md` "Alarma de contenedor";
  `research.md` §1). Si el fichero no existe o no se puede leer, `get_containers()`
  DEBE seguir devolviendo el estado en vivo de `docker ps` sin `down_since` para
  ningún contenedor, sin tumbar el panel (`contracts/ficheros.md`, garantía de
  `get_containers()`).
- [X] T002 [US1] En el render HTML/JS de la tarjeta de contenedor de
  `docker/homelab-dashboard/scripts/app.py`, mostrar "Caído desde `<fecha>`" cuando
  `down_since` no sea nulo, en la misma fila donde ya se ve el estado en vivo — nunca
  como alarma separada (Clarification 1, FR-003). Depende de T001.
- [X] T003 [US1] Validar manualmente los 3 escenarios de aceptación de User Story 1
  siguiendo `quickstart.md` §1: contenedor caído muestra "caído desde"; tras
  recuperarse, la marca persiste hasta el siguiente ciclo relevante; un contenedor
  sano no muestra ninguna marca. Depende de T001, T002.

**Checkpoint**: User Story 1 funciona y es verificable de forma independiente — MVP
entregable.

---

## Phase 4: User Story 2 - Ver en el dashboard el estado de los hosts que vigila Beszel (Priority: P2)

**Goal**: El dashboard muestra el estado que Beszel ya calcula sobre el host de
Uptime Kuma y el host de AdGuard Home, sin abrir la interfaz de Beszel ni consultar
su base de datos a mano (FR-002, FR-007).

**Independent Test**: Comprobar que el estado de ambos hosts en el dashboard
coincide con el estado que muestra Beszel para esos mismos sistemas en un momento
dado — no requiere que User Story 1 esté terminada (`spec.md`, US2 "Independent
Test"; `quickstart.md` §2).

### Implementation for User Story 2

- [X] T004 [US2] Crear `scripts/beszel_hosts_monitor.py`: consulta la tabla
  `systems` del hub de Beszel vía
  `docker run --rm -v beszel_hub_data:/data python:3.11-alpine python3 -c "..."`
  (stdlib `sqlite3`, sin dependencias externas — `research.md` §3, §6), extrae
  `status` y `beszel_name` para `"Host de Uptime Kuma"` / `"Host de AdGuard Home
  (DNS primario)"`, y escribe
  `docker/homelab-orchestrator/data/beszel_hosts.json` con el esquema de
  `data-model.md` ("Estado de host externo"). Si la consulta falla, no responde, o
  falta alguno de los dos hosts, el script NO reescribe el fichero — lo deja
  envejecer (`contracts/ficheros.md`, garantías 1-3: solo lectura contra Beszel,
  nunca dato a medias).
- [X] T005 [US2] Añadir `heartbeat.write("beszel-hosts", ...)` al final de cada
  ciclo exitoso de `scripts/beszel_hosts_monitor.py`, mismo mecanismo que
  `docker_monitor.py`/`ha_monitor.py` (FR-008, `research.md` §4,
  `data-model.md` "Latido del mecanismo nuevo"). Depende de T004.
- [X] T006 [US2] Añadir modo `--selftest` a `scripts/beszel_hosts_monitor.py` que
  valide, contra datos de ejemplo y sin tocar Beszel ni Docker reales: el parseo de
  la salida de `sqlite3` y la decisión de no escribir el fichero cuando falta un
  host o la consulta falla (`plan.md` "Testing"). Depende de T004.
- [X] T007 [P] [US2] Crear
  `docker/homelab-dashboard/amsterdam9.beszel.hosts-reader.plist`: LaunchAgent con
  `StartInterval` de 300 s apuntando a `scripts/beszel_hosts_monitor.py`, mismo
  patrón que `amsterdam9.dashboard.socat`/`dump_socat_status.py`, usando el
  intérprete `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`
  (`research.md` §5; Regla 10 del `CLAUDE.md` general del homelab). Fichero
  independiente de `app.py` — no bloquea ni depende de T008-T010.
- [X] T008 [P] [US2] Implementar `get_external_hosts()` en
  `docker/homelab-dashboard/scripts/app.py`: lee `beszel_hosts.json`, y decide
  `arriba`/`caído`/`sin evidencia` según la antigüedad de `generated_at` (o el
  `mtime` del fichero) frente al umbral de 15 min, y según si el latido
  `beszel-hosts` está presente (FR-002, FR-004, `research.md` §2). Fichero distinto
  de T004-T007 — sin dependencia de código con el script (solo comparten el
  contrato de `beszel_hosts.json`, ya fijado en `data-model.md`).
- [X] T009 [US2] En `docker/homelab-dashboard/scripts/app.py`, añadir la entrada
  `("beszel-hosts", "Estado de hosts externos (Beszel)", 900)` a `MONITOR_JOBS` y su
  descripción correspondiente en `MONITOR_INFO`, para que aparezca en el panel
  "Estado de los monitores" que ya existe (FR-008, `research.md` §4). Depende de
  T008 (mismo fichero).
- [X] T010 [US2] En `collect()` de `docker/homelab-dashboard/scripts/app.py`, sumar
  `external_hosts` usando `get_external_hosts()`. Depende de T008.
- [X] T011 [US2] En el render HTML/JS de `docker/homelab-dashboard/scripts/app.py`,
  añadir la sección de hosts externos ("Host de Uptime Kuma", "Host de AdGuard Home
  (DNS primario)") mostrando arriba/caído/sin evidencia, sin construir ningún portal
  nuevo (FR-005, FR-007). Depende de T010.
- [X] T012 [US2] Validar manualmente User Story 2 siguiendo `quickstart.md` §2-3:
  comparar la consulta directa a Beszel con lo que muestra el dashboard; parar el
  LaunchAgent (`launchctl bootout gui/$(id -u)/amsterdam9.beszel.hosts-reader`) y
  esperar más de 15 min, y comprobar que el dashboard pasa a "sin evidencia" y que
  la fila `beszel-hosts` aparece en rojo en "Estado de los monitores" (SC-004,
  SC-005). Depende de T004-T011.

**Checkpoint**: User Stories 1 y 2 funcionan, cada una verificable de forma
independiente.

---

## Phase 5: Verificación cruzada (cierre de las brechas)

**Purpose**: Confirmar las garantías que cruzan ambas historias — resiliencia
general del dashboard y el cierre real de las brechas que motivaron el feature.

- [X] T013 Validar `quickstart.md` §4 (SC-004): renombrar temporalmente
  `docker_monitor_state.json`, recargar el dashboard, y comprobar que el resto de
  paneles (sistema, discos, crons, LaunchAgents, inventario de cobertura, y la
  sección de hosts externos de US2) siguen funcionando con normalidad — solo el dato
  de "caído desde" desaparece, sin que la página falle. Restaurar el fichero.
  Depende de T003, T012.
- [X] T014 Validar `quickstart.md` §5 (SC-003): relanzar
  `python3 -m inventory.cli --gaps --no-telegram --no-dashboard` desde este repo y
  comprobar que ninguna brecha de categoría `contenedor`, ni de `host_externo` para
  "Host de Uptime Kuma" / "Host de AdGuard Home (DNS primario)", sigue apareciendo
  en el listado. Depende de T013.

**Checkpoint**: Feature 002 completo — 3 de las 4 brechas reales identificadas en
`BRIEFING.md` ("Feature 002 — material de partida") cerradas.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: sin tareas — ver rationale en cada fase.
- **User Story 1 (Phase 3)**: sin dependencia de Foundational (no hay) ni de US2.
- **User Story 2 (Phase 4)**: sin dependencia de US1 — puede empezar en paralelo.
- **Verificación cruzada (Phase 5)**: depende de que **ambas** historias estén
  terminadas (T003 y T012).

### Within User Story 1

T001 → T002 → T003 (mismo fichero, orden estricto: leer el dato antes de
mostrarlo, mostrar antes de validar).

### Within User Story 2

T004 → T005 (mismo fichero, latido depende del ciclo ya funcionando)
T004 → T006 (mismo fichero, selftest depende de que exista el script)
T007 independiente de T004-T006 (fichero distinto, solo referencia la ruta ya
fijada en `plan.md`)
T008 independiente de T004-T007 (fichero distinto, solo comparte el contrato de
`beszel_hosts.json`)
T008 → T009 → T010 → T011 (mismo fichero `app.py`, orden estricto: decidir el
estado antes de exponerlo en `MONITOR_JOBS`/`collect()`/render)
T012 depende de T004-T011 (valida el conjunto)

### Parallel Opportunities

- T007 (plist) puede avanzar en paralelo con T004-T006 (script) y con T008 (función
  nueva en `app.py`) — tres ficheros distintos, sin dependencia de código entre
  ellos.
- User Story 1 completa (T001-T003) puede avanzar en paralelo con User Story 2
  completa (T004-T012) — historias independientes por diseño.

---

## Parallel Example: arrancar ambas historias a la vez

```bash
# Historia 1 (un desarrollador/sesión):
Task: "T001 [US1] Leer docker_monitor_state.json en get_containers()"

# Historia 2, en paralelo (otro desarrollador/sesión):
Task: "T004 [US2] Crear scripts/beszel_hosts_monitor.py"
Task: "T007 [P] [US2] Crear amsterdam9.beszel.hosts-reader.plist"
Task: "T008 [P] [US2] Implementar get_external_hosts() en app.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 sola)

1. T001 → T002 → T003.
2. **Parar y validar**: es la entrega de menor esfuerzo y mayor valor
   (`spec.md`, "Why this priority" de US1) — cierra el caso que motivó el proyecto
   entero (49 reinicios de `beszel` sin alerta visible).
3. Desplegar/demo si está listo — no depende de US2 para tener valor por sí sola.

### Incremental Delivery

1. User Story 1 → validar → desplegar (MVP).
2. User Story 2 → validar → desplegar.
3. Verificación cruzada (T013-T014) → cierre formal de `SC-003`/`SC-004`.

---

## Notes

- [P] = ficheros distintos, sin dependencia de código.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Sin tareas de test de contrato/integración: no se piden en `spec.md`; el
  `--selftest` de T006 y la validación manual vía `quickstart.md` son la
  verificación de este feature, mismo patrón que el resto del homelab.
- Ninguna tarea de este feature toca `docker_monitor.py` ni cambia su lógica de
  reinicio (`spec.md`, Assumptions) — todas las tareas son de lectura/exposición.
- Ninguna tarea introduce credenciales nuevas ni toca la API HTTP de Beszel
  (`research.md` §3, riesgo aceptado explícitamente) — todo el acceso es local vía
  el volumen `beszel_hub_data`.
- **Hallazgo durante T014**: SC-003 no se cumplía solo con T001-T012 — el propio
  `src/inventory/evaluate.py` de feature 001 (dentro de este repo, a diferencia del
  resto del feature) tenía hardcodeado `llega_a_dashboard="no"` para la categoría
  `host_externo`, con el comentario "hoy no está disponible aquí". Ese hecho dejó de
  ser cierto al desplegar T004-T012. Corregido para comprobar el latido real de
  `beszel-hosts` (mismo patrón que el resto de `evaluate.py`), igual que ya se hizo
  dos veces antes en este proyecto para HA y para "Estado de los monitores" (ver
  `git log`). Sin esta corrección, el inventario habría seguido reportando una
  brecha ya cerrada — divergencia entre el spec (SC-003) y el código, que
  `CLAUDE.md` trata como defecto del código.
