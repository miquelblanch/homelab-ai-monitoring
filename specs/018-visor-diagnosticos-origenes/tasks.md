# Tasks: Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Input**: Design documents from `/specs/018-visor-diagnosticos-origenes/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api-diagnostico.md](./contracts/api-diagnostico.md), [quickstart.md](./quickstart.md)

**Tests**: sin tareas de test automatizado — mismo caso que 008: este
repo no contiene `app.py`. La validación es manual contra el
dashboard real, siguiendo [quickstart.md](./quickstart.md).

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: sin dependencia lógica entre tareas
- **[Story]**: US1 / US2 / US3, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Todo el código de este feature vive fuera de este repositorio, en
`/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py`
(plan.md, Project Structure) — sin control de versiones (research.md
§5).

---

## Phase 1: Setup

- [X] T001 Copiar `homelab-dashboard/scripts/app.py` a
  `app.py.bak-<YYYYMMDD-HHMMSS>` en el mismo directorio antes de
  cualquier edición (research.md §5) — no versionado, mismo criterio
  que el original

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T002 Implementar `get_diagnostico_para_origen(origen, identidad,
  down_since=None)` en `homelab-dashboard/scripts/app.py`, sustituyendo
  a `get_diagnostico_para_alarma()` (008) — tres ramas según
  `research.md §3`/`data-model.md`: `identidad is None` → episodio más
  reciente de `origen` sin filtro de nombre; `identidad` presente y
  `down_since is None` → `WHERE componente = ? AND origen = ?`, el más
  reciente; ambos presentes → mismo algoritmo de distancia-al-rango de
  008 (`_DIAGNOSTICO_TOLERANCIA_S`), con `origen` añadido al filtro. El
  resto de la función (consulta de `diagnosticos`/`hipotesis`,
  normalización de fechas) se reutiliza tal cual de la versión de 008
  — depende de T001
- [X] T003 [P] Añadir la constante `HOSTS_EXTERNOS_CANONICO` en
  `homelab-dashboard/scripts/app.py`, junto a `EXTERNAL_HOSTS` — copia
  literal de `evidencia.py::HOSTS_EXTERNOS` (data-model.md) —
  independiente de T002

**Checkpoint**: la función generalizada de emparejamiento está lista;
ninguna historia puede arrancar antes de esto.

---

## Phase 3: User Story 1 - Recuperar el diagnóstico de contenedor, hoy roto en producción (Priority: P1) 🎯 bug fix, MVP real

**Goal**: el emparejamiento de contenedor vuelve a funcionar contra el
esquema real de `diagnostico.db` (spec.md FR-001, SC-001).

**Independent Test**: `get_diagnostico_para_origen('contenedor',
'beszel')` no lanza, y devuelve un dict o `None` según corresponda —
quickstart.md Escenario 1.

### Implementación para User Story 1

- [X] T004 [US1] Conectar `get_diagnostico_para_origen("contenedor",
  c["name"], c.get("down_since"))` en la rama `contenedores` de
  `get_active_alarms()` (`homelab-dashboard/scripts/app.py`),
  reemplazando la llamada rota a `get_diagnostico_para_alarma()`
  (data-model.md) — depende de T002
- [X] T005 [US1] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — confirma que ya no lanza `no such
  column: contenedor` y que devuelve el episodio real esperado
  (depende de T004)

**Checkpoint**: la regresión del Principio XII está corregida — el
visor de contenedor vuelve a funcionar como en 008.

---

## Phase 4: User Story 2 - Ver el diagnóstico de los 7 orígenes con identidad estable (Priority: P1)

**Goal**: HA, disco, relay, host externo, agente, latido e inventario
muestran su diagnóstico cuando existe (spec.md FR-002/FR-003/FR-004,
SC-002).

**Independent Test**: diagnosticar en vivo un componente de cada
origen y comprobar el emparejamiento — quickstart.md Escenarios 2, 3, 6.

### Implementación para User Story 2

- [X] T006 [US2] Conectar `get_diagnostico_para_origen("ha", cid,
  chk.get("down_since"))` en la rama `ha` de `get_active_alarms()` —
  usa `cid`, no `label` (data-model.md) — depende de T002
- [X] T007 [P] [US2] Conectar `get_diagnostico_para_origen("disco",
  d["label"])` en la rama `discos` — depende de T002
- [X] T008 [P] [US2] Conectar `get_diagnostico_para_origen("relay",
  r["name"])` en la rama `relays` — depende de T002
- [X] T009 [P] [US2] Conectar `get_diagnostico_para_origen("host_externo",
  HOSTS_EXTERNOS_CANONICO.get(h["name"], h["name"]))` en la rama
  `hosts_externos` — depende de T002, T003
- [X] T010 [P] [US2] Conectar `get_diagnostico_para_origen("agente",
  a["label"])` en la sub-rama de LaunchAgents de `agentes` — usa
  `a["label"]` completo, no `a["short"]`; la sub-rama de Crons de
  Hermes NO se toca, sigue sin `diagnostico` (FR-006) — depende de T002
- [X] T011 [P] [US2] Conectar `get_diagnostico_para_origen("latido",
  m["job"])` en la rama `monitores` — usa `job`, no `label`
  (data-model.md, feature 017) — depende de T002
- [X] T012 [P] [US2] Conectar `get_diagnostico_para_origen("inventario",
  b.get("componente", ""))` en la rama `inventario` — depende de T002
- [X] T013 [US2] Validar manualmente los Escenarios 2, 3 y 6 de
  [quickstart.md](./quickstart.md) — disco/latido sin ventana, HA por
  `cid`, y la limitación real de relay en diferido (depende de
  T006-T012)

**Checkpoint**: 8 de los 10 orígenes (contenedor + estos 7) muestran su
diagnóstico cuando existe.

---

## Phase 5: User Story 3 - Ver el diagnóstico de los 2 orígenes sin identidad estable (Priority: P2)

**Goal**: backup y hub de Beszel muestran el episodio más reciente de
su origen (spec.md FR-005, SC-003).

**Independent Test**: diagnosticar en vivo el backup o el hub y
comprobar que aparece — quickstart.md Escenario 4.

### Implementación para User Story 3

- [X] T014 [P] [US3] Conectar `get_diagnostico_para_origen("backup",
  None)` en la rama `backup` de `get_active_alarms()` — depende de T002
- [X] T015 [P] [US3] Conectar `get_diagnostico_para_origen("hub_beszel",
  None)` en la rama `beszel_hub` — depende de T002
- [X] T016 [US3] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) (depende de T014, T015)

**Checkpoint**: los 10 orígenes están cubiertos — 9 con diagnóstico
posible, 1 (Crons de Hermes) documentado como fuera de alcance.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — ninguna alarma de Crons de Hermes
  lleva `diagnostico` distinto de `null` (spec.md FR-006, contrato
  garantía 10)
- [X] T018 [P] Validar que las alarmas agrupadas siguen con
  `diagnostico: null` para cualquier origen, no solo contenedor (spec.md
  FR-007, contrato garantía — sin cambios de código, T004-T015 no tocan
  ese bloque; solo confirmación)
- [X] T019 [P] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — ninguna alarma sin diagnóstico
  real cambia de aspecto (regresión, SC-006)
- [X] T020 Reconstruir y relanzar el contenedor `homelab-dashboard`
  (`docker compose up -d --build` en `docker/homelab-dashboard/`) y
  ejecutar la verificación de salud de
  [quickstart.md](./quickstart.md) (`docker ps` + `curl /api/data`) —
  depende de que T004-T015 estén aplicadas

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — empieza de inmediato
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las tres
  historias
- **US1 (Phase 3)**: depende solo de la Fase 2 — bug fix, el más
  urgente
- **US2 (Phase 4)**: depende solo de la Fase 2 — independiente de US1
  en cuanto a lógica (comparten función, no rama de código)
- **US3 (Phase 5)**: depende solo de la Fase 2 — independiente de US1/US2
- **Polish (Phase 6)**: depende de que las tres historias estén
  completas; T020 es el único punto real de despliegue

### Parallel Opportunities

- T002, T003 (Foundational) son paralelas entre sí
- T007-T012 (US2, cada rama de origen) son paralelas entre sí una vez
  completada T002/T006
- T014, T015 (US3) son paralelas entre sí
- T017, T018, T019 (Polish) son paralelas entre sí

---

## Implementation Strategy

### Orden real: arreglar antes de generalizar

1. Completar Fase 1: Setup (copia de seguridad)
2. Completar Fase 2: Foundational (función generalizada)
3. Completar Fase 3: US1 — **la regresión del Principio XII queda
   corregida aquí**, antes de tocar ningún origen nuevo
4. **PARAR Y VALIDAR**: Escenario 1 de `quickstart.md`
5. Completar Fase 4: US2 (7 orígenes) y Fase 5: US3 (2 orígenes) — en
   cualquier orden, son independientes entre sí
6. Completar Fase 6: Polish, incluyendo el único despliegue real (T020)
7. **PARAR Y VALIDAR**: el resto de escenarios de `quickstart.md`
   contra el dashboard real reconstruido

---

## Notes

- [P] = sin dependencia lógica entre tareas, aunque casi todo comparte
  fichero (`app.py`, un solo fichero, mismo caso que 008)
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni dispara un diagnóstico
  nuevo desde el dashboard (FR-010) ni escribe en `diagnostico.db`
  (FR-011)
- Ninguna tarea da cobertura de diagnóstico a los Crons de Hermes
  (FR-006/FR-012) — documentado como fuera de alcance, no una alarma
  sin emparejar por descuido
- El despliegue real (reconstrucción del contenedor) se hace **una
  sola vez**, al final (T020), no tras cada tarea individual — evita
  reconstruir 15 veces un contenedor Docker por cada rama de origen
