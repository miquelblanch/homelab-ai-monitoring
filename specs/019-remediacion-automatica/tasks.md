# Tasks: Remediación Automática — Primera Pieza (Rotación de Logs)

**Input**: Design documents from `/specs/019-remediacion-automatica/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest ya usado por `diagnostico`/`inventory` —
contra logs de prueba en un directorio temporal, nunca los reales.

**Organization**: cinco historias de usuario (spec.md), en el orden de
prioridad P1×3, P2×2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos o funciones
  independientes, sin dependencia de datos entre ellas)
- **[Story]**: US1-US5, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Paquete nuevo `src/remediacion/`, hermano de `diagnostico`/`inventory`,
sin dependencia de ninguno de los dos (plan.md, Project Structure).

---

## Phase 1: Setup

- [X] T001 Crear `src/remediacion/__init__.py` con el docstring del
  módulo — qué es, qué NO hace (sin DeepSeek, sin Telegram, sin
  dashboard — FR-013/FR-014), referencia a `specs/019-.../`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T002 [P] Implementar `src/remediacion/model.py` — dataclasses
  `ConfiguracionAccion` (`tipo_accion`, `modo`, `actualizado_en`) e
  `IntentoRemediacion` (todos los campos de data-model.md); constantes
  `MODOS = ("manual", "automatico")`, `ESTADOS = ("pendiente",
  "rechazado", "ejecutado", "fallido", "deshecho")` — sin estado
  intermedio "aprobado": `aprobar` ejecuta la rotación en la misma
  llamada (data-model.md)
- [X] T003 Implementar `src/remediacion/store.py` — `db_path()`
  (configurable vía `REMEDIACION_DB_PATH`), `init_db(conn)` (crea las
  2 tablas de data-model.md si no existen), `connect()` (context
  manager, mismo patrón que `diagnostico/store.py`), `get_modo(conn,
  tipo_accion)` (crea la fila en `manual` si no existe — FR-002),
  `set_modo(conn, tipo_accion, modo)`, `insert_intento(conn,
  intento)`, `get_intento(conn, id)`, `update_intento_estado(conn, id,
  estado, detalle, fichero_rotado=None)`, `listar_pendientes(conn,
  tipo_accion=None)`, `historial(conn, tipo_accion)` (recuento por
  estado) — depende de T002

**Checkpoint**: persistencia lista; ninguna historia puede arrancar
antes de esto.

---

## Phase 3: User Story 1 - Detectar y proponer en modo manual (Priority: P1) 🎯 MVP

**Goal**: una condición determinista detectada sobre una lista cerrada
de logs crea una propuesta pendiente, sin tocar ningún fichero
(spec.md FR-001/FR-002/FR-005/FR-006/FR-008).

**Independent Test**: log de prueba por encima del umbral → `comprobar`
crea `pendiente`; log por debajo → no crea nada — quickstart.md
Escenario 1.

### Implementación para User Story 1

- [X] T004 [US1] Implementar en `src/remediacion/acciones.py`:
  `REMEDIACION_LOGS_DIR` (configurable, por defecto `~/Library/Logs`),
  `UMBRAL_ROTACION_BYTES_DEFAULT` (configurable, 10 MB por defecto),
  `LOGS_VIGILADOS` (lista cerrada de 2 `(nombre, nombre_fichero,
  umbral_bytes)`: `health-docker`/`health-docker.log`,
  `health-ha`/`health-ha.log`) — research.md §3
- [X] T005 [US1] Implementar `comprobar_rotar_log(conn)` en
  `acciones.py` — para cada entrada de `LOGS_VIGILADOS` cuya ruta
  exista y supere su umbral: si ya hay un intento `pendiente` para ese
  `componente`, lo salta (FR-008); si no, crea el intento con
  `get_modo(conn, "rotar_log")` — en `manual` queda `pendiente`; en
  `automatico` se resuelve en la misma llamada (implementación
  completa aquí; la validación específica del modo automático es
  User Story 4). Un fichero de la lista que no existe se ignora sin
  lanzar — depende de T003, T004
- [X] T006 [US1] Conectar `comprobar` y `pendientes` en
  `src/remediacion/cli.py` (nuevo módulo, `argparse`, mismo patrón que
  `diagnostico/cli.py`) — depende de T005
- [X] T007 [P] [US1] Autocomprobación
  `tests/selftest/test_remediacion_acciones.py` —
  `comprobar_rotar_log()` contra logs de prueba: por encima del
  umbral crea `pendiente`; por debajo no crea nada; fichero ausente se
  ignora; una segunda llamada con un `pendiente` ya existente no
  duplica (FR-008)
- [X] T008 [US1] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) (depende de T006)

**Checkpoint**: detectar y proponer funciona de extremo a extremo —
MVP real, el modo manual es el comportamiento por defecto y más
seguro.

---

## Phase 4: User Story 2 - Aprobar o rechazar una propuesta pendiente (Priority: P1)

**Goal**: una propuesta pendiente se puede aprobar (rota de verdad,
sin perder contenido) o rechazar (no se toca nada) — spec.md
FR-009, Edge Cases.

**Independent Test**: aprobar rota sin pérdida; rechazar no cambia el
fichero; resolver dos veces se rechaza — quickstart.md Escenarios 2, 3.

### Implementación para User Story 2

- [X] T009 [US2] Implementar `ejecutar_rotar_log(ruta) -> str` en
  `acciones.py` — renombra `foo.log` → `foo.log.rotado-<ISO
  compacto>`, crea `foo.log` vacío nuevo; nunca trunca ni borra
  (research.md §4, FR-009). Devuelve la ruta del fichero rotado
- [X] T010 [US2] Conectar `aprobar ID` y `rechazar ID` en `cli.py` —
  ambos exigen `estado == "pendiente"` (si no, error explícito sin
  ejecutar nada); `aprobar` llama a T009 y pasa a `ejecutado` (o
  `fallido` si la ruta ya no existe — Edge Cases de spec.md);
  `rechazar` pasa a `rechazado` sin tocar el fichero — depende de T003,
  T009
- [X] T011 [P] [US2] Autocomprobación
  `tests/selftest/test_remediacion_acciones.py` — `ejecutar_rotar_log()`
  conserva el contenido íntegro en el fichero rotado, deja el original
  vacío; `tests/selftest/test_remediacion_cli.py` — aprobar/rechazar
  sobre un `pendiente` real; aprobar/rechazar sobre un intento ya
  resuelto se rechaza sin ejecutar
- [X] T012 [US2] Validar manualmente los Escenarios 2 y 3 de
  [quickstart.md](./quickstart.md) (depende de T010)

**Checkpoint**: el ciclo completo de modo manual funciona — proponer,
aprobar o rechazar.

---

## Phase 5: User Story 3 - Cambiar el modo de un tipo de acción, con su historial (Priority: P1)

**Goal**: Miquel cambia el modo de `rotar_log` desde el CLI, viendo el
historial antes — sin ninguna condición previa (spec.md
FR-003/FR-004).

**Independent Test**: `historial` muestra el recuento real; `modo
--automatico` cambia sin más — quickstart.md Escenario 4 (parte de
modo/historial).

### Implementación para User Story 3

- [X] T013 [US3] Conectar `modo TIPO_ACCION (--automatico|--manual)` y
  `historial TIPO_ACCION` en `cli.py` — `modo` imprime el historial
  (`store.historial()`) antes de aplicar el cambio (FR-004), luego
  llama a `store.set_modo()` sin ninguna otra condición (FR-003) —
  depende de T003
- [X] T014 [P] [US3] Autocomprobación
  `tests/selftest/test_remediacion_store.py` — `get_modo()` devuelve
  `manual` por defecto para un tipo de acción nunca visto antes
  (FR-002); `set_modo()` cambia y persiste; `historial()` cuenta
  correctamente por estado
- [X] T015 [US3] Validar manualmente la parte de `historial`/`modo`
  del Escenario 4 de [quickstart.md](./quickstart.md) (depende de
  T013)

**Checkpoint**: el interruptor pedido por Miquel ya funciona — el
valor central de esta feature.

---

## Phase 6: User Story 4 - Modo automático: ejecuta directo (Priority: P2)

**Goal**: con `rotar_log` en automático, `comprobar` ejecuta sin
esperar aprobación, y el registro queda igual de completo (spec.md
FR-007).

**Independent Test**: log de prueba por encima del umbral con
`rotar_log` en automático → se rota directo, sin ningún `pendiente`
— quickstart.md Escenario 4 completo.

### Implementación para User Story 4

- [X] T016 [US4] Confirmar/ajustar la rama `automatico` de
  `comprobar_rotar_log()` (T005) — el intento nace directamente en
  `ejecutado` (o `fallido`) llamando a `ejecutar_rotar_log()` en la
  misma pasada, nunca pasa por `pendiente` (FR-007) — depende de T005,
  T009
- [X] T017 [P] [US4] Autocomprobación
  `tests/selftest/test_remediacion_acciones.py` — con
  `configuracion_accion.modo="automatico"`, `comprobar_rotar_log()`
  deja el intento en `ejecutado` sin ningún `pendiente` intermedio, y
  el fichero se rota de verdad
- [X] T018 [US4] Validar manualmente el Escenario 4 completo de
  [quickstart.md](./quickstart.md) (depende de T016)

**Checkpoint**: las dos mitades del interruptor (manual/automático)
funcionan y se pueden comparar directamente.

---

## Phase 7: User Story 5 - Deshacer una rotación ya ejecutada (Priority: P2)

**Goal**: cualquier rotación ejecutada se puede deshacer sin perder
nunca nada, ni siquiera lo escrito después de rotar (spec.md
FR-010, SC-004).

**Independent Test**: rotar, escribir algo nuevo, deshacer — el
contenido de antes vuelve, lo nuevo no se pierde — quickstart.md
Escenario 5.

### Implementación para User Story 5

- [X] T019 [US5] Implementar `deshacer_rotar_log(ruta_original,
  ruta_rotada) -> str | None` en `acciones.py` — procedimiento de dos
  pasos de research.md §4: si `ruta_original` existe y tiene
  contenido, renombrarla a `foo.log.tras-deshacer-<ISO>` primero;
  luego renombrar `ruta_rotada` de vuelta a `ruta_original`. Ningún
  paso trunca ni borra (FR-010)
- [X] T020 [US5] Conectar `deshacer ID` en `cli.py` — exige `estado ==
  "ejecutado"` (si no, error explícito); llama a T019 y pasa a
  `deshecho` — depende de T003, T019
- [X] T021 [P] [US5] Autocomprobación
  `tests/selftest/test_remediacion_acciones.py` — `deshacer_rotar_log()`
  sin nada escrito después (caso simple) y con contenido nuevo escrito
  después de rotar (el caso que exige el paso extra — verifica que
  ambos ficheros sobreviven íntegros); `tests/selftest/test_remediacion_cli.py`
  — deshacer sobre un intento `pendiente` o `rechazado` se rechaza
- [X] T022 [US5] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) (depende de T020)

**Checkpoint**: las 5 historias de usuario funcionan juntas — feature
completo según el spec.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T023 [P] Conectar `--selftest` en `cli.py` (orquesta
  `test_remediacion_store`/`test_remediacion_acciones`/
  `test_remediacion_cli`, mismo patrón que `diagnostico.cli
  --selftest` vía `tests/selftest/__init__.py::run_all()` — añadir los
  3 módulos nuevos a esa orquesta)
- [X] T024 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — única vez que se tocan los logs
  reales (`health-docker.log`, `health-ha.log`), con `rotar_log`
  todavía en modo manual (depende de T008, T012)
- [X] T025 [P] Confirmar por inspección que `LOGS_VIGILADOS` (T004) no
  contiene ningún log de un componente de la lista de críticos del
  `CLAUDE.md` general (FR-012) — documentado en spec.md Assumptions,
  esta tarea es la verificación explícita antes de cerrar el feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 5 historias
- **US1 (Phase 3)**: depende solo de la Fase 2 — MVP real
- **US2 (Phase 4)**: depende de US1 (necesita intentos `pendiente` que
  resolver)
- **US3 (Phase 5)**: depende solo de la Fase 2 (usa `store.py`
  directamente) — en la práctica se valida junto a US1/US2 ya
  desplegadas
- **US4 (Phase 6)**: depende de US1 (T005) y de US2 (T009,
  `ejecutar_rotar_log`) — reutiliza ambas piezas, no añade lógica de
  persistencia nueva
- **US5 (Phase 7)**: depende de US2 (necesita intentos `ejecutado` que
  deshacer)
- **Polish (Phase 8)**: depende de que las 5 historias estén completas

### Parallel Opportunities

- T002 (model.py) es independiente antes de T003
- T007 (US1) es paralelo a T006 una vez lista T005
- T011 (US2) es paralelo a T010 una vez lista T009
- T014 (US3) es paralelo a T013
- T017 (US4) es paralelo a T016
- T021 (US5) es paralelo a T020
- T023, T024, T025 (Polish) son paralelas entre sí

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (persistencia)
3. Completar Fase 3: US1 (T004-T008) — detectar y proponer, sin
   ejecutar nada todavía
4. **PARAR Y VALIDAR**: Escenario 1 de `quickstart.md`
5. Es el punto donde el feature ya demuestra el comportamiento más
   seguro (modo manual, propuesta sin actuar)

### Entrega incremental

1. Setup + Foundational → base lista
2. US1 → MVP real, propuestas sin ejecutar
3. US2 → ciclo manual completo (aprobar/rechazar)
4. US3 → el interruptor pedido por Miquel, con historial
5. US4 → modo automático, reutilizando US1+US2
6. US5 → reversibilidad real (deshacer)
7. Polish → `--selftest` agregado, validación contra los logs reales
   (única vez, al final, deliberada), verificación de exclusión de
   críticos

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento notifica por Telegram ni escribe
  nada en el dashboard (FR-014)
- Ninguna tarea depende de `src/diagnostico/` ni de DeepSeek (FR-013,
  plan.md "Structure Decision")
- Los logs reales (`~/Library/Logs/health-docker.log`,
  `~/Library/Logs/health-ha.log`) solo se tocan una vez, en T024, al
  final, con la propiedad de "nunca destruye nada" ya verificada por
  T007/T011/T021 contra datos de prueba
