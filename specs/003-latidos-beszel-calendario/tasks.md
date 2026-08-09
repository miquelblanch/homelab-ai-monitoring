---

description: "Task list for Latido Propio — Recordatorios de Nextcloud y Beszel (Hub)"
---

# Tasks: Latido Propio — Recordatorios de Nextcloud y Beszel (Hub)

**Input**: Design documents from `/specs/003-latidos-beszel-calendario/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ficheros.md, quickstart.md (todos presentes)

**Tests**: No se piden tests de contrato/integración explícitos en `spec.md`. `plan.md`
("Testing") pide ampliar el `--selftest` ya existente de `beszel_hosts_monitor.py`
(feature 002) — se incluye como tarea de implementación de ese script, no como fase
de test aparte. El cambio en `bautista-calendar.sh` (bash) no tiene suite propia en
el homelab; se valida con `quickstart.md`, igual que el resto de scripts bash del
proyecto.

**Organization**: Tareas agrupadas por historia de usuario (`spec.md`), en orden de
prioridad P1 → P2, más una fase final de verificación cruzada.

**Nota de ubicación**: la mayoría del código de este feature vive **fuera de este
repositorio**, en la máquina privada del homelab (mismo patrón que features 001 y
002). La excepción es `src/inventory/evaluate.py`, dentro de este repo — ver
`plan.md`, "Project Structure", sobre por qué esta vez va previsto desde el plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencia de una
  tarea sin terminar)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2)
- Cada tarea incluye la ruta exacta del fichero que toca

---

## Phase 1: Setup

Sin tareas. Igual que feature 002, no hay proyecto nuevo que inicializar — dos
ficheros existentes ampliados y un parche más al servicio web que ya existe
(`plan.md`, "Structure Decision").

---

## Phase 2: Foundational

Sin tareas bloqueantes. Las dos historias son independientes por diseño (`spec.md`,
"Independent Test" de cada una): User Story 1 solo toca `bautista-calendar.sh`,
`MONITOR_JOBS`/`MONITOR_INFO` de `app.py`, y la categoría `integracion` de
`evaluate.py`; User Story 2 solo toca `beszel_hosts_monitor.py`, otras partes de
`app.py`, y la categoría `infra_monitorizacion` de `evaluate.py`. Ningún fichero se
edita por las dos historias a la vez.

---

## Phase 3: User Story 1 - Saber si los recordatorios de Nextcloud se han ejecutado hoy (Priority: P1) 🎯 MVP

**Goal**: El panel "Estado de los monitores" del dashboard muestra si el cron de
recordatorios de las 10:00 se ejecutó hoy, tanto si mandó recordatorios, como si
calló porque no había eventos, como si detectó y reportó un error real (FR-001,
FR-002).

**Independent Test**: Dejar pasar un día normal (con o sin eventos) y comprobar que
el panel refleja que el cron se ejecutó, sin depender de si mandó o no un mensaje
por Telegram — y, provocando que el cron no llegue a correr, comprobar que el panel
lo refleja como caducado al cabo de un tiempo razonable (`spec.md`, US1
"Independent Test"; `quickstart.md` §1).

### Implementation for User Story 1

- [X] T001 [US1] En `scripts/bautista-calendar.sh`, añadir una llamada a
  `heartbeat.write("bautista-calendar", ...)` justo después de calcular `OUTPUT` y
  antes del `exit 0` de silencio (mismo patrón inline `$PY -c "..."` que ya usa el
  script para leer las credenciales de Telegram). El `detail` DEBE ser una de tres
  etiquetas fijas elegidas por el propio script —
  `"recordatorios enviados"` / `"sin eventos hoy"` / `"error real detectado"` —
  nunca el contenido de `$OUTPUT` (`research.md` §1: interpolar texto de eventos de
  calendario sin escapar en un `python3 -c` es una inyección de comandos). Si el
  script falla antes de este punto (p. ej. sin credenciales), el latido de ese día
  no se escribe — es el comportamiento correcto, no hace falta código adicional
  para ese caso (Edge Cases, `spec.md`).
- [X] T002 [P] [US1] En `docker/homelab-dashboard/scripts/app.py`, añadir la
  entrada `("bautista-calendar", "Recordatorios de Nextcloud (calendario)", 108000)`
  a `MONITOR_JOBS` y su descripción correspondiente en `MONITOR_INFO` (FR-002,
  `research.md` §2 — 108000 s / 30 h, mismo margen que `verify-backups`). Fichero
  distinto de T001, sin dependencia de código.
- [X] T003 [P] [US1] En `src/inventory/evaluate.py`, función
  `_vigilancia_integracion()`: sustituir el hardcode
  `if nombre.startswith("Recordatorios de Nextcloud"): return False, False, None, "no"`
  por una comprobación real vía `_vigilancia_por_heartbeat("bautista-calendar",
  "bautista-calendar.sh (latido propio)", 108000)`, con `declarado`/`llega` derivados
  del resultado (mismo patrón que ya usa `_vigilancia_telegram()` en el mismo
  fichero). Fichero distinto de T001/T002, sin dependencia de código — solo
  comparte el nombre del job con T001.
- [X] T004 [US1] Validar manualmente los 3 escenarios de aceptación de User Story 1
  siguiendo `quickstart.md` §1: ejecutar el cron con eventos (latido + mensaje);
  ejecutar sin eventos (latido, sin mensaje); simular que no corre y comprobar que
  el panel lo marca caducado pasadas 30 h. Depende de T001, T002, T003.

**Checkpoint**: User Story 1 funciona y es verificable de forma independiente — MVP
entregable.

---

## Phase 4: User Story 2 - Saber si Beszel (hub) ha dejado de vigilar de verdad (Priority: P2)

**Goal**: El panel "Estado de los monitores" muestra si Beszel ha dejado de tener
datos frescos de los 3 sistemas que vigila a la vez (Mac Mini, Uptime Kuma, AdGuard
Home) — nunca por un solo sistema individual, que ya tiene su propia alarma
(FR-003, FR-004, FR-005).

**Independent Test**: Comprobar que el panel refleja el mismo estado de frescura de
datos que se ve consultando directamente la base de datos del hub de Beszel en un
momento dado — no requiere que User Story 1 esté terminada (`spec.md`, US2
"Independent Test"; `quickstart.md` §2-4).

### Implementation for User Story 2

- [X] T005 [US2] En `scripts/beszel_hosts_monitor.py`, ampliar la consulta SQL de
  `select name, status` a `select name, status, updated`; `_parse_systems_output()`
  devuelve también `updated` por sistema; `build_payload()` añade la clave
  `hub_systems` con **todos** los sistemas encontrados en la consulta (no solo los
  2 hosts canónicos de `hosts`) — mismo valor de `updated` tal cual lo reporta
  Beszel, sin traducir (`data-model.md`, `contracts/ficheros.md` garantías 4-5). Si
  la consulta falla o faltan los 2 hosts canónicos, el payload entero sigue siendo
  `None` (garantía "todo o nada" de feature 002, sin cambios).
- [X] T006 [US2] Ampliar el modo `--selftest` de `scripts/beszel_hosts_monitor.py`
  con casos para `hub_systems`: parseo de filas con `updated`, y que
  `build_payload()` incluya todos los sistemas de la consulta (no solo los 2
  canónicos) dentro de `hub_systems`. Depende de T005 (mismo fichero).
- [X] T007 [P] [US2] En `docker/homelab-dashboard/scripts/app.py`, implementar
  `get_beszel_hub_status()`: lee `hub_systems` de `beszel_hosts.json` y decide
  `sano` comparando la antigüedad de cada `updated` contra `BESZEL_HOSTS_MAX_AGE_S`
  (900 s, ya definida por feature 002) en el momento de la lectura — `sano=false`
  únicamente si **todos** los sistemas superan el umbral a la vez (FR-004,
  `data-model.md`). Si `hub_systems` está vacío o ausente (fichero inexistente, o
  presente pero sin esa clave), `sano` DEBE ser `false` — cero sistemas no es
  "cero sistemas viejos", es ausencia de dato (Principio II; ver Notes). Fichero
  distinto de T005/T006, sin dependencia de código (solo comparte el contrato de
  `beszel_hosts.json`, ya fijado en `data-model.md`).
- [X] T008 [US2] En `collect()` de `docker/homelab-dashboard/scripts/app.py`, sumar
  `beszel_hub` usando `get_beszel_hub_status()`. Depende de T007 (mismo fichero).
- [X] T009 [US2] En el render de la tabla "Estado de los monitores" de
  `docker/homelab-dashboard/scripts/app.py`, añadir una fila "Beszel (hub)" a mano
  (`monitorsRows += monitorRow(...)`), mismo patrón que ya usan las filas
  "heartbeat.py" y "Backup diario" — no una entrada de `MONITOR_JOBS` (`research.md`
  §4: la pregunta es de contenido, no de edad de un latido genérico). Depende de
  T008.
- [X] T010 [P] [US2] En `src/inventory/sources.py`, dentro de
  `monitoring_infra_components()`, calcular `meta={"hub_sano": ...}` para
  "Beszel (hub)" (función nueva `_beszel_hub_sano()`: lee `beszel_hosts.json`
  desde la ruta privada del homelab, aplica "al menos un sistema con dato
  fresco, umbral 900 s" — sin datos o fichero ilegible ⇒ `False`, nunca lanza).
  **Desviación consciente del plan**: no `_homelab_bridge.py` como decía
  `plan.md`, sino `sources.py` — mismo patrón que ya usa "Backup diario"
  (`heartbeat_existe` en `meta`, interpretado después en `evaluate.py`), más
  consistente que introducir un segundo sitio para el mismo tipo de dato.
  Fichero distinto de T005-T009, sin dependencia de código.
- [X] T011 [US2] En `src/inventory/evaluate.py`, dentro de `evaluate_component()`,
  categoría `infra_monitorizacion`: sustituir el hardcode
  `llega = "no" if c.nombre_actual == "Beszel (hub)" else "si"` y la entrada
  `"Beszel (hub)": None` de `_INFRA_MONITORIZACION_VIGILANCIA` por una rama que
  lea `raw.meta.get("hub_sano")` (calculado en T010). Depende de T010.
- [X] T012 [US2] Validar manualmente User Story 2 siguiendo `quickstart.md` §2-4:
  comparar la consulta directa a Beszel con lo que muestra el dashboard (datos
  reales, sano); confirmar por inspección de código + dato sintético que un solo
  sistema viejo no cambia `sano` (Clarifications, escenario 3); parar el
  LaunchAgent `amsterdam9.beszel.hosts-reader` más de 15 min y confirmar que los 3
  sistemas envejecen a la vez y `sano` pasa a `false` (escenario 2, SC-002).
  Depende de T005-T011.

**Checkpoint**: User Stories 1 y 2 funcionan, cada una verificable de forma
independiente.

---

## Phase 5: Verificación cruzada (cierre de las brechas)

**Purpose**: Confirmar las garantías que cruzan ambas historias — resiliencia
general del dashboard y el cierre real de las 2 brechas que motivaron el feature.

- [X] T013 Validar `quickstart.md` §5 (SC-004): renombrar temporalmente
  `beszel_hosts.json`, recargar el dashboard, y comprobar que el resto de paneles
  siguen funcionando con normalidad — el mecanismo de vigilancia de Beszel se
  muestra como no-sano (sin dato que leer), sin que la página falle. Restaurar el
  fichero. Depende de T009, T012.
- [X] T014 Validar `quickstart.md` §6 (SC-003): relanzar
  `PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard`
  desde este repo y comprobar que ninguna brecha de categoría `infra_monitorizacion`
  para "Beszel (hub)", ni de `integracion` para "Recordatorios de Nextcloud
  (Tareas/Calendario)", sigue apareciendo en el listado. Depende de T003, T004,
  T011, T012.

**Checkpoint**: Feature 003 completo — las 2 brechas reales que quedaban tras
feature 002 (`BRIEFING.md`) cerradas.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: sin tareas — ver rationale en cada fase.
- **User Story 1 (Phase 3)**: sin dependencia de Foundational (no hay) ni de US2.
- **User Story 2 (Phase 4)**: sin dependencia de US1 — puede empezar en paralelo.
- **Verificación cruzada (Phase 5)**: depende de que **ambas** historias estén
  terminadas (T004 y T012), y de sus tareas de `evaluate.py` (T003, T011).

### Within User Story 1

T001 → T004 (mismo job, el latido debe existir antes de poder validarlo)
T002 → T004 (idem, la fila del panel debe existir antes de validarla)
T003 → T004 (idem, para el cierre de brecha)
T001, T002, T003 son mutuamente independientes entre sí (ficheros distintos, sin
dependencia de código) — solo T004 depende de las tres.

### Within User Story 2

T005 → T006 (mismo fichero, el selftest depende de que exista el campo que prueba)
T007 independiente de T005/T006 (fichero distinto, solo comparte el contrato ya
fijado en `data-model.md`)
T007 → T008 → T009 (mismo fichero `app.py`, orden estricto: decidir el estado antes
de exponerlo en `collect()`/render)
T010 independiente de T005-T009 (fichero distinto)
T010 → T011 (mismo cambio lógico, `evaluate.py` depende de la función del puente)
T012 depende de T005-T011 (valida el conjunto)

### Parallel Opportunities

- T001, T002, T003 (User Story 1) pueden avanzar en paralelo — tres ficheros
  distintos, sin dependencia de código entre ellos.
- T007 y T010 (User Story 2) pueden avanzar en paralelo con T005/T006 — tres
  ficheros distintos, sin dependencia de código entre ellos.
- User Story 1 completa (T001-T004) puede avanzar en paralelo con User Story 2
  completa (T005-T012) — historias independientes por diseño.

---

## Parallel Example: arrancar ambas historias a la vez

```bash
# Historia 1 (un desarrollador/sesión):
Task: "T001 [US1] Latido en bautista-calendar.sh"
Task: "T002 [P] [US1] Entrada MONITOR_JOBS/MONITOR_INFO en app.py"
Task: "T003 [P] [US1] evaluate.py — categoría integracion"

# Historia 2, en paralelo (otro desarrollador/sesión):
Task: "T005 [US2] Ampliar consulta + build_payload en beszel_hosts_monitor.py"
Task: "T007 [P] [US2] get_beszel_hub_status() en app.py"
Task: "T010 [P] [US2] beszel_hub_fresh() en _homelab_bridge.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 sola)

1. T001, T002, T003 (en cualquier orden o en paralelo) → T004.
2. **Parar y validar**: es la pieza más barata de las dos (`spec.md`, "Why this
   priority" de US1) — el fallo de fondo de los recordatorios ya está arreglado,
   esto solo añade la vigilancia que faltaba.
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
- T001 es la única tarea de este feature con una restricción de seguridad
  explícita (nunca interpolar contenido de calendario sin escapar,
  `research.md` §1) — no es opcional, es parte de la definición de "hecho" de
  esa tarea.
- Ninguna tarea de este feature toca `docker_monitor.py`, `ha_monitor.py`, ni
  cambia la configuración de Beszel o de los recordatorios de Nextcloud
  (`spec.md`, FR-006/FR-007/Assumptions) — todas las tareas son de
  lectura/exposición.
- FR-003 ("...y registrar que esa comprobación se ha realizado") y FR-008
  (latido propio del mecanismo) se satisfacen reutilizando el latido
  `beszel-hosts` ya existente de feature 002, sin tarea propia — ver
  `research.md` §4.
- T007 DEBE tratar `hub_systems` vacío o ausente como `sano=false` — dato
  ausente no es sano por omisión (Principio II; hallazgo H1 de
  `/speckit-analyze`, 2026-08-09).
- A diferencia de feature 002, la corrección de `src/inventory/evaluate.py`
  (T003, T010, T011) va prevista desde `tasks.md`, no descubierta durante la
  validación de `SC-003` — ver `plan.md`, "Project Structure".
