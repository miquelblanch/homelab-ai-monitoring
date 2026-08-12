# Tasks: Generalizar el Diagnóstico al Inventario de Cobertura

**Input**: Design documents from `/specs/013-diagnostico-inventario/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features
007/009/010/011/012) — verificación de lógica pura contra una
`inventario.db` de prueba en un fichero temporal, sin tocar la real ni
DeepSeek, salvo en las tareas de validación manual explícitas de
Polish.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo. `src/inventory/` no cambia — solo
se consume por import (research.md §2). Sin cambios en
`src/diagnostico/store.py`, `src/diagnostico/gasto.py` ni
`src/diagnostico/_homelab_bridge.py` — ninguna tarea los toca.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: el molde de snapshot vacío que las dos historias
necesitan — mismo patrón que el Foundational de 009-012.

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el sexto valor real de
  `origen` (`"inventario"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`) — sin cambio de
  esquema ni de campos, solo el docstring (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_inventario_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más
  `inventario_ejecucion_id`/`inventario_hallazgo`/`inventario_brecha`/
  `inventario_comparacion` a `null`, mismo patrón que
  `_snapshot_relay_vacio()` de 012 (data-model.md)

**Checkpoint**: el molde de snapshot está listo para que cualquier
historia lo use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo una brecha de cobertura activa (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquier
componente del inventario, con el mismo rigor que ya tiene un
contenedor, un disco, un check de HA, un backup o un relay (spec.md
FR-001 a FR-007).

**Independent Test**: `congelar --inventario-vivo NOMBRE` +
`diagnosticar` contra un componente sin brecha activa concluye
`no_diagnosticable` sin inventar una causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [P] [US1] Añadir `from inventory import store as inv_store,
  diff as inv_diff` a `src/diagnostico/evidencia.py` + constante
  `TIPOS_INVENTARIO_EN_ALCANCE` (los 5 de `inventory.model.TIPOS_BRECHA`
  salvo `condicion_incumplida`) + implementar
  `_hallazgo_de_componente(conn_inv, ejecucion_id, nombre)` y
  `_brecha_de_componente(conn_inv, ejecucion_id, nombre)` — recorren
  `inv_store.hallazgos_de_ejecucion()`/`brechas_de_ejecucion()`
  buscando `nombre_actual == nombre`, `None` si no aparece.
  `_brecha_de_componente` **no filtra por tipo** — devuelve cualquiera
  de los 6 tipos posibles si existe; el rechazo de
  `condicion_incumplida` es solo responsabilidad de T004, filtrar aquí
  la dejaría sin nada que rechazar (research.md §2/§4/§5; hallazgo U1
  de `/speckit-analyze`, 2026-08-12) — primera vez que `diagnostico`
  importa un paquete hermano en vez de leer un fichero/DB externo
- [X] T004 [US1] Implementar `_validar_tipo_brecha_inventario(brecha)`
  en `src/diagnostico/evidencia.py` — lanza `ValueError` si
  `brecha["tipo"] == "condicion_incumplida"`, antes de congelar nada
  (FR-010, research.md §5, mismo patrón que `_validar_check_ha()`
  bloqueando la cerradura en 010) — depende de T003
- [X] T005 [US1] Implementar `_comparacion_dict(comparacion)` en
  `src/diagnostico/evidencia.py` + constante
  `INVENTARIO_COMPARACION_MAX_ENTRADAS = 30` — envuelve cada una de las
  cuatro listas de `inventory.diff.Comparacion` en `{"total", "muestra"}`
  acotada al límite (research.md §11, hallazgo real: el caso más grande
  medido contra la línea base real llega a 319) — depende de T003
- [X] T006 [US1] Implementar `congelar_inventario_vivo(conn, nombre)`
  en `src/diagnostico/evidencia.py` — ejecución =
  `inv_store.latest_ejecucion()`; resuelve hallazgo/brecha (T003),
  valida FR-010 (T004); si hay brecha con `primera_ejecucion_id > 1`,
  arma `inventario_comparacion` con `inv_diff.compare_runs()` +
  `_comparacion_dict()` (T005) contra `primera_ejecucion_id - 1`
  (**nunca** contra `ejecucion_id - 1`, research.md §4); arma el
  snapshot (T002); `componente=nombre`, `es_critico=False` siempre,
  `origen="inventario"`, `en_vivo=True`,
  `ventana_inicio=ventana_fin=ejecucion["fecha"]`,
  `restart_history_id=None` (data-model.md) — depende de T002, T003,
  T004, T005
- [X] T007 [US1] Conectar el flag `--inventario-vivo NOMBRE` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — `NOMBRE` puede tener espacios, entrecomillado igual que
  `--relay-vivo`; capturar `ValueError` de T004/T006 e imprimirlo en
  stderr con código de salida 1, mismo tratamiento que `--ha-vivo` con
  la cerradura (contracts/cli.md) — depende de T006
- [X] T008 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o una brecha de cobertura
  del propio inventario de monitorización" a la lista ya existente.
  **Sin cláusula nueva de restricción de contenido** (research.md §7):
  a diferencia de relays (012), la exclusión de `condicion_incumplida`
  ya se resolvió en código antes de llegar aquí (T004) — independiente
  de T003-T007
- [X] T009 [P] [US1] Autocomprobación `tests/selftest/test_evidencia.py`
  — `_hallazgo_de_componente()`/`_brecha_de_componente()` contra una
  `inventario.db` de prueba en fichero temporal (componente existente
  con brecha, componente sano, componente inexistente);
  `_validar_tipo_brecha_inventario()` lanza `ValueError` solo para
  `condicion_incumplida`; `_comparacion_dict()` acota correctamente una
  lista simulada de más de 30 entradas conservando el `total` real;
  `congelar_inventario_vivo()` arma el snapshot correctamente en los
  tres casos (con brecha, sano, inexistente)
- [X] T010 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "inventario", sigue sin incluir la
  cláusula de crítico (`es_critico=False` siempre); **y** (mismo
  hallazgo recurrente que motivó C1 en 009/010/011/012 — corregido
  aquí desde el principio, no como corrección posterior de
  `/speckit-analyze`) `test_parsear_respuesta_inventario_con_varias_hipotesis`:
  una respuesta simulada de un episodio de inventario con
  `len(hipotesis) > 1` se acepta correctamente (SC-002)

**Checkpoint**: Miquel puede diagnosticar en vivo cualquier componente
del inventario con el mismo rigor que los demás orígenes — User Story
1 completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un momento pasado de inventario, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar una ejecución pasada concreta del
inventario y diagnosticar una brecha que existió en ese momento, con
la misma garantía de reproducibilidad que los demás orígenes (spec.md
FR-001, FR-002; SC-001, SC-005).

**Independent Test**: `congelar --inventario-historico` dos veces sobre
la misma `EJECUCION_ID` y comprobar que `diagnosticar` produce el mismo
`conclusion_tipo` las dos veces — quickstart.md Escenario 5.

### Implementación para User Story 2

- [X] T011 [US2] Implementar `congelar_inventario_historico(conn,
  nombre, ejecucion_id)` en `src/diagnostico/evidencia.py` — ejecución
  = `inv_store.get_ejecucion(conn_inv, ejecucion_id)` (`None` si no
  existe, mismo criterio que un `check_id`/`label` inexistente:
  congela igual con evidencia vacía, research.md §9); reutiliza
  `_hallazgo_de_componente`/`_brecha_de_componente`/
  `_validar_tipo_brecha_inventario`/`_comparacion_dict` (T003-T005, ya
  agnósticos a qué ejecución se les pasa); `componente=nombre`
  (**nunca** `nombre@ejecucion_id` — research.md §3, mismo patrón que
  `check_id`/`label` de HA/discos); `ventana_inicio=ventana_fin=
  ejecucion["fecha"]` si la ejecución existe, si no el momento de
  invocar `congelar` (research.md §9); `en_vivo=False` — depende de
  T002-T005
- [X] T012 [US2] Conectar el flag `--inventario-historico
  "NOMBRE@EJECUCION_ID"` en `src/diagnostico/cli.py` — `partition("@")`
  igual que `--disco-historico`/`--ha-historico`, con `EJECUCION_ID`
  parseado como `int`; mismo orden `identificador@localizador` que esos
  dos orígenes, a diferencia de `--relay-historico`/`--backup-historico`
  (research.md §3/§8; contracts/cli.md) — depende de T011
- [X] T013 [P] [US2] Autocomprobación `tests/selftest/test_evidencia.py`
  (ampliar T009) — `congelar_inventario_historico()` reproducible (dos
  congelados de la misma `NOMBRE@EJECUCION_ID` producen la misma
  evidencia); `ejecucion_id` inexistente congela igual con evidencia
  vacía, `componente` = el `NOMBRE` pedido; comparación anclada a
  `primera_ejecucion_id - 1` y **no** a `ejecucion_id - 1` con un caso
  simulado donde ambos difieren (research.md §4, el hallazgo real de
  §10: la ejecución pedida no tiene por qué ser la primera de la racha)
- [X] T014 [P] [US2] Autocomprobación `tests/selftest/test_deepseek.py`
  (ampliar T010) — prueba de integración de
  `deepseek.diagnosticar_episodio()` con `origen="inventario"` y una
  respuesta simulada de DeepSeek: confirma que ningún tratamiento
  especial de otro origen (la validación de "nunca nombres un relay
  concreto" de 012, la cláusula de estado ya calculado de HA de 010)
  se dispara por error para `origen="inventario"` — este origen no
  tiene ningún invariante de contenido propio que validar después de
  la respuesta (research.md §7), toda su restricción de alcance ya se
  resolvió antes de llamar (T004)

**Checkpoint**: las dos historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido (FR-007,
`gasto.py` sin cambios) protegiendo también al inventario.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T015 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir inventario a la lista de
  orígenes soportados y referenciar
  `specs/013-diagnostico-inventario/`; dejar solo hosts externos, hub
  de Beszel y agentes en la lista de "orígenes que siguen fuera de
  alcance"
- [X] T016 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (sin migración de esquema; depende de que T001-T014 estén
  desplegadas)
- [X] T017 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra al menos un componente sano
  real — SC-004 (depende de US1)
- [X] T018 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — componente inexistente, evidencia
  vacía sin lanzar (depende de US1)
- [X] T019 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — diagnóstico en diferido contra al
  menos una de las cuatro brechas reales conocidas (ejecuciones #19,
  #28, #31, #52) — SC-005, la garantía central de este feature (la
  segunda línea base real del proyecto tras 012); confirmar que
  `inventario_comparacion.ejecucion_previa_id` es 2 y no
  `EJECUCION_ID - 1` (research.md §10); validar **antes** que el resto
  de escenarios de diferido, mismo criterio que 011/012 dieron
  prioridad a su propia garantía central (depende de US2)
- [X] T020 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido —
  SC-001 (depende de US2)
- [X] T021 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de
  inventario cuenta contra el mismo límite diario que los demás
  orígenes — FR-007 (depende de US1 o US2)
- [X] T022 [P] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — una brecha real de tipo
  `condicion_incumplida` se rechaza antes de congelar — FR-010 (depende
  de US1)
- [X] T023 [P] Validar manualmente el Escenario 8 de
  [quickstart.md](./quickstart.md) — `EJECUCION_ID` inexistente,
  evidencia vacía sin lanzar (depende de US2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real; T003
  es la base que también reutilizará US2 al completo
- **US2 (Phase 3)**: depende de la Fase 1 y de T003-T005 (US1) — a
  diferencia de 012 (donde vivo/diferido leían fuentes distintas y
  compartían poco código), aquí `congelar_inventario_historico`
  reutiliza literalmente las mismas cuatro funciones que
  `congelar_inventario_vivo`, con la única diferencia de qué ejecución
  se les pasa — la dependencia de US2 hacia US1 es más fuerte que en
  cualquier feature anterior de este proyecto
- **Polish (Phase 4)**: T015 es independiente de todo lo demás; T016
  depende de que US1/US2 estén desplegadas; T019 es la validación más
  importante de Polish — confirma la garantía central del feature
  contra brechas reales ya conocidas, no simuladas

### Parallel Opportunities

- T001, T002 (Foundational) son paralelas entre sí
- T003 (US1) es la base de T004/T005, que a su vez son paralelas entre
  sí antes de que T006 las use
- T008 (US1, prompt) es paralelo a T003-T007
- T009, T010 (autocomprobaciones US1) son paralelas entre sí
- T013, T014 (autocomprobaciones US2) son paralelas entre sí, e
  independientes de T009/T010 salvo por compartir fichero
- T015-T023 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende

---

## Parallel Example: User Story 1

```bash
# T004 (validación FR-010) y T005 (límite defensivo) pueden ir en paralelo tras T003:
Task: "Implementar _validar_tipo_brecha_inventario() en src/diagnostico/evidencia.py"
Task: "Implementar _comparacion_dict() en src/diagnostico/evidencia.py"

# Autocomprobaciones de US1, en paralelo entre sí una vez T006/T007/T008 estén listas:
Task: "Autocomprobación _hallazgo_de_componente/congelar_inventario_vivo en tests/selftest/test_evidencia.py"
Task: "Autocomprobación prompt generalizado + SC-002 en tests/selftest/test_deepseek.py"
```

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (molde de snapshot)
2. Completar Fase 2: US1 (diagnóstico de inventario en vivo)
3. **PARAR Y VALIDAR**: Escenario 2 de `quickstart.md` contra al menos
   un componente sano real
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar una brecha de cobertura con el mismo rigor que los
   demás orígenes

### Entrega incremental

1. Foundational → molde de snapshot listo, sin romper
   007/009/010/011/012
2. US1 → diagnóstico de inventario en vivo, demo posible (MVP!)
3. US2 → diagnóstico en diferido, reproducible, apoyado en la misma
   base de funciones que US1 — **y la segunda comprobación real de
   este proyecto contra una línea base real desde el arranque** (T019,
   las cuatro brechas reales de #19/#28/#31/#52)
4. Polish → validación manual completa de los 8 escenarios,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento declara un estado esperado nuevo,
  añade vigilancia ni corrige qué llega al dashboard (FR-008) — eso
  sigue siendo trabajo de `inventory.cli` y de los features 001-006
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py`, `src/diagnostico/_homelab_bridge.py` ni
  ningún fichero de `src/inventory/` — sin migración de esquema, el
  gasto ya es agnóstico al origen, y este feature solo consume
  `inventory` por import, nunca lo modifica
- **T009/T010 incluyen desde el principio la prueba de SC-002
  (`len(hipotesis) > 1`)** que `/speckit-analyze` tuvo que añadir como
  corrección (hallazgo C1) en 009, 010, 011 y 012 — cuarta vez seguida
  que se detecta la misma brecha recurrente; en este feature se escribe
  directamente en `tasks.md`, no se espera a que `/speckit-analyze` la
  vuelva a encontrar
- **T004 es la tarea que aplica, desde el diseño, la misma lección que
  012 tuvo que aprender a posteriori (hallazgo F1)**: una restricción
  de alcance ("nunca esto") se valida en código contra el propio dato
  de entrada, no solo se pide en el prompt y se confía en que el modelo
  la respete
