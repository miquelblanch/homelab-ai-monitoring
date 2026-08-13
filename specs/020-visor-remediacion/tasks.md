# Tasks: Visor de Remediación en el Dashboard

**Input**: Design documents from `/specs/020-visor-remediacion/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/snapshot-json.md](./contracts/snapshot-json.md), [quickstart.md](./quickstart.md)

**Organization**: tres historias de usuario (spec.md).

## Phase 1: Foundational

- [X] T001 Implementar `REMEDIACION_SNAPSHOT_PATH` (configurable) y
  `escribir_snapshot(conn)` en `src/remediacion/acciones.py` —
  recorre `LOGS_VIGILADOS`, arma el JSON de data-model.md con
  `get_modo(conn, "rotar_log")` y el tamaño real de cada log (0 si no
  existe), nunca lanza (data-model.md, contrato garantía 1)
- [X] T002 [P] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — forma correcta del
  JSON, log ausente ⇒ `tamano_bytes: 0`, ruta de escritura inválida no
  lanza

---

## Phase 2: User Story 1 - Ver el estado en el dashboard (Priority: P1) 🎯 MVP

**Goal**: los 17 logs vigilados, con tamaño y umbral reales, visibles
en el dashboard sin usar el CLI (FR-001/FR-004/FR-007).

- [X] T003 [US1] Conectar `escribir_snapshot()` al final de
  `_run_comprobar()` en `src/remediacion/cli.py` — depende de T001
- [X] T004 [US1] Copia de seguridad de
  `homelab-dashboard/scripts/app.py` antes de editar (fuera de este
  repo, sin control de versiones — mismo criterio que 018)
- [X] T005 [US1] Implementar `get_remediacion_estado()` en `app.py` —
  lee `remediacion_estado.json` con `try/except` a prueba de fallos,
  `None` si no existe o falla (research.md §4, FR-007) — depende de T004
- [X] T006 [US1] Añadir `"remediacion": get_remediacion_estado()` en
  `collect()` (`app.py`) — depende de T005
- [X] T007 [US1] Añadir la sección nueva (HTML/JS) dentro del panel
  `sistema` — lista de 17 logs con nombre/tamaño/umbral, marca visual
  si `supera_umbral`; nada si `remediacion` es `null` — depende de T006
- [X] T008 [US1] Validar manualmente los Escenarios 1, 2 y 4 de
  [quickstart.md](./quickstart.md) (depende de T003, T007)

---

## Phase 3: User Story 2 - Snapshot fresco sin intervención manual (Priority: P1)

**Goal**: el snapshot se actualiza solo cada 15 min (FR-002/FR-003).

- [X] T009 [US2] Crear `~/Library/LaunchAgents/amsterdam9.remediacion.comprobar.plist`
  (fuera de este repo) — `StartInterval=900`, ejecuta
  `PYTHONPATH=.../src python3 -m remediacion.cli comprobar` — depende
  de T003
- [X] T010 [US2] Mostrar `generado_en` en la sección nueva del
  dashboard (`app.py`, JS) — depende de T007
- [X] T011 [US2] Cargar el LaunchAgent (`launchctl load`) y validar
  manualmente el Escenario 3 de [quickstart.md](./quickstart.md) —
  depende de T009

---

## Phase 4: User Story 3 - Modo visible, sin control de acción (Priority: P2)

**Goal**: el modo de `rotar_log` visible, sin ningún botón que actúe
(FR-005/FR-006).

- [X] T012 [US3] Mostrar `modo_rotar_log` en la sección nueva
  (`app.py`, JS) — depende de T007
- [X] T013 [US3] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — sin ningún control interactivo
  en el HTML/JS de la sección (depende de T012)

---

## Phase 5: Polish

- [X] T014 [P] Reconstruir y relanzar el contenedor
  `homelab-dashboard` (`docker compose up -d --build`) y verificar
  salud (`docker ps` + `curl /api/data`) — depende de T007, T010, T012
- [X] T015 [P] Ejecutar `--selftest` completo, confirmar que sigue en
  verde con `escribir_snapshot()` añadido

---

## Dependencies

- Foundational (T001-T002) bloquea todo
- US1 (T003-T008) es el MVP real
- US2 (T009-T011) depende de que `comprobar` ya escriba el snapshot (T003)
- US3 (T012-T013) depende de que la sección ya exista (T007)
- Polish (T014-T015) depende de que las 3 historias estén completas
