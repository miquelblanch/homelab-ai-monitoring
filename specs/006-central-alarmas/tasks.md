---

description: "Task list for Central de Alarmas del Homelab"
---

# Tasks: Central de Alarmas del Homelab

**Input**: Design documents from `/specs/006-central-alarmas/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-alarms.md, quickstart.md (todos presentes)

**Tests**: No se piden tests de contrato/integración explícitos en `spec.md`.
`plan.md` ("Testing") confirma que `app.py` no tiene suite automática en este
repo privado — la verificación es `quickstart.md`, mismo patrón que features
002/003.

**Organization**: Tareas agrupadas por historia de usuario (`spec.md`), en
orden de prioridad P1 → P2 → P3, más una fase de Foundational (ver Notes:
las tres historias comparten una única función backend) y una fase final de
verificación cruzada.

**Nota de ubicación**: todo el código de este feature vive **fuera de este
repositorio**, en `homelab-dashboard/scripts/app.py` (privado) — a
diferencia de feature 003, ninguna tarea toca `src/inventory/` (`plan.md`,
"Project Structure": el origen "inventario de cobertura" se consume tal
cual, sin regla de evaluación nueva).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencia
  de una tarea sin terminar)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta exacta del fichero que toca

---

## Phase 1: Setup

Sin tareas. Mismo criterio que features 002/003: no hay proyecto nuevo que
inicializar — una ampliación más del único servicio web que ya existe
(`plan.md`, "Structure Decision").

---

## Phase 2: Foundational

**Purpose**: Construir la única función backend (`get_active_alarms()`) y su
catálogo de tipos (`ALARM_TYPES`) de los que dependen las tres historias de
usuario. No tiene sentido dividir esta función entre historias: las tres
leen la misma lista de alarmas, y `nivel`/`explicacion`/`remediacion` salen
de la misma entrada de `ALARM_TYPES` a la vez (`data-model.md`) — separarla
significaría reescribir la misma función tres veces. Lo que sí se divide por
historia es la capa de presentación (Phases 3-5).

**⚠️ CRITICAL**: Ninguna historia de usuario es visible en el dashboard
hasta que esta fase esté completa.

- [X] T001 En `docker/homelab-dashboard/scripts/app.py`, añadir la constante
  `ALARM_GROUP_THRESHOLD = 5` (`research.md` §3) y el diccionario
  `ALARM_TYPES` con las 19 entradas de `data-model.md` ("Tipo de alarma —
  catálogo `ALARM_TYPES`"), copiando `nivel`/`explicacion`/`remediacion` tal
  cual — incluida la variante `contenedor_caido_critico` con la advertencia
  de no tocar sin aprobación (FR-007) y el tipo genérico `origen_sin_datos`
  (Edge Cases, `spec.md`). Mismo patrón de ubicación que `MONITOR_INFO`.
- [X] T002 En `docker/homelab-dashboard/scripts/app.py`, implementar
  `get_active_alarms()`: para cada uno de los 10 orígenes
  (`get_containers()`/`get_docker_monitor_state()`, `get_ha_monitor()`,
  `get_backup_heartbeat()`, `get_monitor_heartbeats()`, `get_socat_relays()`,
  `get_external_hosts()`, `get_beszel_hub_status()`,
  `get_launchagents()`/`get_crons()`, `get_disks()`, `get_inventory()`),
  recorrer sus condiciones de fallo activas (respetando lo que cada origen ya
  marca como intencionado/falso positivo conocido, FR-011) y construir una
  "Alarma activa" por cada una (`data-model.md`: `origen`, `tipo`, `nivel`,
  `componente`, `mensaje`, `explicacion`, `remediacion`, `antiguedad_s`
  opcional, `agrupada`, `cantidad`), usando `ALARM_TYPES` (T001) para
  `nivel`/`explicacion`/`remediacion` — si el `tipo` no existe en el
  catálogo, usar los textos fijos de "sin explicación/remediación
  documentada todavía" (FR-008) en vez de omitir la alarma. Si la lectura de
  un origen falla, añadir una alarma `origen_sin_datos` para ese origen en
  vez de propagar la excepción (contrato §6). Depende de T001 (mismo
  fichero, necesita `ALARM_TYPES` ya definido).
- [X] T003 En `get_active_alarms()` (mismo fichero, continuación de T002),
  aplicar la agrupación de cascada: cuando más de `ALARM_GROUP_THRESHOLD`
  alarmas compartan `(origen, tipo)`, colapsarlas en una sola entrada con
  `agrupada=true` y `cantidad=N` (FR-013, `research.md` §3); después, ordenar
  la lista resultante por `nivel` (crítico → aviso → informativo) y, dentro
  del mismo nivel, por `antiguedad_s` descendente cuando exista (FR-004).
  Depende de T002 (misma función).
- [X] T004 En `collect()` (o el punto equivalente donde se construye la
  respuesta de `/api/data`) de `docker/homelab-dashboard/scripts/app.py`,
  añadir la clave `"alarms": {"total": ..., "items": [...]}` usando
  `get_active_alarms()`, con `total` igual al número de entradas de `items`
  (no la suma de `cantidad`, contrato §2). Depende de T003.
- [X] T005 Validar la Fase Foundational contra `contracts/api-alarms.md`:
  `curl -s http://homelab.amsterdam9.home/api/data | python3 -m json.tool | grep -A5 '"alarms"'`
  y comprobar que, con el homelab sano, devuelve `"total": 0, "items": []`
  (nunca la clave ausente, garantía 4 del contrato). Depende de T004.

**Checkpoint**: `get_active_alarms()` completa y expuesta en `/api/data` —
las tres historias de usuario pueden empezar su capa de presentación.

---

## Phase 3: User Story 1 - Ver de un vistazo todo lo que está roto en el homelab (Priority: P1) 🎯 MVP

**Goal**: Una pestaña nueva "Alarmas" en el dashboard muestra, en una sola
lista ordenada por gravedad, el origen y el componente afectado de cada
alarma activa — o un mensaje explícito si no hay ninguna (FR-001, FR-003,
FR-004, FR-010).

**Independent Test**: Con al menos un origen en fallo real, abrir la
pestaña y comprobar que la alarma aparece listada; con el homelab sano,
comprobar el mensaje explícito de "sin alarmas" (`spec.md`, US1;
`quickstart.md` §1).

### Implementation for User Story 1

- [X] T006 [US1] En la plantilla HTML de `docker/homelab-dashboard/scripts/app.py`,
  añadir el enlace `<a href="#alarmas" data-page="alarmas">` a `#top-nav` y
  la sección `<section class="panel" id="alarmas" hidden>` con su
  `panel-head` y un `<div id="alarmas-body">` para las filas — mismo patrón
  estructural que la pestaña Inventario (`#cobertura`).
- [X] T007 [US1] En el JS embebido del mismo fichero, añadir `"alarmas"` al
  array `PAGES` de la función `showPage()` para que la navegación y el
  `hidden` toggling la reconozcan. Depende de T006 (necesita que exista el
  `id="alarmas"`).
- [X] T008 [US1] Implementar `renderAlarmas(alarms)` en el JS embebido:
  recorre `alarms.items` (ya vienen ordenados por el backend, T003 — no
  reordenar en JS) y pinta, por cada uno, `origen`, `componente` y
  `mensaje`, con un `status-dot`/color según `nivel` reutilizando los tokens
  `--crit`/`--warn` ya existentes (`levelClass`/`dotClass`, `research.md`
  §4) y una variante neutra para `informativo`; si `agrupada` es `true`,
  mostrar `cantidad` junto al componente (p. ej. "23 entidades de Home
  Assistant"). Llamar a `renderAlarmas(d.alarms)` desde `render(d)`. Depende
  de T004 (necesita la clave `alarms`) y T007.
- [X] T009 [US1] En `renderAlarmas()` (mismo fichero, continuación de T008),
  cuando `alarms.total === 0`, mostrar un mensaje explícito positivo ("Sin
  alarmas activas ahora mismo") en `#alarmas-body` en vez de una lista vacía
  (FR-010, escenario 2 de US1). Depende de T008.
- [X] T010 [US1] Reconstruir y recrear el contenedor
  (`docker compose up -d --build dashboard`, `plan.md`) y validar
  manualmente User Story 1 siguiendo `quickstart.md` §1: confirmar el
  mensaje de "sin alarmas" con el homelab sano; `docker stop qbittorrent`,
  recargar la pestaña y confirmar que aparece la alarma con origen y
  componente identificados; `docker start qbittorrent` para restaurar.
  Depende de T009.

**Checkpoint**: User Story 1 funciona y es verificable de forma
independiente — MVP entregable.

---

## Phase 4: User Story 2 - Entender qué significa cada alarma sin investigarla (Priority: P2)

**Goal**: Cada alarma de la lista trae, además de lo de US1, una
explicación en prosa de qué implica el fallo — o el aviso fijo de que no
existe todavía para ese tipo (FR-005, FR-008).

**Independent Test**: Para un tipo de alarma con texto ya escrito en
`ALARM_TYPES`, comprobar que se muestra la frase en prosa, no solo el dato
técnico bruto (`spec.md`, US2; `quickstart.md` §2).

### Implementation for User Story 2

- [X] T011 [P] [US2] En `renderAlarmas()` (mismo fichero que T008), añadir
  bajo cada fila el texto de `explicacion` — ya viene resuelto desde el
  backend (T002: texto real o el aviso fijo de "sin explicación documentada
  todavía" cuando el `tipo` no está en `ALARM_TYPES`), así que esta tarea es
  puramente de presentación, sin lógica de fallback nueva en JS. Depende de
  T008 (misma función, pero es una adición de marcado sin tocar la lógica
  de T008/T009 — se marca `[P]` porque no reabre esas líneas).
  **Nota de implementación**: se construyó junto con T008 en un solo paso
  (la fila ya salía completa con `explicacion` desde el primer commit) —
  no hizo falta una segunda edición separada.
- [X] T012 [US2] Validar manualmente User Story 2 siguiendo
  `quickstart.md` §2: confirmar que la alarma de T010
  (`contenedor_caido`) muestra la explicación real de `ALARM_TYPES`: y, con
  un tipo sintético fuera del catálogo (o revisando el camino de código),
  confirmar que se muestra el aviso fijo en vez de ocultar la fila (FR-008,
  escenario 2 de US2). Depende de T011.

**Checkpoint**: User Stories 1 y 2 funcionan, cada una verificable de forma
independiente.

---

## Phase 5: User Story 3 - Tener una sugerencia de qué hacer, sin que nada se ejecute solo (Priority: P3)

**Goal**: Cada alarma trae también una remediación sugerida en texto —
incluida la advertencia especial para contenedores críticos (FR-007) — sin
ningún control que ejecute nada (FR-006, FR-008, FR-009).

**Independent Test**: Confirmar el texto de remediación en una alarma real,
y que ninguna interacción de la pestaña dispara una petición distinta de
`GET` (`spec.md`, US3; `quickstart.md` §3).

### Implementation for User Story 3

- [X] T013 [US3] En `renderAlarmas()` (mismo fichero que T011), añadir bajo
  cada fila el texto de `remediacion` — igual que T011, ya resuelto desde el
  backend (T002), incluida la variante de advertencia para
  `contenedor_caido_critico` (FR-007). No añadir ningún elemento interactivo
  que dispare una petición de escritura — la fila es puramente informativa.
  Depende de T011 (misma función, misma fila).
  **Nota de implementación**: igual que T011, ya salió completa desde T008
  (incluida la conversión de `**texto**` a negrita para que la advertencia
  de FR-007 se vea destacada, no como asteriscos literales).
- [X] T014 [US3] Validar manualmente User Story 3 siguiendo
  `quickstart.md` §3: confirmar el texto de remediación en la alarma de
  T010; por inspección de código (sin parar un contenedor crítico real),
  confirmar que `ALARM_TYPES["contenedor_caido_critico"].remediacion` lleva
  la advertencia de no tocar sin aprobación; con la pestaña Network del
  navegador abierta, confirmar que interactuar con la pestaña Alarmas solo
  genera peticiones `GET` a `/api/data`. Depende de T013.

**Checkpoint**: Las tres historias de usuario funcionan, cada una
verificable de forma independiente — feature completo en su alcance de
detección pura (sin remediación automática, FR-009/FR-015).

---

## Phase 6: Verificación cruzada (cierre)

**Purpose**: Confirmar las garantías que cruzan las tres historias —
agrupación de cascada, orden por gravedad, resiliencia del dashboard, y que
el recuento mostrado coincide con la realidad.

- [X] T015 Validar `quickstart.md` §4 (FR-013, agrupación de cascada): con
  datos sintéticos contra `get_active_alarms()` en un entorno de prueba
  (nunca contra producción), confirmar que más de `ALARM_GROUP_THRESHOLD`
  alarmas del mismo `(origen, tipo)` colapsan en una entrada con
  `agrupada=true` y `cantidad` igual al número real. Depende de T003.
- [X] T016 Validar `quickstart.md` §5 (FR-004, orden por gravedad): con al
  menos dos alarmas activas de niveles distintos a la vez, confirmar que la
  de nivel Crítico aparece primero en la pestaña, sin importar cuál se
  activó antes. Depende de T010.
- [X] T017 Validar `quickstart.md` §6 (SC-004, resiliencia, contrato §6):
  renombrar temporalmente `ha_monitor_state.json`, recargar el dashboard, y
  confirmar que el resto de pestañas siguen funcionando y que la pestaña
  Alarmas muestra una entrada `origen_sin_datos` para `ha` en vez de fallar
  o quedar en blanco. Restaurar el fichero. Depende de T010.
- [X] T018 Validar `quickstart.md` §7 (SC-005, recuento coincide): comparar
  el total de alarmas de `origen: "contenedores"` (sumando `cantidad`)
  contra lo que la propia pestaña Docker ya muestra como caído, sin
  duplicados ni ausencias. Depende de T010, T012, T014.
- [X] T019 Validar `quickstart.md` §1 (escenario 3 de US1, FR-012):
  provocar dos orígenes en fallo a la vez (`qbittorrent` parado +
  `ha_monitor_state.json` renombrado) y confirmar que `alarms.items` trae
  dos entradas independientes, no fusionadas. Restaurar ambas cosas.
  Depende de T010, T017. Cierra el hallazgo E3 de `/speckit-analyze`.
- [X] T020 Validar `quickstart.md` §8 (FR-011, no reevaluar intencionados):
  confirmar que `frigate` (parado a propósito, `NEVER_RESTART`) no genera
  ninguna alarma `contenedor_caido` pese a no estar `running`. Depende de
  T010. Cierra el hallazgo E1 de `/speckit-analyze`.
- [X] T021 Validar `quickstart.md` §9 (FR-014, antigüedad opcional):
  confirmar que una alarma de `origen: "discos"` trae `antiguedad_s: null`
  — o, en su defecto, por inspección de código de `get_active_alarms()`.
  Depende de T010. Cierra el hallazgo E2 de `/speckit-analyze`.

**Checkpoint**: Feature 006 completo — pestaña Alarmas operativa sobre los
10 orígenes, sin ninguna acción automática ni dependencia de IA (FR-009,
FR-015).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: sin tareas.
- **Foundational (Phase 2)**: sin dependencias externas — BLOQUEA las tres
  historias de usuario.
- **User Story 1 (Phase 3)**: depende de Foundational. Sin dependencia de
  US2/US3.
- **User Story 2 (Phase 4)**: depende de Foundational **y** de que exista la
  fila base de US1 (T008) — el texto de explicación se añade a una fila que
  US1 ya pinta (mismo orden de capas que describe `spec.md`, "Why this
  priority" de US2).
- **User Story 3 (Phase 5)**: depende de Foundational y de US2 (T011) por el
  mismo motivo — añade una línea más a la misma fila.
- **Verificación cruzada (Phase 6)**: depende de que las tres historias
  estén terminadas.

### Within Foundational

T001 → T002 → T003 → T004 → T005 (una sola función construida en el mismo
fichero; cada tarea añade sobre la anterior, sin trabajo independiente que
paralelizar).

### Within User Story 1

T006 → T007 → T008 → T009 → T010 (misma sección de la plantilla y del JS;
orden estricto porque cada paso necesita el `id`/función anterior).

### Within User Story 2 y 3

T011 (tras T008) → T012; T013 (tras T011) → T014. T011 se marca `[P]`
porque es una adición de marcado que no reabre las líneas que tocan T008/T009,
aunque comparta fichero.

### Parallel Opportunities

Casi ninguna: las tres historias y la fase Foundational viven en el mismo
fichero (`app.py`), a diferencia de feature 003, donde cada historia tenía
ficheros propios. La única tarea marcada `[P]` es T011, por no competir con
las líneas que T008/T009 ya escribieron. Las tareas de validación
(T015-T018) no producen código y pueden ejecutarse en cualquier orden entre
sí una vez cumplidas sus dependencias, pero no se marcan `[P]` por ser pasos
manuales secuenciales, mismo criterio que features 002/003.

---

## Implementation Strategy

### MVP First (User Story 1 sola)

1. Completar Foundational (T001-T005) — sin esto, ninguna historia es
   visible.
2. Completar User Story 1 (T006-T010).
3. **Parar y validar**: la lista agregada por sí sola ya cumple el valor
   mínimo del feature ("de un vistazo", `spec.md`) — MVP entregable antes de
   escribir ninguna explicación ni remediación.

### Incremental Delivery

1. Foundational → User Story 1 → validar → desplegar (MVP).
2. User Story 2 → validar → desplegar (añade explicación).
3. User Story 3 → validar → desplegar (añade remediación sugerida).
4. Verificación cruzada (T015-T018) → cierre formal de `SC-004`/`SC-005` y
   de los dos edge cases de `/speckit-clarify` (cascada, orden).

---

## Notes

- `[P]` = no reabre líneas ya escritas por otra tarea, aunque comparta
  fichero — no "ficheros distintos" como en features anteriores, porque
  este feature entero vive en un único fichero (`plan.md`, "Structure
  Decision").
- `[Story]` mapea cada tarea a su historia de usuario para trazabilidad.
- Sin tareas de test de contrato/integración: no se piden en `spec.md`; la
  validación manual vía `quickstart.md` es la verificación de este feature,
  mismo patrón que el resto del homelab-dashboard.
- T002 es la tarea con más superficie de este feature (los 10 orígenes a la
  vez) — si conviene dividirla en sub-pasos durante `/speckit-implement`
  (uno por origen), hacerlo dentro de la misma T002 en vez de crear tareas
  nuevas: sigue siendo una sola función, un solo checkpoint de "terminada".
- FR-009 y FR-015 (sin acciones ejecutables, sin IA/tokens) no tienen tarea
  propia — son propiedades que NINGUNA tarea de este feature debe violar,
  verificadas explícitamente en T014.
- Ninguna tarea de este feature toca `docker_monitor.py`, `ha_monitor.py`,
  ni ningún script de origen — todas leen datos que esos procesos ya
  escriben (FR-002).
