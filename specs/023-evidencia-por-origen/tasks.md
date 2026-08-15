# Tasks: Evidencia de Diagnóstico Organizada por Origen

**Input**: Design documents from `/specs/023-evidencia-por-origen/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/fachada-evidencia.md, quickstart.md

**Tests**: No se piden tests nuevos (spec.md no lo pide) — pero FR-005/FR-007
exigen que los tests **existentes** se reorganicen y sigan verificando lo
mismo. Por eso el movimiento de cada test va en la misma tarea que el
movimiento del código de su origen: son la misma unidad de trabajo, no una
fase de TDD separada.

**Organización**: agrupadas por historia de usuario de `spec.md`. Aviso
honesto sobre la independencia entre historias, distinto del caso general:
US2 y US3 no pueden empezar hasta que US1 termine — no hay forma de "añadir
un origen nuevo a la estructura" o "confirmar que los consumidores no se
rompieron" antes de que la estructura y la fachada existan. La única
independencia real es que, una vez hecho US1, US2 y US3 no dependen entre sí.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (fichero distinto, sin dependencias)
- **[Story]**: Historia de usuario a la que pertenece (US1, US2, US3)
- Rutas de fichero exactas en cada descripción

## Path Conventions

Proyecto único: `src/` y `tests/` en la raíz del repo (ver `plan.md` §Project
Structure).

---

## Phase 1: Setup

**Purpose**: Capturar la línea base antes de tocar nada y preparar el
esqueleto del paquete.

- [X] T001 [P] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest` y `-m remediacion.cli --selftest`; guardar la salida completa (recuento de aserciones y fallos de cada uno) en `specs/023-evidencia-por-origen/baseline-selftest.txt` — es la línea base contra la que se comparan T026 y T029 (SC-002, quickstart.md paso 1)
- [X] T002 [P] Crear `src/diagnostico/evidencia/` con `__init__.py` y `_compartido.py` vacíos (placeholder, se llenan en Phase 2 y Phase 3)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extraer el mecanismo compartido real (`research.md` §2,
`data-model.md` §Mecanismo compartido) — todo origen que se mueva en Phase 3
importará de aquí, así que debe existir primero.

**⚠️ CRITICAL**: ninguna tarea de Phase 3 puede empezar antes de que esta fase esté completa y verificada.

- [X] T003 Mover a `src/diagnostico/evidencia/_compartido.py`: `homelab_db_path()`, `_connect_homelab_db()`, `_run_ro()`, `docker_logs_tail()`, `_docker_bin()`, `BESZEL_HUB_VOLUME` — eliminarlas de `src/diagnostico/evidencia.py` y sustituir sus usos ahí por `from .evidencia import _compartido` (o equivalente relativo, ya que en este punto `evidencia.py` sigue siendo un único fichero con los diez orígenes todavía dentro)
- [X] T004 Checkpoint: ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest` y confirmar el mismo recuento de aserciones que `baseline-selftest.txt` (T001) — si difiere, no continuar a Phase 3

**Checkpoint**: mecanismo compartido extraído y verificado — Phase 3 puede empezar.

---

## Phase 3: User Story 1 - Revisar el comportamiento de un solo origen (Priority: P1) 🎯 MVP

**Goal**: Partir los diez orígenes y su test en piezas que se puedan leer,
tocar y verificar de forma aislada — FR-001, FR-003, FR-007.

**Independent Test**: elegir cualquiera de los diez ficheros de origen (por
ejemplo `disco.py`) y confirmar que se entiende y se verifica por completo
sin abrir `ha.py`, `backup.py` ni ningún otro (spec.md, Acceptance Scenario
US1.2).

### Implementation for User Story 1

Cada tarea mueve el código de un origen (`data-model.md`, tabla "Origen de
evidencia") y su bloque de test correspondiente en el mismo paso, porque son
la misma unidad de valor: un origen que se movió pero cuyo test se quedó
atrás no es un origen verificable de forma aislada (falla el "Independent
Test" de esta historia).

- [X] T005 [US1] Mover el origen contenedor a `src/diagnostico/evidencia/contenedor.py` (`congelar_historico`, `congelar_vivo`, `restart_history_row`, `container_metrics_window`, `container_metrics_hourly_window`, `container_metrics_recientes`, `disk_metrics_near`, `docker_inspect`, `_parse_docker_inspect`, `es_critico` — data-model.md fila "Contenedor", ojo: `disk_metrics_near` es de contenedor pese al nombre, research.md §2); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T006 [US1] Mover el origen disco a `src/diagnostico/evidencia/disco.py` (`congelar_disco_vivo`, `congelar_disco_historico`, `disk_metrics_window`, `disk_metrics_recientes`, `_disco_path`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T007 [US1] Mover el origen Home Assistant a `src/diagnostico/evidencia/ha.py` (`congelar_ha_vivo`, `congelar_ha_historico`, `ha_check_by_id`, `_simplificar_historial`, `ha_history_window`, `_validar_check_ha`, `_resolver_evidencia_ha`, `CHECKS_HA_EXCLUIDOS_CERRADURA`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T008 [US1] Mover el origen backup a `src/diagnostico/evidencia/backup.py` (`congelar_backup_vivo`, `congelar_backup_historico`, `_listar_logs_backup`, `_momento_de_log_backup`, `_log_backup_mas_reciente`, `_log_backup_cercano`, `_parsear_log_backup`, `_snapshot_backup_vacio`, `_congelar_backup`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T009 [US1] Mover el origen relay a `src/diagnostico/evidencia/relay.py` (`congelar_relay_vivo`, `congelar_relay_historico`, `listar_nombres_relay`, `nombres_relay_evidenciados`, `_relay_actual`, `_agregado_relays_ventana`, `_snapshot_relay_vacio`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T010 [US1] Mover el origen inventario a `src/diagnostico/evidencia/inventario.py` (`congelar_inventario_vivo`, `congelar_inventario_historico`, `_hallazgo_de_componente`, `_brecha_de_componente`, `_validar_tipo_brecha_inventario`, `_comparacion_dict`, `_snapshot_inventario_vacio`, `_armar_episodio_inventario`, más los imports `inv_diff`/`inv_store`/`TIPOS_BRECHA` de `inventory` — solo se usan aquí); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T011 [US1] Mover el origen host externo a `src/diagnostico/evidencia/host_externo.py` (`congelar_host_externo_vivo`, `congelar_host_externo_historico`, `_a_utc_madrid`, `_host_externo_actual`, `_consultar_beszel_hub`, `_resumen_system_stats`, `_snapshot_host_externo_vacio`, `_QUERY_SYSTEM_STATS`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T012 [US1] Mover el origen hub Beszel a `src/diagnostico/evidencia/hub_beszel.py` (`congelar_hub_beszel_vivo`, `congelar_hub_beszel_historico`, `_hub_beszel_actual`, `_consultar_beszel_hub_todos_sistemas`, `_resumen_por_sistema`, `_snapshot_hub_beszel_vacio`, `_QUERY_SYSTEM_STATS_TODOS`); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T013 [US1] Mover el origen agente a `src/diagnostico/evidencia/agente.py` (`congelar_agente_vivo`, `_agente_actual`, `_snapshot_agente_vacio` — sin variante histórica, spec.md Edge Cases); eliminarlo de `src/diagnostico/evidencia.py`
- [X] T014 [US1] Mover el origen latido a `src/diagnostico/evidencia/latido.py` (`congelar_latido_vivo`, `_latido_actual`, `_snapshot_latido_vacio` — sin variante histórica); eliminarlo de `src/diagnostico/evidencia.py`, que a partir de aquí debe quedar vacío salvo el docstring de cabecera
- [X] T015 [US1] Crear la fachada `src/diagnostico/evidencia/__init__.py` reexportando exactamente los 20 nombres de `contracts/fachada-evidencia.md` §"Firmas que la fachada DEBE preservar"; eliminar el fichero ya vacío `src/diagnostico/evidencia.py`
- [X] T016 [US1] Crear `tests/selftest/test_evidencia_contenedor.py`: mover los casos de contenedor de `tests/selftest/test_evidencia.py`, importar `from diagnostico.evidencia import contenedor` y reescribir cualquier `evidencia._algo` como `contenedor._algo`
- [X] T017 [US1] Crear `tests/selftest/test_evidencia_disco.py`: mover los casos de disco; importar `from diagnostico.evidencia import disco`
- [X] T018 [US1] Crear `tests/selftest/test_evidencia_ha.py`: mover los casos de HA, incluidos los que usan `CHECKS_HA_EXCLUIDOS_CERRADURA`; importar `from diagnostico.evidencia import ha`
- [X] T019 [US1] Crear `tests/selftest/test_evidencia_backup.py`: mover los casos de backup, incluidos los de `_parsear_log_backup`; importar `from diagnostico.evidencia import backup`
- [X] T020 [US1] Crear `tests/selftest/test_evidencia_relay.py`: mover los casos de relay, incluidos `_relay_actual`, `_agregado_relays_ventana`, `listar_nombres_relay`, `nombres_relay_evidenciados`; importar `from diagnostico.evidencia import relay`
- [X] T021 [US1] Crear `tests/selftest/test_evidencia_inventario.py`: mover los casos de inventario, incluidos `_hallazgo_de_componente`, `_brecha_de_componente`, `_validar_tipo_brecha_inventario`, `_comparacion_dict`; importar `from diagnostico.evidencia import inventario`
- [X] T022 [US1] Crear `tests/selftest/test_evidencia_host_externo.py`: mover los casos de host externo; importar `from diagnostico.evidencia import host_externo` y **reescribir `patch.object(evidencia, "_consultar_beszel_hub", ...)` como `patch.object(host_externo, "_consultar_beszel_hub", ...)`** — si no, el parche deja de alcanzar la función real (research.md §3, riesgo verificado)
- [X] T023 [US1] Crear `tests/selftest/test_evidencia_hub_beszel.py`: mover los casos de hub Beszel; importar `from diagnostico.evidencia import hub_beszel` y **reescribir `patch.object(evidencia, "_consultar_beszel_hub_todos_sistemas", ...)` como `patch.object(hub_beszel, "_consultar_beszel_hub_todos_sistemas", ...)`** — mismo riesgo que T022
- [X] T024 [US1] Crear `tests/selftest/test_evidencia_agente.py`: mover los casos de agente; importar `from diagnostico.evidencia import agente`
- [X] T025 [US1] Crear `tests/selftest/test_evidencia_latido.py`: mover los casos de latido; importar `from diagnostico.evidencia import latido`
- [X] T026 [US1] Eliminar `tests/selftest/test_evidencia.py` (ya vacío tras T016-T025) y ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`; confirmar el mismo recuento de aserciones que `baseline-selftest.txt` (T001) — cero perdidas, cero duplicadas (SC-002)

**Checkpoint**: los diez orígenes y sus tests viven en ficheros independientes; cualquiera se puede revisar sin abrir los otros nueve. US1 es demostrable de forma aislada.

---

## Phase 4: User Story 2 - Añadir un origen de evidencia nuevo (Priority: P2)

**Goal**: Demostrar, no solo argumentar, que la estructura de US1 cumple
SC-001 — un origen nuevo no toca a los existentes.

**Independent Test**: incorporar un origen de prueba desechable y comprobar
con `git diff --stat` que ningún módulo de origen existente cambia.

### Implementation for User Story 2

- [X] T027 [US2] Crear `src/diagnostico/evidencia/_scratch_origen_prueba.py` con una función mínima de ejemplo, añadir su export a `src/diagnostico/evidencia/__init__.py`; ejecutar `git diff --stat` y confirmar que ningún fichero `contenedor.py`...`latido.py` aparece en el diff (solo `__init__.py` y el fichero nuevo); revertir el export y eliminar el fichero de prueba (quickstart.md paso 5)

**Checkpoint**: SC-001 verificado con evidencia real, no solo por diseño.

---

## Phase 5: User Story 3 - Confirmar que no hay comportamiento observable roto (Priority: P3)

**Goal**: Cerrar la garantía de FR-002/SC-004 para los tres consumidores
reales antes de dar el refactor por terminado.

**Independent Test**: ejecutar la suite completa antes/después y comparar —
ya preparado por T001; comparar aquí es lo único que falta.

### Implementation for User Story 3

- [X] T028 [US3] Ejecutar el script de verificación de la fachada de `quickstart.md` paso 4 (los 20 nombres de `contracts/fachada-evidencia.md`) contra `src/diagnostico/evidencia/__init__.py`
- [X] T029 [US3] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest` y `-m remediacion.cli --selftest`; comparar el recuento de aserciones y fallos contra `baseline-selftest.txt` (T001) — deben ser idénticos
- [X] T030 [US3] Confirmar con `git diff --stat` que `src/diagnostico/cli.py`, `src/remediacion/acciones.py` y `src/diagnostico/deepseek.py` no aparecen en el diff de esta feature (FR-002 — los tres consumidores no cambian una línea)

**Checkpoint**: los tres consumidores reales verificados, no solo asumidos.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Dejar el repo sin rastros del fichero único que ya no existe.

- [X] T031 [P] Actualizar los comentarios que referencian "evidencia.py" como fichero único en `src/diagnostico/store.py:5` y `src/diagnostico/model.py:4` para reflejar el paquete `diagnostico/evidencia/`
- [X] T032 Actualizar `REFACTOR-evidencia.md` (raíz del repo) marcándolo como resuelto por esta feature, con un enlace a `specs/023-evidencia-por-origen/`
- [X] T033 Ejecutar `quickstart.md` de principio a fin como verificación final antes de dar la feature por completa

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — puede empezar inmediatamente
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA todo lo demás
- **US1 (Phase 3, P1, MVP)**: depende de Foundational — es el refactor en sí
- **US2 (Phase 4, P2)**: depende de que US1 haya terminado (T005-T026) — no hay estructura que probar antes
- **US3 (Phase 5, P3)**: depende de que US1 haya terminado — no hay fachada que verificar antes. Independiente de US2 (pueden ir en cualquier orden entre sí)
- **Polish (Phase 6)**: depende de US1, US2 y US3 completas

### Parallel Opportunities

- T001 y T002 (Setup) en paralelo — ficheros distintos
- T005-T014 (mover los diez orígenes) son lógicamente independientes entre sí (cada uno a su propio fichero destino) pero todas editan el mismo fichero origen `evidencia.py` para eliminar el código movido — **no marcadas [P]** por ese conflicto de fichero compartido, aunque el orden entre ellas no importa
- Mismo razonamiento para T016-T025 (mueven texto del mismo `test_evidencia.py` origen) — no marcadas [P]
- T031 (Polish) en paralelo con el resto de Phase 6 — fichero distinto de T032/T033

---

## Parallel Example: Setup

```bash
# T001 y T002 pueden lanzarse a la vez — no comparten fichero:
Task: "Capturar línea base de --selftest en specs/023-evidencia-por-origen/baseline-selftest.txt"
Task: "Crear esqueleto src/diagnostico/evidencia/{__init__.py,_compartido.py} vacíos"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Phase 1 (Setup) y Phase 2 (Foundational — bloquea todo lo demás)
2. Completar Phase 3 (US1): los diez orígenes y sus tests, en ficheros
   independientes, con la fachada funcionando
3. **PARAR Y VALIDAR**: T026 debe dar el mismo recuento de aserciones que la
   línea base — si no, no seguir a US2/US3
4. Con esto ya se cumple el problema central de `spec.md` (US1, P1)

### Incremental Delivery

1. Setup + Foundational → mecanismo compartido extraído y verificado
2. US1 → el refactor real; recuento de aserciones idéntico a la línea base (MVP)
3. US2 → prueba concreta de que un origen nuevo no toca a los existentes
4. US3 → confirmación explícita de que los tres consumidores no notan nada
5. Polish → sin rastros de comentarios ni documentos desactualizados

---

## Notes

- [P] = ficheros distintos, sin dependencias entre sí
- [Story] mapea cada tarea a su historia de usuario para trazabilidad
- Ninguna tarea de código nueva: todo es mover, nunca reescribir lógica —
  cualquier diff que no sea puramente "quitar de aquí, poner allí" es una
  señal de que algo se salió de alcance (FR-002)
- Confirmar el recuento de aserciones contra `baseline-selftest.txt` en T004,
  T026 y T029 — no basta con "sigue en verde", tiene que ser el mismo número
- Hacer commit tras cada tarea o grupo lógico (por ejemplo, tras mover un
  origen completo con su test)
