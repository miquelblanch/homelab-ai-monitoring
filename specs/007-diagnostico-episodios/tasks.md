# Tasks: Diagnóstico de Episodios (Frente 2, sin remediación)

**Input**: Design documents from `/specs/007-diagnostico-episodios/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`), mismo
patrón sin pytest que ya usa `inventory` (feature 001-006) — no TDD estricto
("rojo antes de verde"), sino verificación de lógica pura sin tocar
DeepSeek/Docker/`homelab.db` reales, igual que el resto del repo.

**Organization**: agrupadas por historia de usuario (spec.md) para poder
implementar y probar cada una por separado.

**Nota de versión**: esta revisión incorpora T023 y T031 (nuevas), y
reescribe research.md §6/contracts/cli.md, para resolver los hallazgos B1,
E1 y E2 de `/speckit-analyze` (2026-08-10) — ver el detalle en cada tarea
nueva. El resto de tareas conserva su contenido, solo cambia su número
donde hizo falta hueco.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin dependencia)
- **[Story]**: US1 / US2 / US3, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Single project, mismo layout que `src/inventory/` (plan.md, Project
Structure): `src/diagnostico/` para el código, `tests/selftest/` para las
autocomprobaciones.

---

## Phase 1: Setup

**Purpose**: esqueleto del paquete nuevo, sin lógica todavía

- [X] T001 Crear el esqueleto de `src/diagnostico/`: `__init__.py` y
  `cli.py` con `argparse` para los cuatro subcomandos de
  [contracts/cli.md](./contracts/cli.md) (`congelar --historico/--vivo`,
  `diagnosticar`, `mostrar`, `--selftest`), cada uno llamando por ahora a
  un `raise NotImplementedError`
- [X] T002 [P] Crear `src/diagnostico/_homelab_bridge.py` — copia mínima
  deliberada (research.md §7) de `get_secret`, `record_heartbeat`,
  `docker_critical`, `docker_never_restart` desde
  `src/inventory/_homelab_bridge.py`, sin las funciones de `ha_monitor`
  (este feature no toca HA)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: esquema de datos y acceso a evidencia que las tres historias
necesitan

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T003 [P] Implementar el esquema SQLite completo (`episodios`,
  `diagnosticos`, `hipotesis`, `gasto_diario`) y `connect()`/`init_db()`
  en `src/diagnostico/store.py`, según [data-model.md](./data-model.md)
  (mismo patrón `sqlite3.Row` + `CREATE TABLE IF NOT EXISTS` que
  `inventory/store.py`)
- [X] T004 [P] Crear los dataclasses `Episodio`, `Hipotesis`,
  `Diagnostico`, `GastoDiario` en `src/diagnostico/model.py`, según
  [data-model.md](./data-model.md)
- [X] T005 [P] Implementar en `src/diagnostico/evidencia.py` la lista
  blanca de subprocesos de solo lectura (`_READONLY_ALLOWLIST`/`_run_ro`,
  copiado y ampliado de `inventory/sources.py` con
  `("docker", "logs")` además de `("docker", "ps")`/`("docker",
  "inspect")`), según research.md §5
- [X] T006 Implementar en `src/diagnostico/evidencia.py` los lectores de
  `homelab.db` — `restart_history_row(id)`, `container_metrics_window(
  container, inicio, fin)`, `disk_metrics_near(timestamp)` — con
  `sqlite3.connect()` normal (sin `mode=ro`, research.md §4) y disciplina
  de solo `SELECT` (depende de T005, mismo fichero)

**Checkpoint**: persistencia propia y acceso a evidencia listos; ninguna
historia de usuario puede arrancar antes de esto.

---

## Phase 3: User Story 1 - Diagnosticar un episodio en diferido, reproduciblemente (Priority: P1) 🎯 MVP (parcial)

**Goal**: congelar el snapshot de un episodio (histórico o en vivo),
persistirlo, y poder inspeccionarlo — la base de la reproducibilidad
(FR-001, FR-002).

**Independent Test**: congelar dos veces el mismo contenedor no debe
producir dos episodios idénticos por accidente; congelar un episodio
histórico y volver a `mostrar`lo debe reproducir exactamente la misma
evidencia guardada. **Nota de dependencia real**: el escenario de
aceptación 1 del spec ("produce una conclusión") solo se completa de
verdad una vez que la Fase 4 (US2) también existe — se listan en el
orden de prioridad del spec, no en orden de dependencia técnica
(research.md §8 ya separa "congelar" de "diagnosticar" a propósito).

### Implementación para User Story 1

- [X] T007 [US1] Implementar `congelar_historico(restart_history_id)` en
  `src/diagnostico/evidencia.py` — arma el `snapshot_evidencia` (fila de
  `restart_history` + ventana de `container_metrics`/`disk_metrics`),
  según [data-model.md](./data-model.md) "Forma del snapshot" (FR-001,
  FR-002; depende de T006)
- [X] T008 [US1] Implementar `congelar_vivo(contenedor)` en
  `src/diagnostico/evidencia.py` — `docker inspect`/`docker logs --tail
  200` + última ventana de `container_metrics` disponible (FR-001,
  FR-002; mismo fichero que T007)
- [X] T009 [US1] Implementar `es_critico(contenedor)` en
  `src/diagnostico/evidencia.py`, vía
  `_homelab_bridge.docker_critical()` (T002), y usarlo desde T007/T008
  para fijar `episodios.es_critico` en el momento de congelar — nunca
  reevaluado después (research.md §7, FR-013a)
- [X] T010 [P] [US1] Implementar `insert_episodio(conn, episodio)` en
  `src/diagnostico/store.py`, según [data-model.md](./data-model.md)
  (depende de T003/T004; fichero distinto de T007-T009)
- [X] T011 [US1] Conectar el subcomando `congelar --historico ID` /
  `congelar --vivo CONTENEDOR` en `src/diagnostico/cli.py`, imprimiendo
  el `episodio_id` asignado, según [contracts/cli.md](./contracts/cli.md)
  (depende de T007, T008, T009, T010)
- [X] T012 [US1] Implementar el subcomando `mostrar EPISODIO_ID` en
  `src/diagnostico/cli.py` — imprime los campos del episodio congelado
  (sin diagnósticos todavía, eso lo añade T020) según
  [contracts/cli.md](./contracts/cli.md) (Principio VIII; mismo fichero
  que T011)
- [X] T013 [P] [US1] Autocomprobación
  `tests/selftest/test_evidencia.py` — forma del snapshot, `es_critico`
  fijado en el momento correcto, `congelar_historico`/`congelar_vivo`
  contra una base `homelab.db` de prueba en un fichero temporal (nunca
  la real)
- [X] T014 [P] [US1] Autocomprobación `tests/selftest/test_store.py` —
  esquema idempotente (`init_db()` dos veces no falla), inserción y
  lectura de `episodios`

**Checkpoint**: los episodios se congelan y se pueden inspeccionar; la
reproducibilidad completa (SC-001) se comprueba una vez cerrada la Fase 4.

---

## Phase 4: User Story 2 - Formular y contrastar varias hipótesis, con registro (Priority: P1) 🎯 MVP

**Goal**: la llamada real a DeepSeek, con contraste incluido en la misma
respuesta (research.md §2), y su registro persistente y legible después
(FR-003 a FR-008, Principio VIII).

**Independent Test**: revisar el registro (`mostrar`) de una ejecución
cualquiera de `diagnosticar` — debe listar más de una hipótesis, cada una
con su comprobación concreta y su desenlace, reconstruible sin volver a
ejecutar nada.

### Implementación para User Story 2

- [X] T015 [P] [US2] Implementar `llamar_deepseek(prompt, modelo)` en
  `src/diagnostico/deepseek.py` — `urllib.request`/`ssl`, temperatura 0,
  `max_tokens=DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` (research.md §6),
  devuelve el JSON crudo de la respuesta incluida `usage` (research.md
  §2/§3; fichero nuevo, independiente de la Fase 3)
- [X] T016 [US2] Implementar `construir_prompt(snapshot, es_critico)` en
  `src/diagnostico/deepseek.py` — pide hipótesis + contraste + desenlace
  en JSON estructurado; si `es_critico`, incluye la instrucción explícita
  de no proponer ninguna acción (FR-004, FR-005, FR-013; mismo fichero
  que T015)
- [X] T017 [US2] Implementar `parsear_respuesta(json_bruto)` en
  `src/diagnostico/deepseek.py` — valida el invariante FR-007
  (exactamente `causa_probable` con ≥1 hipótesis `confirmada`, o
  `no_diagnosticable` sin ninguna) antes de devolver la lista de
  hipótesis y la conclusión; si la respuesta es HTTP 200 pero el
  contenido no cumple el invariante (JSON mal formado, o ambigüedad
  entre las dos conclusiones), lo señala como fallo de parseo — mismo
  tratamiento que "DeepSeek no responde" en los Edge Cases del spec, no
  un caso nuevo sin definir (mismo fichero que T015/T016)
- [X] T018 [P] [US2] Implementar `insert_diagnostico(conn, diagnostico)` /
  `insert_hipotesis(conn, hipotesis)` en `src/diagnostico/store.py`, según
  [data-model.md](./data-model.md) (depende de T003/T004; fichero
  distinto de T015-T017)
- [X] T019 [US2] Conectar el subcomando `diagnosticar EPISODIO_ID` en
  `src/diagnostico/cli.py` — carga el snapshot ya persistido (nunca
  vuelve a consultar `homelab.db`/Docker, FR-002), construye el prompt,
  llama a DeepSeek, parsea, persiste, imprime la conclusión; si T017
  señala un fallo de parseo, se comporta igual que el Edge Case "DeepSeek
  no responde" (registra el fallo, concluye `no_diagnosticable`, nunca
  aborta sin persistir nada), según
  [contracts/cli.md](./contracts/cli.md) (depende de T011, T015-T018)
- [X] T020 [US2] Ampliar `mostrar` (T012) en `src/diagnostico/cli.py`
  para imprimir, por cada intento de diagnóstico del episodio, sus
  hipótesis con comprobación y desenlace (FR-006, mismo fichero que T019)
- [X] T021 [P] [US2] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt incluye la cláusula "sin acción" cuando `es_critico=True`,
  `parsear_respuesta` acepta una respuesta bien formada y trata como
  fallo de parseo una mal formada (JSON inválido, o las dos conclusiones
  a la vez), invariante FR-007 comprobado, **y** que una respuesta con
  evidencia suficiente produce `len(hipotesis) > 1` (SC-003) — sin
  llamada HTTP real, respuesta simulada
- [X] T022 [P] [US2] Ampliar `tests/selftest/test_store.py` (T014) —
  `insert_diagnostico`/`insert_hipotesis` de ida y vuelta, varios
  `diagnosticos` sobre el mismo `episodio_id` conviven sin pisarse
  (necesario para comprobar SC-001 comparando intentos)
- [X] T023 [P] [US2] Autocomprobación **nueva**
  `tests/selftest/test_reproducibilidad.py` — resuelve el hallazgo **E2**
  de `/speckit-analyze` (2026-08-10): simula `llamar_deepseek` para que
  devuelva la misma respuesta JSON fija en dos invocaciones de
  `diagnosticar` seguidas sobre el mismo `episodio_id` ya congelado (un
  fixture, no `homelab.db` real), y comprueba que los dos `diagnosticos`
  resultantes tienen el mismo `conclusion_tipo` y el mismo desenlace por
  hipótesis y en el mismo orden. Cubre la parte de SC-001 que el código
  puede garantizar de verdad (la tubería determinista); la varianza real
  de DeepSeek en producción sigue siendo el hallazgo aparte que el propio
  Edge Case del spec ya reconoce, no algo que un mock pueda demostrar
  (depende de T017, T019, T022)

**Checkpoint**: `congelar` → `diagnosticar` → `mostrar` funcionan de
extremo a extremo. SC-001 (reproducibilidad, ahora con prueba automatizada
de su parte determinista) y SC-003 (más de una hipótesis registrada, con
comprobación explícita en T021) ya son comprobables sin depender solo de
una ejecución manual contra DeepSeek real.

---

## Phase 5: User Story 3 - No gastar más de lo previsto en un día (Priority: P2)

**Goal**: cortacircuitos de gasto diario a partir de tokens reales
(FR-009, FR-010).

**Independent Test**: fijar `DIAGNOSTICO_LIMITE_EUR_DIA` a un valor ya
superado y comprobar que `diagnosticar` no llama a DeepSeek — concluye
`no_diagnosticable` por límite alcanzado.

### Implementación para User Story 3

- [X] T024 [P] [US3] Implementar `PRECIOS_EUR_POR_MILLON_TOKENS`,
  `registrar_coste(tokens_entrada, tokens_salida, modelo)` y
  `gasto_hoy()` en `src/diagnostico/gasto.py`, según research.md §6
  (fichero nuevo, independiente de las Fases 3-4)
- [X] T025 [US3] Implementar `hay_presupuesto()` en
  `src/diagnostico/gasto.py` — la estimación previa a la llamada es
  `tokens_entrada_reales + DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` (research.md
  §6, hallazgo **B1** de `/speckit-analyze`: cifra concreta y
  configurable, no un margen "prudente" sin definir) contra
  `PRECIOS_EUR_POR_MILLON_TOKENS` y el límite del día (FR-010; mismo
  fichero que T024)
- [X] T026 [US3] Conectar el cortacircuitos en el subcomando
  `diagnosticar` (T019) en `src/diagnostico/cli.py` — si
  `hay_presupuesto()` es falso, omite la llamada a DeepSeek y persiste
  `no_diagnosticable` con motivo "límite de gasto diario alcanzado"
  (depende de T019, T025)
- [X] T027 [P] [US3] Implementar `upsert_gasto_diario(conn, dia, coste,
  limite)` en `src/diagnostico/store.py`, según
  [data-model.md](./data-model.md) (límite congelado por día; fichero
  distinto de T024-T026)
- [X] T028 [P] [US3] Autocomprobación `tests/selftest/test_gasto.py` —
  cálculo de coste a partir de tokens fijos, `hay_presupuesto()` usando
  la cifra concreta de `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` en los tres
  casos (por debajo / al límite / por encima), reinicio del acumulado al
  cambiar de día natural (Edge Case del spec)

**Checkpoint**: las tres historias de usuario funcionan juntas — el
feature completo según el spec (sin remediación, con presupuesto
controlado por una cifra concreta, no una estimación vaga).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T029 [P] Conectar `--selftest` en `src/diagnostico/cli.py` para
  ejecutar `tests.selftest.run_all()`, mismo patrón que
  `inventory.cli --selftest`
- [X] T030 Validar contra la línea base de `beszel` (FR-011, SC-002):
  ejecutar `congelar --historico` + `diagnosticar` real. **Completada el
  2026-08-10 con `DEEPSEEK_API_KEY` ya configurada.** `congelar
  --historico` se ejecutó contra 6 episodios reales de `beszel`
  (`restart_history_id` 4, 16, 17, 25, 79, 81 → episodios 6-11); de esos,
  16/17/25 tienen evidencia de métricas totalmente vacía (anteriores al
  2026-04-17, fuera incluso de `container_metrics_hourly`) y 4/79/81
  tienen 2 muestras horarias cada uno. `diagnosticar` real (DeepSeek,
  `deepseek-chat`) concluyó `no_diagnosticable` en **6 de 6** — ninguno
  inventó una causa. Coste total de toda la validación de T030+T032:
  ~0,017 € (muy por debajo del límite de 5 €/día). Dos hallazgos reales
  de esta ejecución, no anticipados en el plan:
  1. Un intento sobre un episodio distinto (#12) devolvió el mismo
     `conclusion_tipo` (`no_diagnosticable`) las dos veces pero un número
     de hipótesis distinto (0 y 3) — SC-001 exige reproducibilidad de la
     conclusión, que se cumplió; la varianza en el conteo de hipótesis es
     exactamente el Edge Case que el spec ya preveía ("hallazgo a
     registrar y resolver, no un comportamiento aceptable") — queda
     abierto, no se ha intentado resolver en esta sesión.
  2. Al probar el Escenario 4 (contenedor crítico, ver T032) el modelo
     marcó una hipótesis "confirmada" en una respuesta que a la vez
     concluía `no_diagnosticable` — viola el invariante FR-007 tal como
     está escrito en el prompt, y el parser lo rechazó correctamente 3
     veces seguidas (`diagnosticos` #12/13/14: "respuesta de DeepSeek
     inconsistente"). Causa raíz: el prompt no dejaba claro que
     "confirmada" significa "esta ES la causa", no "esta comprobación se
     completó" — el modelo lo confundía en el caso concreto de un
     contenedor sano sin ningún episodio real que explicar. Corregido en
     `deepseek.py` (`_PROMPT_INSTRUCCIONES`, aclaración explícita del
     significado de "confirmada"); tras el cambio, la siguiente llamada
     (#15) fue consistente. No se ha vuelto a probar en gran volumen si
     la ambigüedad reaparece en otros escenarios — vigilar en uso real.
- [X] T031 Crear fixture de regresión **nueva** para la línea base de
  `beszel` — resuelve el hallazgo **E1** de `/speckit-analyze`
  (2026-08-10): usa los tres snapshots REALES congelados en T030
  (`restart_history_id` 16, 17, 25 — evidencia vacía verificada, no
  elegidos a mano) en `tests/selftest/fixtures/beszel_baseline.py`, y
  `tests/selftest/test_baseline_beszel.py` que llama a
  `diagnosticar_episodio` sobre esos tres snapshots fijos con una
  respuesta DeepSeek **simulada** (no real — sigue siendo así: una
  fixture de regresión no debe gastar presupuesto real cada vez que se
  ejecuta el selftest), comprobando que la tubería determinista persiste
  `no_diagnosticable` para los tres sin alterarlo. T030 sí confirmó por
  separado, con una llamada real, que los mismos tres (16, 17, 25)
  concluyen `no_diagnosticable` de verdad — esta fixture y esa
  confirmación son complementarias, no la misma cosa (depende de T007,
  T017)
- [X] T032 [P] Ejecutar los 4 escenarios de
  [quickstart.md](./quickstart.md) contra el homelab real y confirmar
  los resultados esperados de cada uno. **Los 4 confirmados el
  2026-08-10**: Escenario 1 (reproducibilidad) — mismo `conclusion_tipo`
  en dos intentos sobre el mismo episodio, con la salvedad del conteo de
  hipótesis distinto ya registrada en T030; Escenario 2 (línea base de
  `beszel`) — 6/6 episodios reales concluyen `no_diagnosticable`;
  Escenario 3 (cortacircuitos, `DIAGNOSTICO_LIMITE_EUR_DIA=0.0`) —
  concluye sin llamar; Escenario 4 (contenedor crítico, `homeassistant`
  en vivo) — 5 hipótesis contrastadas, todas descartadas o sin evidencia,
  ninguna acción propuesta ni ejecutada (FR-013/FR-013a), tras corregir
  la ambigüedad del prompt encontrada en T030.
- [X] T033 [P] Añadir un docstring de módulo a
  `src/diagnostico/__init__.py` explicando el alcance (solo contenedores,
  sin remediación — ver spec.md), mismo estilo que
  `inventory/store.py`/`inventory/deliver.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — empieza de inmediato
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las tres
  historias
- **US1 (Phase 3)** y **US2 (Phase 4)**: ambas P1, dependen solo de la
  Fase 2 en cuanto a código, pero **la prueba de aceptación completa de
  US1 depende de que US2 también exista** (research.md §8) — no son
  independientes de verdad pese a compartir prioridad
- **US3 (Phase 5)**: depende de que `diagnosticar` (T019, Fase 4) ya
  exista — el cortacircuitos envuelve esa llamada, no tiene sentido antes
- **Polish (Phase 6)**: depende de que las tres historias estén completas;
  T031 depende además de que T030 haya identificado los episodios
  concretos de la línea base

### Within Each User Story

- Modelo/esquema (Fase 2) antes que cualquier lectura/escritura
- `evidencia.py` (congelar) antes que `cli.py` lo exponga
- `deepseek.py` (llamar/parsear) antes que `cli.py` lo conecte a
  `diagnosticar`
- `gasto.py` antes de envolver el cortacircuitos en `diagnosticar`
- Autocomprobaciones después de la implementación que verifican (no es
  TDD estricto — mismo patrón que el resto del repo)

### Parallel Opportunities

- T002 (Setup) es paralelo a T001 (ficheros distintos)
- T003, T004, T005 (Foundational) son paralelos entre sí (ficheros
  distintos); T006 depende de T005 (mismo fichero)
- T010 (US1, `store.py`) es paralelo a T007-T009 (US1, `evidencia.py`)
- T013, T014 (autocomprobaciones US1) son paralelas entre sí
- T015 (US2, `deepseek.py`) es paralelo a toda la Fase 3 salvo que
  comparta fichero — no lo comparte
- T018 (US2, `store.py`) es paralelo a T015-T017 (US2, `deepseek.py`)
- T021, T022, T023 (autocomprobaciones US2) son paralelas entre sí una
  vez que T022 esté lista (T023 depende de T022 además de T017/T019)
- T024 (US3, `gasto.py`) es paralelo a T027 (US3, `store.py`)
- T028 (autocomprobación US3) es paralela a T024-T027 una vez que existe
  la lógica que comprueba
- T029, T032, T033 (Polish) son paralelas entre sí; T030 es manual y
  secuencial (usa las mismas rutas de CLI que T032, mejor no solaparlas);
  T031 depende de T030 y no puede paralelizarse con ella

---

## Parallel Example: Foundational

```bash
# T003, T004, T005 se pueden hacer a la vez (ficheros distintos):
Task: "Esquema SQLite completo en src/diagnostico/store.py"
Task: "Dataclasses Episodio/Hipotesis/Diagnostico/GastoDiario en src/diagnostico/model.py"
Task: "Lista blanca de subprocesos en src/diagnostico/evidencia.py"
```

## Parallel Example: User Story 2

```bash
# T015 y T018 se pueden hacer a la vez (ficheros distintos):
Task: "llamar_deepseek() en src/diagnostico/deepseek.py"
Task: "insert_diagnostico()/insert_hipotesis() en src/diagnostico/store.py"
```

---

## Implementation Strategy

### MVP real de este feature (US1 + US2 juntas)

A diferencia de la mayoría de features de Spec Kit, aquí el MVP no es
"solo la primera historia" — US1 y US2 comparten la misma tubería
(congelar → diagnosticar) y ninguna es demostrable por sí sola sin la
otra (research.md §8). El MVP real es:

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (bloquea todo)
3. Completar Fase 3: US1 (congelar/mostrar)
4. Completar Fase 4: US2 (diagnosticar de verdad, incluida T023)
5. **PARAR Y VALIDAR**: correr `test_reproducibilidad.py` (T023) y luego
   el Escenario 1 de `quickstart.md` — reproducibilidad de principio a fin
6. Ese es el punto en el que el feature ya demuestra el caso de prueba de
   `beszel` (FR-011) sin ningún límite de gasto todavía activo

### Entrega incremental

1. Setup + Foundational → base lista
2. US1 + US2 juntas → MVP real, demo posible (congelar + diagnosticar +
   mostrar, sin cortacircuitos de gasto todavía — riesgo aceptado solo
   para la fase de desarrollo, nunca para uso real sin T024-T027)
3. US3 → gasto controlado, ya seguro para uso repetido sin supervisión
   del acumulado a mano
4. Polish → `--selftest`, validación contra la línea base de `beszel`
   (manual en T030, automatizada en T031), quickstart completo

---

## Notes

- [P] = ficheros distintos, sin dependencia
- [Story] mapea cada tarea a su historia para trazabilidad
- US1 y US2 comparten prioridad P1 porque el spec las prioriza igual, no
  porque sean independientes entre sí — ver la nota de dependencia real
  en cada fase
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre el homelab (FR-012) — es una restricción del propio
  feature, no algo que quede pendiente de implementar
- Confirmar el formato de la respuesta de DeepSeek en el prompt real
  antes de dar T017 por cerrada — la validación FR-007 depende de que el
  modelo de verdad devuelva JSON parseable, no solo de que el código lo
  espere
- T023 y T031 son incorporaciones de la revisión `/speckit-analyze`
  (2026-08-10, hallazgos E2 y E1) — antes de esa revisión, SC-001 y
  SC-002/FR-011 solo tenían verificación manual (T032/T030); ahora tienen
  además una prueba automatizada de su parte determinista
