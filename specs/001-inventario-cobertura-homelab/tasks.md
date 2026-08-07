---

description: "Task list for Inventario Sistemático de Cobertura del Homelab"

---

# Tasks: Inventario Sistemático de Cobertura del Homelab

**Input**: Design documents from `/specs/001-inventario-cobertura-homelab/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: El spec no pide TDD explícitamente. Los `tests/selftest/*` de abajo son el patrón de autocomprobación que ya usa el resto del homelab (`metrics_db.py --selftest`, `test_docker_monitor.py`) — se escriben como parte de la implementación de cada historia, no como gate previo.

**Organización**: Tareas agrupadas por historia de usuario (spec.md), en orden de prioridad P1 → P2 → P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencias pendientes)
- **[Story]**: A qué historia de usuario pertenece (US1, US2, US3)
- Las rutas de fichero son las de `src/inventory/`, `tests/selftest/`, salvo T036 (fuera del repo — ver Nota de límite del repo en `plan.md`)

## Path Conventions

Proyecto único: `src/inventory/`, `tests/selftest/` en la raíz de este repo — ver "Project Structure" en `plan.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Estructura inicial del paquete, sin lógica todavía.

- [X] T001 Crear el esqueleto del paquete: `src/inventory/__init__.py`, `src/inventory/cli.py` (entrypoint vacío), `tests/selftest/__init__.py` — plan.md "Project Structure"
- [X] T002 [P] Añadir el puente de import hacia `/Volumes/FastData/homelab/scripts/` para reutilizar `homelab_secrets.py` (`get`/`telegram`) y `heartbeat.py` (`write`) sin duplicarlos — mismo patrón `sys.path.insert(0, ...)` que ya usa `docker_monitor.py`, documentado en `src/inventory/deliver.py`. research.md §6-§7

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lo que necesitan las tres historias antes de poder implementarse.

**⚠️ CRITICAL**: Ninguna historia de usuario empieza antes de completar esta fase.

- [X] T003 [P] Definir las dataclasses `Componente`, `Hallazgo`, `Brecha`, `Ejecucion` en `src/inventory/model.py` — data-model.md
- [X] T004 Crear el esquema SQLite (4 tablas `componentes`/`hallazgos`/`brechas`/`ejecuciones`, todas append-only) y el helper de conexión/`init_db()` en `src/inventory/store.py` — data-model.md, FR-017 (depende de T003)
- [X] T005 [P] Esqueleto de argparse con los flags de `contracts/cli.md` (`--gaps`, `--since`, `--no-telegram`, `--no-dashboard`, `--selftest`), sin lógica todavía, en `src/inventory/cli.py`
- [X] T006 [P] Runner de autocomprobación (recolección de fallos, formato `OK`/`FALLO`, mismo patrón que `test_docker_monitor.py`) en `tests/selftest/__init__.py`

**Checkpoint**: Fundación lista — las historias de usuario pueden empezar.

---

## Phase 3: User Story 1 - Ver la cobertura real de todo el homelab (Priority: P1) 🎯 MVP

**Goal**: Generar, en una ejecución, la lista completa de componentes del homelab con las tres respuestas rellenas (FR-001 a FR-010).

**Independent Test**: `quickstart.md` paso 1 — `python3 -m inventory.cli --no-telegram --no-dashboard` produce una lista sin ninguna fila en blanco.

### Implementation for User Story 1

- [X] T007 [P] [US1] Adaptador de contenedores Docker en `src/inventory/sources.py::docker_components()` — FR-001, `docker ps -a`/`docker inspect`
- [X] T008 [P] [US1] Adaptador de relays hacia la LAN (`socat_relays.json`) en `src/inventory/sources.py::relay_components()` — FR-002
- [X] T009 [P] [US1] Adaptador de recordatorios de Nextcloud en `src/inventory/sources.py::nextcloud_reminder_components()` — FR-002
- [X] T010 [P] [US1] Adaptador de backups (latido de `backup_diario_nvme.sh`) en `src/inventory/sources.py::backup_components()` — FR-002
- [X] T011 [P] [US1] Adaptador de LaunchAgents/crons (`launchctl list`, `cron/jobs.json` de Hermes) en `src/inventory/sources.py::launchagent_components()` — FR-002
- [X] T012 [P] [US1] Adaptador de entidades de Home Assistant, cualquier dominio, leyendo `unique_id` de `.storage/core.entity_registry` en `src/inventory/sources.py::ha_entity_components()` — FR-003, research.md §3
- [X] T013 [P] [US1] Adaptador de la propia infraestructura de monitorización (Beszel y qué vigila) en `src/inventory/sources.py::monitoring_infra_components()` — FR-004
- [X] T014 [P] [US1] Adaptador de hosts externos (host de Uptime Kuma, host de AdGuard Home) en `src/inventory/sources.py::external_host_components()` — FR-005
- [X] T015 [P] [US1] Adaptador de Hermes/Bautista y del canal de Telegram como componentes propios y separados en `src/inventory/sources.py::hermes_and_telegram_components()` — FR-006
- [X] T016 [US1] Evaluar las tres preguntas por componente, incluyendo el valor "sin evidencia" en `src/inventory/evaluate.py::evaluate_component()` — FR-007 a FR-010 (depende de T007-T015)
- [X] T017 [US1] Calcular caducidad a 90 días de una declaración de estado esperado en `src/inventory/evaluate.py::is_declaration_stale()` — FR-007, Clarification 3 (depende de T016)
- [X] T018 [US1] Marcar componentes intencionadamente no vigilados (`frigate`, entidad muda de la cerradura) en `src/inventory/evaluate.py::is_intentional()` — FR-012 (depende de T016)
- [X] T019 [US1] Persistir la ejecución completa (componentes + hallazgos) en SQLite en `src/inventory/store.py::save_run()` — FR-017 (depende de T004, T016-T018)
- [X] T020 [US1] Entrega por Telegram del resumen/listado completo en `src/inventory/deliver.py::send_telegram()` — FR-018, `contracts/entrega.md`, reutilizando `homelab_secrets.telegram()` (depende de T002, T019)
- [X] T021 [P] [US1] Escribir `inventario.json` en `docker/homelab-orchestrator/data/` en `src/inventory/deliver.py::write_dashboard_json()` — FR-018, `contracts/entrega.md` (depende de T019)
- [X] T022 [US1] Registrar el latido tras una ejecución exitosa (persistencia y entrega OK) en `src/inventory/deliver.py::record_heartbeat()` — research.md §7, mitigación del riesgo de Telegram (depende de T002, T019, T020, T021)
- [X] T023 [US1] Conectar la ejecución por defecto de la CLI (todo lo anterior en orden) en `src/inventory/cli.py` — `contracts/cli.md` (depende de T005, T019-T022)
- [X] T024 [P] [US1] Autocomprobación de `evaluate.py` (caducidad, intencionados, y que `evaluate_component()` nunca devuelve un hallazgo con alguna de las tres respuestas vacía — FR-010) en `tests/selftest/test_evaluate.py` (depende de T016, T017, T018)

**Checkpoint**: User Story 1 completa y comprobable de forma independiente (`quickstart.md` pasos 1 y 3).

---

## Phase 4: User Story 2 - Priorizar qué brecha atacar primero (Priority: P2)

**Goal**: A partir del inventario completo, un listado filtrado de solo las brechas, con contexto suficiente (FR-011, FR-012).

**Independent Test**: `quickstart.md` paso 2 — `--gaps` produce una lista más corta con componente, pregunta que falla y contexto.

### Implementation for User Story 2

- [X] T025 [US2] Clasificar cada brecha por tipo (`sin_declaracion`, `declaracion_caducada`, `sin_vigilancia`, `no_llega_a_dashboard`, `riesgo_concentrado_telegram`) en `src/inventory/evaluate.py::classify_gap()` — FR-011, data-model.md tabla `brechas` (depende de T016-T018)
- [X] T026 [US2] Generar el contexto explicativo por brecha (componente, pregunta que falla, por qué importa) en `src/inventory/evaluate.py::gap_context()` — FR-011, SC-003 (depende de T025)
- [X] T027 [US2] Destacar el riesgo concentrado de Telegram aparte, al principio de la entrega, no mezclado en la lista en `src/inventory/deliver.py::send_telegram()` — Edge Case de FR-006, `contracts/entrega.md` (depende de T020, T025)
- [X] T028 [US2] Conectar el flag `--gaps` en la CLI en `src/inventory/cli.py` — `contracts/cli.md` (depende de T023, T026)
- [X] T029 [P] [US2] Autocomprobación de la clasificación de brechas en `tests/selftest/test_evaluate.py` (depende de T025)

**Checkpoint**: User Story 1 y 2 funcionan juntas, cada una comprobable por separado (`quickstart.md` paso 2).

---

## Phase 5: User Story 3 - Repetir el inventario cuando el homelab cambia (Priority: P3)

**Goal**: Ejecuciones repetibles y a demanda, con reconocimiento de identidad entre ejecuciones y diff de brechas nuevas vs conocidas (FR-013 a FR-015).

**Independent Test**: `quickstart.md` pasos 4-5 — repetir sin cambios sigue siendo útil; añadir un componente y repetir lo detecta sin intervención manual.

### Implementation for User Story 3

- [X] T030 [P] [US3] Emparejar un componente entre ejecuciones por su identificador estable (nombre de contenedor/servicio para Docker, `unique_id` para HA; baja+alta si la fuente no ofrece ninguno) en `src/inventory/identity.py::match_component()` — FR-015, Clarification 1, research.md §3 (depende de T003)
- [X] T031 [US3] Comparar dos ejecuciones y distinguir brechas nuevas de conocidas, y componentes de alta/baja en `src/inventory/diff.py::compare_runs()` — FR-013, FR-015 (depende de T030, T019)
- [X] T032 [US3] Conectar el flag `--since RUN_ID` en la CLI en `src/inventory/cli.py` — `contracts/cli.md` (depende de T023, T031)
- [X] T033 [US3] Garantizar que una ejecución sin cambios sigue devolviendo el resultado completo, no solo un diff vacío en `src/inventory/cli.py` — FR-013, User Story 3 escenario 3 (depende de T032)
- [X] T034 [P] [US3] Autocomprobación del emparejamiento por identidad estable en `tests/selftest/test_identity.py` (depende de T030)
- [X] T035 [P] [US3] Autocomprobación del diff (nuevas vs conocidas, retención sin purga) en `tests/selftest/test_diff.py` (depende de T031)

**Checkpoint**: Las tres historias de usuario funcionan, cada una comprobable de forma independiente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Lo que toca a más de una historia, incluida la única pieza que vive fuera de este repositorio.

- [X] T036 [P] Extender `docker/homelab-dashboard/scripts/app.py` —**fuera de este repositorio**, aplicar como parche sobre la máquina del homelab, no como fichero de `src/`— con `get_inventory()` (lee `inventario.json`, mismo patrón que `get_socat_relays()`) y una sección nueva en el HTML/JS embebido — `contracts/entrega.md` (depende de T021). *Fichero editado y compila OK (2026-08-08); backup en `app.py.bak.20260808_002339`. **No desplegado**: falta `docker compose build && up -d dashboard` en `docker/homelab-dashboard/` — decisión explícita de Miquel de aplicar sin reiniciar el contenedor todavía.*
- [X] T037 Orquestar `--selftest` completo en `src/inventory/cli.py`, ejecutando T024 + T029 + T034 + T035 + T040 contra una BD temporal, sin tocar Docker/HA/Telegram reales — mismo patrón `metrics_db.py --selftest` (depende de T006, T024, T029, T034, T035, T040)
- [X] T038 Ejecutar la validación de `quickstart.md` de extremo a extremo, pasos 1 a 7, y anotar el resultado
- [X] T039 [US2] Curar a mano el mapeo componente → hallazgo conocido de `BARRIDO-2026-08-01.md` y `BARRIDO-2026-08-07.md` (fichero de referencia, p. ej. `src/inventory/known_findings.py`) y usarlo en `evaluate.py::gap_context()` para rellenar `brechas.conocida_por_barrido_previo` — spec.md User Story 2 escenario 2, data-model.md (depende de T026). *Pertenece lógicamente a la Fase 4 (US2) — numerada al final de `tasks.md` para no renumerar todo el fichero; añadida tras `/speckit-analyze` (hallazgo G1).*
- [X] T040 [P] Añadir una lista blanca de subcomandos de solo lectura (`docker ps`, `docker inspect`, `launchctl list`, ...) y una comprobación en `tests/selftest/test_no_mutation.py` que falle si algún adaptador de `sources.py` invoca un subcomando fuera de esa lista — FR-016 (depende de T007-T015). *Salvaguarda añadida tras `/speckit-analyze` (hallazgo G2).*

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sin dependencias — empieza de inmediato.
- **Foundational (Fase 2)**: depende de Setup — bloquea las tres historias de usuario.
- **User Story 1 (Fase 3)**: depende de Foundational. Sin dependencias de US2/US3.
- **User Story 2 (Fase 4)**: depende de Foundational y de que `evaluate.py`/`deliver.py`/`cli.py` de US1 existan (T016-T018, T020, T023) — reutiliza esos módulos, no los duplica.
- **User Story 3 (Fase 5)**: depende de Foundational y de `store.py::save_run()` (T019) y `cli.py` (T023) de US1 — necesita al menos una ejecución persistida para poder comparar.
- **Polish (Fase 6)**: depende de que las historias que se vayan a entregar estén completas. T039 depende de T026 (US2); T040 depende de T007-T015 (US1) aunque esté numerada al final.

### Parallel Opportunities

- Los nueve adaptadores de `sources.py` (T007-T015) son independientes entre sí — mismo fichero, funciones distintas, sin dependencias cruzadas: paralelizables.
- T003, T005, T006 (Foundational) son paralelizables entre sí.
- T021 (JSON del dashboard) es paralelizable con T020 (Telegram) — ambas dependen solo de T019.
- Los cuatro `tests/selftest/*` (T024, T029, T034, T035) son paralelizables entre sí una vez completada la lógica que comprueban.
- US2 y US3 pueden desarrollarse en paralelo entre sí una vez completada US1 (T007-T023), si hay más de una persona — ambas dependen de US1, no la una de la otra.

---

## Parallel Example: User Story 1

```bash
# Lanzar juntos los nueve adaptadores de fuente:
Task: "Adaptador de contenedores Docker en src/inventory/sources.py::docker_components()"
Task: "Adaptador de relays en src/inventory/sources.py::relay_components()"
Task: "Adaptador de recordatorios de Nextcloud en src/inventory/sources.py::nextcloud_reminder_components()"
Task: "Adaptador de backups en src/inventory/sources.py::backup_components()"
Task: "Adaptador de LaunchAgents/crons en src/inventory/sources.py::launchagent_components()"
Task: "Adaptador de entidades de Home Assistant en src/inventory/sources.py::ha_entity_components()"
Task: "Adaptador de infraestructura de monitorización en src/inventory/sources.py::monitoring_infra_components()"
Task: "Adaptador de hosts externos en src/inventory/sources.py::external_host_components()"
Task: "Adaptador de Hermes/Bautista y Telegram en src/inventory/sources.py::hermes_and_telegram_components()"
```

---

## Implementation Strategy

### MVP primero (User Story 1 sola)

1. Fase 1: Setup
2. Fase 2: Foundational (bloqueante)
3. Fase 3: User Story 1
4. **Parar y validar**: `quickstart.md` pasos 1 y 3 — el inventario completo existe y cubre ≥11 brechas frente a la línea base
5. Es ya un entregable útil por sí solo: la primera vez que existe la lista completa de cobertura del homelab

### Entrega incremental

1. Setup + Foundational → base lista
2. + User Story 1 → validar con `quickstart.md` → MVP
3. + User Story 2 → validar (`quickstart.md` paso 2) → listado de brechas accionable
4. + User Story 3 → validar (`quickstart.md` pasos 4-5) → repetible y comparable en el tiempo
5. Polish (dashboard externo + selftest orquestado + validación completa)

---

## Notes

- [P] = ficheros/funciones distintos, sin dependencias pendientes.
- [Story] traza cada tarea a su historia de usuario, para justificar por qué existe.
- T036 es la única tarea que no vive en `src/` de este repositorio — ver "Nota de límite del repo" en `plan.md`.
- Ninguna tarea de este feature modifica, reinicia ni corrige nada del homelab (FR-016) — todo lo de arriba es lectura y persistencia propia; T040 lo comprueba explícitamente, no es solo una afirmación.
- T039 y T040 se añadieron después de `/speckit-analyze` (2026-08-07) — ver hallazgos G1 y G2 del informe.
- Commitear tras cada tarea o grupo lógico; parar en cada checkpoint para validar la historia de forma independiente antes de seguir.
