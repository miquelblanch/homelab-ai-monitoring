# Tasks: Generalizar el Diagnóstico a los Latidos de Monitores

**Input**: Design documents from `/specs/017-diagnostico-latidos/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007-016) —
verificación de lógica pura contra ficheros `<job>.json` de prueba, sin
tocar DeepSeek real salvo en las tareas de validación manual explícitas
de Polish.

**Organization**: una sola historia de usuario (spec.md) — segundo
feature de la serie sin US2, porque no existe ningún modo diferido
posible (research.md §2), mismo caso que 016.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo. Sin cambios en
`src/diagnostico/store.py`, `src/diagnostico/gasto.py` ni
`src/diagnostico/_homelab_bridge.py`.

---

## Phase 1: Foundational (Blocking Prerequisites)

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el décimo y último valor
  real de `origen` (`"latido"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`/`"inventario"`/`"host_externo"`/`"hub_beszel"`/`"agente"`)
  — sin cambio de esquema ni de campos, solo el docstring
  (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_latido_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más `latido_actual`
  a `null`, mismo patrón que `_snapshot_agente_vacio()` de 016
  (data-model.md)

**Checkpoint**: el molde de snapshot está listo.

---

## Phase 2: User Story 1 - Diagnosticar en vivo el latido de un job concreto (Priority: P1) 🎯 único alcance del feature

**Goal**: Miquel puede pedir un diagnóstico en vivo del latido de
cualquiera de los 8 jobs vigilados, con el mismo rigor que los demás
orígenes (spec.md FR-001 a FR-007).

**Independent Test**: `congelar --latido-vivo JOB` + `diagnosticar`
contra un job con latido reciente y sano concluye `no_diagnosticable`
sin inventar una causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [US1] Implementar constante `MONITOR_JOBS` (lista de 8
  `(job, label, max_age_s)`, copia literal de `app.py::MONITOR_JOBS`) y
  `_latido_actual(job)` en `src/diagnostico/evidencia.py` + constante
  `MONITOR_HEARTBEATS_DIR` (configurable, por defecto
  `/Volumes/FastData/homelab/data/heartbeats`) — si `job` no está entre
  los 8, devuelve `None`; si sí, lee `<job>.json` y calcula `age_s =
  ahora - epoch`, `ok = age_s <= max_age_s` (**nunca combinado con
  `status`** — hallazgo real de research.md §3); si el fichero no
  existe, o cualquier lectura falla, devuelve `{job, label, detail:
  "sin latido", status: None, ok: False, age_s: None, max_age_s}` —
  mismo cálculo y mismo texto exacto que `app.py::get_monitor_heartbeats()`
  (research.md §3)
- [X] T004 [US1] Implementar `congelar_latido_vivo(conn, job)` en
  `src/diagnostico/evidencia.py` — arma el snapshot (T002) con
  `latido_actual=<resultado de T003>`; `componente=job`,
  `es_critico=False` siempre, `origen="latido"`, `en_vivo=True`
  (siempre — no existe modo diferido), `restart_history_id=None`
  (data-model.md) — depende de T002, T003
- [X] T005 [US1] Conectar el flag `--latido-vivo JOB` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — **sin par `--latido-historico`**, segundo origen de los
  10 con un solo flag (FR-011, research.md §2/§5; contracts/cli.md) —
  depende de T004
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o el latido de un monitor
  del propio homelab" a la lista ya existente. **Cláusula nueva**,
  `_PROMPT_CLAUSULA_LATIDO_ESTADO` (mismo patrón que
  `_PROMPT_CLAUSULA_HA_ESTADO` de 010): el campo `latido_actual.ok` es
  el veredicto ya calculado, no se recalcula a partir de `status`
  (research.md §4) — enganchada en `construir_prompt()` con `if
  snapshot.get("latido_actual") is not None` — independiente de
  T003-T005
- [X] T007 [P] [US1] Autocomprobación `tests/selftest/test_evidencia.py`
  — `_latido_actual()` contra ficheros `<job>.json` de prueba: latido
  reciente y sano (`ok=True`), latido rancio (`ok=False`), latido con
  `status="error"` pero edad fresca (`ok=True` igualmente — el hallazgo
  de research.md §3), fichero ausente (`ok=False, age_s=None`), `job`
  inexistente entre los 8 (`None`); `congelar_latido_vivo()` arma el
  snapshot correctamente en los cinco casos, con `en_vivo=True` siempre
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "latido", incluye la cláusula
  `_PROMPT_CLAUSULA_LATIDO_ESTADO` solo cuando `latido_actual` no es
  `None`; **y** (mismo hallazgo recurrente ya corregido desde el diseño
  en 013-016) `test_parsear_respuesta_latido_con_varias_hipotesis`: una
  respuesta simulada con `len(hipotesis) > 1` se acepta correctamente
  (SC-002)

**Checkpoint**: Miquel puede diagnosticar en vivo el latido de
cualquiera de los 8 jobs con el mismo rigor que los demás orígenes —
feature completo (sin US2, research.md §2).

---

## Phase 3: Polish & Cross-Cutting Concerns

- [X] T009 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir latidos de monitores como
  décimo y último origen, referenciar
  `specs/017-diagnostico-latidos/`, y confirmar que no queda ningún
  origen ni mecanismo relacionado pendiente
- [X] T010 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (depende de que T001-T008 estén desplegadas)
- [X] T011 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra al menos dos jobs reales
  sanos — SC-004 (depende de US1)
- [X] T012 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — job inexistente entre los 8,
  evidencia vacía sin lanzar (depende de US1)
- [X] T013 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — reproducibilidad — SC-001
  (depende de US1)
- [X] T014 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — el gasto de latido cuenta contra
  el mismo límite diario — FR-007 (depende de US1)
- [X] T015 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — `congelar --help` no muestra
  ningún `--latido-historico` — FR-011 (depende de T005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA la única
  historia
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el feature
  completo, no un MVP parcial (no hay US2 que le siga)
- **Polish (Phase 3)**: T009 es independiente de todo lo demás; el
  resto depende de que US1 esté desplegada

### Parallel Opportunities

- T001, T002 (Foundational) son paralelas entre sí
- T006 (US1, prompt) es paralelo a T003-T005
- T007, T008 (autocomprobaciones US1) son paralelas entre sí
- T009-T015 (Polish) son paralelas entre sí

---

## Implementation Strategy

### Alcance completo de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (molde de snapshot)
2. Completar Fase 2: US1 (diagnóstico de latido en vivo) — **esto ya
   es el feature completo**, no un MVP parcial
3. **PARAR Y VALIDAR**: los 6 escenarios de `quickstart.md`
4. Con esto se cierra el décimo y último mecanismo relacionado con la
   Central de Alarmas que quedaba pendiente desde 016

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre ningún monitor (FR-008)
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py`
- Ninguna tarea corrige la inconsistencia real entre `MONITOR_JOBS` y
  `heartbeat.py::DEFAULT_MANIFEST` (FR-010) — defecto del homelab,
  fuera de alcance (`BRIEFING.md`, "Feature 017")
- **Segundo feature de la serie sin ninguna tarea de modo diferido**
  (el primero fue 016) — no por omisión, sino porque no existe ninguna
  evidencia histórica real que consultar (research.md §2), comprobado
  explícitamente antes de escribir el spec
- **Feature estructuralmente casi idéntico a 016**: una sola función de
  evidencia (`_latido_actual`), sin subprocesos, sin husos horarios,
  sin consultas externas — los ficheros que lee ya existen y ya los lee
  el dashboard con la misma lógica exacta; la única pieza nueva de
  verdad es la cláusula de prompt (T006), porque aquí sí hay un
  veredicto `ok` ya calculado que replicar con precisión (research.md §3)
