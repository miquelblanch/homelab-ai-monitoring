# Tasks: Puente Único hacia los Scripts del Homelab

**Input**: Design documents from `/specs/024-consolidar-bridge-homelab/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/fachadas-bridge.md, quickstart.md

**Tests**: research.md §2 concluye, verificado por grep (no supuesto),
que **ningún test necesita reescribirse** — todo consumidor de
producción y de test accede a cada `_homelab_bridge` por atributo de
módulo (`bridge.función()`), nunca importando el nombre suelto, así
que un `patch.object()` existente sigue interceptando la llamada real
tenga la función su cuerpo local o reexportado. Por eso este refactor,
a diferencia de 023, no tiene fase de "mover tests" — solo tareas de
verificación.

**Organización**: agrupadas por historia de usuario de `spec.md`. US2
(documentar la dependencia) es independiente de US1 en el sentido de
que no necesita que US1 termine para tener sentido por sí sola, pero
comparte fichero (`diagnostico/_homelab_bridge.py`) con una tarea de
US1 — van en orden, no en paralelo entre sí.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Proyecto único: `src/` en la raíz del repo (ver `plan.md` §Project Structure).

---

## Phase 1: Setup

- [X] T001 [P] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest` y `-m remediacion.cli --selftest`; guardar la salida en `specs/024-consolidar-bridge-homelab/baseline-selftest.txt` — línea base para T008 (SC-003, quickstart.md paso 1)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Crear los dos módulos compartidos nuevos — ninguna fachada de Phase 3 puede reexportar de algo que no existe todavía.

- [X] T002 [P] Crear `src/_homelab_bridge_common.py`: bootstrap de `HOMELAB_SCRIPTS_DIR`/`sys.path`, handles `_homelab_secrets`/`_docker_monitor`, y las funciones `get_secret()`, `telegram_credentials()`, `docker_never_restart()`, `docker_critical()` (la versión BASE, sin el hook de `REMEDIACION_TEST_FORZAR_CRITICO` — data-model.md, research.md §1/§3)
- [X] T003 [P] Crear `src/_homelab_bridge_heartbeat.py`: handle `_heartbeat` y la función `record_heartbeat()` — **nunca** en el mismo fichero que T002 (research.md §1: `remediacion` no debe arrastrar un `import heartbeat` que hoy no hace)
- [X] T004 Checkpoint: `python3 -m py_compile src/_homelab_bridge_common.py src/_homelab_bridge_heartbeat.py` sin error; `PYTHONPATH=src python3 -c "import _homelab_bridge_common, _homelab_bridge_heartbeat"` importa sin lanzar

**Checkpoint**: los dos módulos compartidos existen y se pueden importar — Phase 3 puede empezar.

---

## Phase 3: User Story 1 - Cambiar algo compartido en un solo lugar (Priority: P1) 🎯 MVP

**Goal**: Las tres fachadas reexportan lo compartido y conservan local lo exclusivo — FR-001, FR-002, FR-003, FR-004, FR-006.

**Independent Test**: cambiar el comportamiento de una pieza compartida (por ejemplo `docker_never_restart`) en `_homelab_bridge_common.py` y comprobar que los tres paquetes lo ven sin tocar más ficheros.

### Implementation for User Story 1

- [X] T005 [US1] Reescribir `src/diagnostico/_homelab_bridge.py`: reexportar `get_secret`, `docker_critical`, `docker_never_restart` de `_homelab_bridge_common`, y `record_heartbeat` de `_homelab_bridge_heartbeat`; conservar sin cambios el import local de `ha_monitor` y las funciones `ha_checks`/`ha_history`/`ha_check_status`/`ha_recorder_corrupt_files` (contracts/fachadas-bridge.md, fila "diagnostico")
- [X] T006 [US1] Reescribir `src/inventory/_homelab_bridge.py`: reexportar `get_secret`, `telegram_credentials`, `docker_critical`, `docker_never_restart` de `_homelab_bridge_common`, y `record_heartbeat` de `_homelab_bridge_heartbeat`; conservar sin cambios el import local de `ha_monitor`, `ha_monitor_checked_entities`/`ha_monitor_conditional_entities`/`ha_monitor_check_result`; `read_heartbeat()` y `available()` pasan a usar los handles `_heartbeat`/`_homelab_secrets` importados de los módulos compartidos, no uno propio (contracts/fachadas-bridge.md, fila "inventory")
- [X] T007 [US1] Reescribir `src/remediacion/_homelab_bridge.py`: reexportar `telegram_credentials` y `docker_never_restart` de `_homelab_bridge_common` tal cual; `docker_critical` pasa a ser una función LOCAL que llama a `_homelab_bridge_common.docker_critical()` como base y añade encima la lógica de `REMEDIACION_TEST_FORZAR_CRITICO` (research.md §3) — nunca una reexportación plana; conservar sin cambios `listar_contenedores`, `restart_container`, `breaker_decision`, `recent_restart_attempts`, `declarar_correccion_ia` (contracts/fachadas-bridge.md, fila "remediacion")
- [X] T008 [US1] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest`, `-m remediacion.cli --selftest`; comparar contra `baseline-selftest.txt` (T001) — deben ser idénticos, sin haber tocado ningún fichero de test (SC-003)
- [X] T009 [US1] Verificar el aislamiento del hook de prueba (SC-002, quickstart.md paso 4): con `REMEDIACION_TEST_FORZAR_CRITICO` en el entorno, confirmar que `diagnostico._homelab_bridge.docker_critical()` e `inventory._homelab_bridge.docker_critical()` no lo ven, y que `remediacion._homelab_bridge.docker_critical()` sí
- [X] T010 [US1] Verificar que `remediacion/_homelab_bridge.py` no depende de `_homelab_bridge_heartbeat.py` (research.md §1, corregido tras hallazgo real: `sys.modules` no sirve como criterio porque `docker_monitor.py` ya arrastra `heartbeat` de forma transitiva con o sin este refactor) — comprobar por inspección del código fuente que el fichero no importa `_homelab_bridge_heartbeat` ni expone `record_heartbeat`
- [X] T011 [US1] Verificar las firmas de la fachada (contracts/fachadas-bridge.md) con `inspect.signature()` para cada una de las 26 funciones listadas, antes/después

**Checkpoint**: las tres fachadas funcionan, mismo comportamiento exacto, hook de prueba aislado. US1 es demostrable de forma aislada.

---

## Phase 4: User Story 2 - Saber qué paquete depende de cuál, sin sorpresas (Priority: P2)

**Goal**: La dependencia real de `diagnostico` hacia `inventory` queda documentada — FR-005.

**Independent Test**: comparar la documentación de dependencias de cada paquete contra sus `import` reales — deben coincidir.

### Implementation for User Story 2

- [X] T012 [US2] Corregir el docstring de `src/diagnostico/_homelab_bridge.py`: quitar la afirmación de que `diagnostico` e `inventory` son "paquetes hermanos independientes... sin que ninguno dependa del otro", y anotar la dependencia real hacia `inventory` (vía `evidencia/inventario.py`, feature 013), con referencia a `specs/024-consolidar-bridge-homelab/research.md` §4
- [X] T013 [US2] Verificar SC-004: revisar el docstring de los tres `_homelab_bridge.py` y confirmar que ninguno afirma una independencia que el código ya no cumple — comparar contra los `import` reales de `diagnostico/evidencia/inventario.py` y `remediacion/acciones.py`

**Checkpoint**: la documentación de dependencias coincide con la realidad del código.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T014 [P] Actualizar `REFACTOR-homelab-bridge.md` (raíz del repo) marcándolo como resuelto por esta feature, con enlace a `specs/024-consolidar-bridge-homelab/`
- [X] T015 Ejecutar `quickstart.md` de principio a fin como verificación final
- [X] T016 Prueba estructural de SC-001: cambiar temporalmente el valor de retorno por defecto de una pieza compartida en `src/_homelab_bridge_common.py`, confirmar con `git diff --stat` que ningún otro fichero cambia y que los tres paquetes ven el cambio nuevo, luego revertir
- [X] T017 Verificar FR-006 (contrato a prueba de fallos): con `HOMELAB_SCRIPTS_DIR` apuntando a un directorio vacío o inexistente, confirmar que `get_secret`, `telegram_credentials`, `docker_never_restart`, `docker_critical` y `record_heartbeat` devuelven valores inocuos (cadena vacía, tupla de vacíos, conjunto vacío) sin lanzar excepción

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — bloquea todo lo demás
- **US1 (Phase 3, P1, MVP)**: depende de Foundational
- **US2 (Phase 4, P2)**: depende de que T005 (US1) haya terminado — comparte fichero con T012, van en orden
- **Polish (Phase 5)**: depende de US1 y US2 completas

### Parallel Opportunities

- T002 y T003 (Foundational) en paralelo — ficheros distintos, ninguno depende del otro
- T001 (Setup) es independiente y podría ir en paralelo con T002/T003, pero al ser una sola tarea de captura no aporta mucho hacerlo — se deja secuencial por simplicidad
- T014 (Polish) en paralelo con T015

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Setup + Foundational (T001-T004)
2. US1 (T005-T011) — con esto ya se resuelve el problema central: cambiar algo compartido en un solo lugar, sin arriesgar el hook de prueba
3. **PARAR Y VALIDAR**: T008 debe dar el mismo recuento que la línea base

### Incremental Delivery

1. Setup + Foundational → los dos módulos compartidos existen
2. US1 → las tres fachadas reescritas, comportamiento idéntico (MVP)
3. US2 → dependencia diagnostico→inventory documentada por primera vez
4. Polish → sin rastros de material de auditoría desactualizado

## Notes

- Ninguna tarea reescribe un test — research.md §2 lo verificó, no lo asumió
- Confirmar el recuento de aserciones contra `baseline-selftest.txt` en T008 — no basta "sigue en verde", tiene que ser el mismo número
- `docker_critical` de remediacion NUNCA es una reexportación plana — es la única función de las 26 de `contracts/fachadas-bridge.md` cuya implementación cambia de forma (de copia completa a envoltorio), aunque su firma y comportamiento observable no cambien
