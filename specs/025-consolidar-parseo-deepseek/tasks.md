# Tasks: Parseo de DeepSeek Compartido y Autocomprobación Sincera

**Input**: Design documents from `/specs/025-consolidar-parseo-deepseek/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Ningún test se reescribe (research.md §2, verificado por
grep) — solo tareas de verificación.

**Organización**: US1 (parseo compartido) y US2 (texto de `--selftest`)
son completamente independientes — ficheros distintos, sin relación —
pueden hacerse en cualquier orden.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Proyecto único: `src/` en la raíz del repo.

---

## Phase 1: Setup

- [X] T001 [P] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest`, `-m remediacion.cli --selftest`; guardar en `specs/025-consolidar-parseo-deepseek/baseline-selftest.txt` — línea base para T004 (SC-002, quickstart.md paso 1)

---

## Phase 2: User Story 1 - Corregir el respaldo de una respuesta de DeepSeek en un solo lugar (Priority: P1) 🎯 MVP

**Goal**: `_extraer_contenido_y_tokens()` única, usada por los dos consumidores — FR-001, FR-002, FR-003.

**Independent Test**: cambiar el respaldo en `diagnostico/deepseek.py` y comprobar que ambos consumidores lo ven.

### Implementation for User Story 1

- [X] T002 [US1] Añadir `_extraer_contenido_y_tokens(respuesta: dict) -> tuple[dict, int, int]` a `src/diagnostico/deepseek.py` (research.md §3 — extrae `content`/`reasoning_content` + tokens, lanza si la forma es inesperada); actualizar `parsear_respuesta()` para que la llame y mantenga su propio `try/except` y su validación de `conclusion_tipo`/`hipotesis` sin cambios
- [X] T003 [US1] Actualizar `src/remediacion/deepseek_contenedores.py::parsear_respuesta_remediacion()` para importar y llamar a `diagnostico.deepseek._extraer_contenido_y_tokens()`, manteniendo su propio `try/except` y `_validar_decision()`/`_accion_valida()` sin cambios; quitar el bloque de extracción duplicado
- [X] T004 [US1] Ejecutar `PYTHONPATH=src python3 -m diagnostico.cli --selftest`, `-m inventory.cli --selftest`, `-m remediacion.cli --selftest`; comparar contra `baseline-selftest.txt` (T001) — deben ser idénticos, sin haber tocado ningún fichero de test (SC-002)
- [X] T005 [US1] Verificar el respaldo `reasoning_content` en la función compartida (quickstart.md paso 4): una respuesta con `content` vacío y `reasoning_content` poblado debe seguir recuperándose igual que antes

**Checkpoint**: la extracción compartida funciona, comportamiento idéntico en los dos consumidores.

---

## Phase 3: User Story 2 - Confiar en lo que dice la autocomprobación de cada CLI (Priority: P2)

**Goal**: El texto de `--selftest` en las tres CLIs describe su alcance real — FR-004, FR-005, FR-006.

**Independent Test**: leer el `--help` y el docstring de `_run_selftest()` de las tres CLIs y confirmar que ninguno sugiere un alcance acotado.

### Implementation for User Story 2

- [X] T006 [P] [US2] Corregir en `src/diagnostico/cli.py`: texto de `--help` de `--selftest` y docstring de `_run_selftest()` (quitar la lista "test_evidencia/test_deepseek/test_gasto/test_store/test_reproducibilidad/test_baseline_beszel" — research.md §4)
- [X] T007 [P] [US2] Corregir en `src/inventory/cli.py`: texto de `--help` de `--selftest` y docstring de `_run_selftest()` (quitar la lista "test_evaluate/test_identity/test_diff/test_no_mutation")
- [X] T008 [P] [US2] Corregir en `src/remediacion/cli.py`: texto de `--help` de `--selftest`; añadir docstring a `_run_selftest()` (hoy no tiene ninguno)
- [X] T009 [US2] Verificar el texto corregido (quickstart.md paso 5): `--help` de las tres CLIs menciona la suite completa compartida, ninguna sugiere alcance acotado a sí misma (SC-003)

**Checkpoint**: el texto de las tres CLIs dice la verdad sobre su alcance.

---

## Phase 4: Polish

- [X] T010 [P] Actualizar `REFACTOR-deepseek-selftest.md` (raíz del repo) marcándolo como resuelto, con enlace a `specs/025-consolidar-parseo-deepseek/`
- [X] T011 Ejecutar `quickstart.md` de principio a fin como verificación final
- [X] T012 Prueba estructural de SC-001: cambiar temporalmente el orden de prioridad `content`/`reasoning_content` en `_extraer_contenido_y_tokens()`, confirmar con `git diff --stat` que solo `src/diagnostico/deepseek.py` cambia y que `remediacion/deepseek_contenedores.py` ve el efecto (vía T005), luego revertir

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: sin dependencias
- **US1 (Phase 2, P1, MVP)**: depende de Setup
- **US2 (Phase 3, P2)**: depende de Setup — independiente de US1, ficheros distintos
- **Polish (Phase 4)**: depende de US1 y US2 completas

### Parallel Opportunities

- T006, T007, T008 (US2) en paralelo — tres ficheros distintos
- US1 y US2 podrían hacerse en paralelo entre sí (no comparten ningún fichero) si hubiera más de una persona/agente

## Implementation Strategy

### MVP First

1. Setup (T001)
2. US1 (T002-T005) — resuelve el problema de mayor impacto (el respaldo duplicado que ya causó un problema real)
3. **PARAR Y VALIDAR**: T004 debe dar el mismo recuento que la línea base

### Incremental Delivery

1. Setup → línea base capturada
2. US1 → extracción compartida (MVP)
3. US2 → texto de `--selftest` corregido
4. Polish → material de auditoría actualizado

## Notes

- Ningún test se reescribe — research.md §2 lo verificó, no lo asumió
- `_extraer_contenido_y_tokens()` LANZA — el contrato "nunca lanza" sigue siendo responsabilidad de cada llamador, no de la función compartida (research.md §3)
