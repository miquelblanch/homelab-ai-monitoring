# Tasks: Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Input**: Design documents from `/specs/016-diagnostico-agentes/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007-015) —
verificación de lógica pura contra un `launchagents_raw.txt` de
prueba, sin tocar DeepSeek real salvo en las tareas de validación
manual explícitas de Polish.

**Organization**: una sola historia de usuario (spec.md) — el único
feature de la serie sin US2, porque no existe ningún modo diferido
posible (research.md §2).

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
  `src/diagnostico/model.py` para documentar el noveno y último valor
  real de `origen` (`"agente"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`/`"inventario"`/`"host_externo"`/`"hub_beszel"`)
  — sin cambio de esquema ni de campos, solo el docstring
  (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_agente_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más `agente_actual`
  a `null`, mismo patrón que `_snapshot_hub_beszel_vacio()` de 015
  (data-model.md)

**Checkpoint**: el molde de snapshot está listo.

---

## Phase 2: User Story 1 - Diagnosticar en vivo un agente concreto (Priority: P1) 🎯 único alcance del feature

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquier
LaunchAgent, con el mismo rigor que los demás orígenes (spec.md FR-001
a FR-007).

**Independent Test**: `congelar --agente-vivo LABEL` + `diagnosticar`
contra un agente sano concluye `no_diagnosticable` sin inventar una
causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [US1] Implementar `_agente_actual(label)` en
  `src/diagnostico/evidencia.py` + constante `LAUNCHAGENTS_RAW`
  (configurable, por defecto
  `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/launchagents_raw.txt`)
  — parsea cada línea separada por tabulador (`pid`, `exit_code`,
  `label`), busca `label` exacto; `running = pid != "-"`; `ok =
  exit_code in ("0", "-")`; `status = "running" if running else
  ("idle" if ok else "error")` — mismo cálculo exacto que
  `app.py::get_launchagents()`; `None` si `label` no existe
  (research.md §3)
- [X] T004 [US1] Implementar `congelar_agente_vivo(conn, label)` en
  `src/diagnostico/evidencia.py` — arma el snapshot (T002) con
  `agente_actual=<resultado de T003 o None>`; `componente=label`,
  `es_critico=False` siempre, `origen="agente"`, `en_vivo=True`
  (siempre — no existe modo diferido), `restart_history_id=None`
  (data-model.md) — depende de T002, T003
- [X] T005 [US1] Conectar el flag `--agente-vivo LABEL` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — **sin par `--agente-historico`**, único origen de los 9
  con un solo flag (FR-011, research.md §2/§5; contracts/cli.md) —
  depende de T004
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o un LaunchAgent del
  propio homelab" a la lista ya existente. **Sin cláusula nueva de
  restricción de contenido** (research.md §4): el estado de un agente
  es un hecho directo (`pid`/`exit_code`), no una inferencia sobre
  ausencia de datos como en relays/hosts externos/hub — independiente
  de T003-T005
- [X] T007 [P] [US1] Autocomprobación `tests/selftest/test_evidencia.py`
  — `_agente_actual()` contra un `launchagents_raw.txt` de prueba:
  agente con proceso activo (`status="running"`), agente inactivo con
  `exit_code` normal (`status="idle"`), agente inactivo con
  `exit_code` anómalo (`status="error"`), `label` inexistente
  (`None`); `congelar_agente_vivo()` arma el snapshot correctamente en
  los cuatro casos, con `en_vivo=True` siempre
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "LaunchAgent", sigue sin incluir
  la cláusula de crítico; **y** (mismo hallazgo recurrente ya
  corregido desde el diseño en 013-015)
  `test_parsear_respuesta_agente_con_varias_hipotesis`: una respuesta
  simulada con `len(hipotesis) > 1` se acepta correctamente (SC-002)

**Checkpoint**: Miquel puede diagnosticar en vivo cualquier
LaunchAgent con el mismo rigor que los demás orígenes — feature
completo (sin US2, research.md §2).

---

## Phase 3: Polish & Cross-Cutting Concerns

- [X] T009 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir agentes como noveno y último
  origen, referenciar `specs/016-diagnostico-agentes/`, y quitar la
  frase "el resto de orígenes... siguen fuera de alcance" — no queda
  ninguno
- [X] T010 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (depende de que T001-T008 estén desplegadas)
- [X] T011 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra al menos dos agentes reales
  sanos — SC-004 (depende de US1)
- [X] T012 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — agente inexistente, evidencia
  vacía sin lanzar (depende de US1)
- [X] T013 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — reproducibilidad — SC-001
  (depende de US1)
- [X] T014 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — el gasto de agente cuenta contra
  el mismo límite diario — FR-007 (depende de US1)
- [X] T015 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — `congelar --help` no muestra
  ningún `--agente-historico` — FR-011 (depende de T005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA la única
  historia
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el feature
  completo, no un MVP parcial (no hay US2 que le siga)
- **Polish (Phase 4)**: T009 es independiente de todo lo demás; el
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
2. Completar Fase 2: US1 (diagnóstico de agente en vivo) — **esto ya
   es el feature completo**, no un MVP parcial
3. **PARAR Y VALIDAR**: los 6 escenarios de `quickstart.md`
4. Con esto se cierran los 9 orígenes de la Central de Alarmas que
   este proyecto se propuso generalizar

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre ningún agente (FR-008)
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py`
- Ninguna tarea diagnostica `get_monitor_heartbeats()` (FR-010) —
  mecanismo distinto, fuera de alcance (`BRIEFING.md`, "Feature 016")
- **Este es el único feature de la serie sin ninguna tarea de modo
  diferido** — no por omisión, sino porque no existe ninguna evidencia
  histórica real que consultar (research.md §2), comprobado
  explícitamente antes de escribir el spec
- **Feature más simple de toda la serie**: una sola función de
  evidencia (`_agente_actual`), sin subprocesos, sin husos horarios,
  sin consultas externas — el fichero que lee ya existe y ya lo lee el
  dashboard con la misma lógica exacta
