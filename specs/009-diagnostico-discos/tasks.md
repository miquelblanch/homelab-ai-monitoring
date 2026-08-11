# Tasks: Generalizar el Diagnóstico a Discos

**Input**: Design documents from `/specs/009-diagnostico-discos/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (feature 007) —
verificación de lógica pura sin tocar DeepSeek/`homelab.db` real, salvo
en las tareas de validación manual explícitas.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md,
Project Structure) — ningún paquete nuevo, ningún fichero nuevo en
`homelab-ai-monitoring` fuera de `tests/selftest/`.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: el modelo y el esquema generalizados que las dos historias
necesitan

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase.
**Nota de riesgo**: T002 migra `diagnostico.db` de producción (14
episodios reales ya escritos por 007) — ejecutar contra una copia antes
de tocar el fichero real, y confirmar con T014 antes de dar la
migración por buena.

- [X] T001 [P] Generalizar `Episodio` en `src/diagnostico/model.py` —
  renombrar el campo `contenedor` a `componente`, añadir `origen: str`
  (valor `"contenedor"` o `"disco"`, sin validación estricta en el
  dataclass — se valida por construcción en `evidencia.py`)
  (data-model.md; fichero independiente de T002)
- [X] T002 Implementar la migración idempotente en
  `src/diagnostico/store.py` — dentro de `connect()`, tras
  `_SCHEMA`, comprobar con `PRAGMA table_info(episodios)` si la columna
  `origen` ya existe; si no, ejecutar `ALTER TABLE episodios RENAME
  COLUMN contenedor TO componente` seguido de `ALTER TABLE episodios
  ADD COLUMN origen TEXT NOT NULL DEFAULT 'contenedor'` (research.md
  §1). Actualizar `insert_episodio()`/`_episodio_from_row()` para leer
  y escribir `componente`/`origen` (depende de T001 para los nombres
  de campo del dataclass, fichero distinto). También se actualizó
  `_SCHEMA` para que una base **nueva** cree `componente`/`origen`
  directamente (la migración solo actúa sobre bases ya existentes de
  antes de 009), y se corrigieron 5 sitios en `tests/selftest/*.py`
  que construían `Episodio(contenedor=...)` con el nombre antiguo.

**Checkpoint**: el esquema y el modelo generalizados están listos y son
seguros sobre los datos reales ya existentes.

---

## Phase 2: User Story 1 - Diagnosticar un episodio de disco en vivo (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquiera de
los tres discos reales, con el mismo rigor que ya tiene un contenedor
(spec.md FR-001 a FR-006, FR-008, SC-002/SC-004).

**Independent Test**: `congelar --disco-vivo FastData` +
`diagnosticar` contra un disco sano concluye `no_diagnosticable` sin
inventar una causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [P] [US1] Implementar `disk_metrics_recientes(label,
  limite=12)` en `src/diagnostico/evidencia.py` — últimas muestras de
  `disk_metrics` para ese disco, mismo patrón que
  `container_metrics_recientes()` (research.md §3; fichero ya tocado
  por T004-T005, pero función independiente — sin dependencia real de
  ninguna otra tarea de esta fase)
- [X] T004 [US1] Implementar `congelar_disco_vivo(conn, label)` en
  `src/diagnostico/evidencia.py` — arma el snapshot con la forma de
  `data-model.md` (`disco`, `disk_metrics`, resto de claves heredadas a
  `null`), `es_critico=False` siempre (research.md §4), `origen="disco"`,
  `restart_history_id=None` (depende de T001, T002, T003, mismo
  fichero que T003)
- [X] T005 [US1] Conectar el flag `--disco-vivo LABEL` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — actualizar también los `print()` de `_run_congelar`/
  `_run_mostrar` que hoy referencian `episodio.contenedor` para usar
  `episodio.componente` (contracts/cli.md; depende de T004)
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — cambiar solo la frase de encuadre
  inicial para cubrir contenedores y discos, sin tocar la estructura
  del JSON pedido ni la aclaración de "confirmada" ya corregida
  (research.md §5; independiente de T003-T005)
- [X] T007 [P] [US1] Autocomprobación
  `tests/selftest/test_evidencia.py` — `congelar_disco_vivo()` contra
  una base `homelab.db` de prueba con filas de `disk_metrics`, forma
  del snapshot, `es_critico=False`, `origen="disco"` fijado
  correctamente
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado sigue incluyendo la cláusula "sin acción"
  cuando `es_critico=True` (caso de contenedor crítico, regresión) y no
  la incluye para un episodio de disco; **y** (hallazgo U1 de
  `/speckit-analyze`, 2026-08-11, SC-002) que `parsear_respuesta()`
  acepta sin problema una respuesta simulada de un episodio de disco
  con varias hipótesis — `len(hipotesis) > 1` — mismo patrón que T021
  de 007 ya comprobaba para contenedores

**Checkpoint**: Miquel puede diagnosticar cualquiera de los tres discos
reales en vivo, con el mismo rigor que un contenedor — User Story 1
completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un episodio de disco en diferido, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar un momento pasado de un disco y
diagnosticarlo más tarde, con la misma garantía de reproducibilidad que
ya tienen los contenedores (spec.md FR-001, FR-002; SC-001).

**Independent Test**: diagnosticar dos veces el mismo momento pasado de
un disco produce el mismo `conclusion_tipo` las dos veces —
quickstart.md Escenario 3.

### Implementación para User Story 2

- [X] T009 [US2] Implementar `disk_metrics_window(label, inicio, fin)`
  en `src/diagnostico/evidencia.py` — ventana `[inicio, fin]` sobre
  `disk_metrics` para ese disco, mismo patrón que
  `container_metrics_window()` (research.md §3; depende de Foundational,
  independiente de T003-T008)
- [X] T010 [US2] Implementar `congelar_disco_historico(conn,
  label, momento)` en `src/diagnostico/evidencia.py` — parsea
  `"LABEL@MOMENTO_ISO"` (contracts/cli.md), ventana ±30 min alrededor
  de `momento` (`VENTANA_METRICAS_MINUTOS`, ya existente), mismo resto
  de campos que T004 pero `en_vivo=False` (depende de T009, mismo
  fichero)
- [X] T011 [US2] Conectar el flag `--disco-historico
  "LABEL@MOMENTO_ISO"` en `src/diagnostico/cli.py` — parsea el
  argumento con `str.partition("@")` (depende de T010, mismo patrón de
  conexión que T005)
- [X] T012 [P] [US2] Autocomprobación
  `tests/selftest/test_evidencia.py` (ampliar T007) —
  `congelar_disco_historico()` contra la misma base de prueba, y que
  dos congelados del mismo `"LABEL@MOMENTO"` producen ventanas
  idénticas (base de la reproducibilidad, SC-001)

**Checkpoint**: las dos historias de usuario funcionan juntas — el
feature completo según el spec, con el mismo cortacircuitos de gasto
compartido (FR-007, `gasto.py` sin cambios) protegiendo a ambos
orígenes.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T013 [P] Autocomprobación `tests/selftest/test_store.py` — la
  migración de esquema es idempotente (`connect()`/`init_db()` dos
  veces no falla) y, contra una base de prueba con una fila `episodios`
  ya escrita con el esquema antiguo (`contenedor`, sin `origen`),
  confirma que tras migrar esa fila queda con `origen='contenedor'` y
  el mismo valor de `componente` que tenía antes (research.md §1)
- [X] T014 Validar la migración contra una **copia** de
  `diagnostico.db` de producción (nunca el fichero real directamente)
  — confirmar que los 14 episodios ya existentes se leen igual que
  antes (`mostrar` de cada uno, comparar con la salida ya conocida) antes
  de aplicar la migración al fichero real (quickstart.md Escenario 1;
  depende de T002). **Validado el 2026-08-11**: copia real de
  `diagnostico.db` (9 episodios reales, no 14 — el número exacto de
  filas variaba desde que se escribió la tarea), migrada y verificada:
  mismos `componente`, `origen='contenedor'` correcto, 17 diagnósticos
  y 26 hipótesis intactos, `snapshot_evidencia` sin alterar.
- [X] T015 Aplicar la migración al `diagnostico.db` real (primera
  operación real de `congelar --disco-vivo`/`--disco-historico`
  activará la migración automáticamente) y repetir el Escenario 1 de
  [quickstart.md](./quickstart.md) contra el fichero real (depende de
  T014). **Aplicada el 2026-08-11**: `mostrar 6` contra el fichero real
  reproduce el mismo contenido que antes de migrar; 9 episodios y 17
  diagnósticos preservados.
- [X] T016 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra los tres discos reales
  (FastData, Storage, Sistema) — SC-004. **Validado el 2026-08-11 con
  DeepSeek real** (episodios 15-17): los tres, sanos, concluyeron
  `no_diagnosticable` con 3-4 hipótesis contrastadas cada uno (también
  cierra SC-002 con datos reales, no solo simulados).
- [X] T017 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido,
  SC-001. **Validado el 2026-08-11 con DeepSeek real** (episodio 18,
  FastData@hace 2h, diagnosticado dos veces): mismo `conclusion_tipo`
  (`no_diagnosticable`) en los dos intentos.
- [X] T018 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de
  disco cuenta contra el mismo límite diario que uno de contenedor
  (FR-007). **Validado el 2026-08-11**: `gasto_diario` de hoy
  (0,01297745€) es exactamente la suma del coste real de 1 diagnóstico
  de contenedor (0,00347791€, de la sesión anterior) + 5 de disco
  (0,00949954€) — un único acumulado, confirmado por consulta directa.
- [X] T019 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — ya no es "solo contenedores"; añadir
  discos y referenciar también `specs/009-diagnostico-discos/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real
- **US2 (Phase 3)**: depende de la Fase 1; T009/T010 son independientes
  de todo lo de US1 salvo compartir `evidencia.py` como fichero
- **Polish (Phase 4)**: T013/T014/T015 dependen de T002 (la migración);
  T016-T018 dependen de que US1/US2 estén completas; T019 es
  independiente de todo lo demás

### Parallel Opportunities

- T002 depende de T001 (usa los nombres de campo que T001 define) — no
  son paralelas pese a estar en ficheros distintos (corregido
  2026-08-11, hallazgo I1 de `/speckit-analyze`: T002 llevaba `[P]`
  por error)
- T003 (US1) es paralelo al resto de la Fase 2 hasta que T004 lo use
- T007, T008 (autocomprobaciones US1) son paralelas entre sí
- T009-T010 (US2) son independientes de T003-T008 (US1) salvo por
  compartir `evidencia.py`
- T016, T017, T018, T019 (Polish) son paralelas entre sí

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (modelo + migración)
2. Completar Fase 2: US1 (diagnóstico de disco en vivo)
3. **PARAR Y VALIDAR**: T014 (migración contra copia) antes de tocar el
   `diagnostico.db` real; después, Escenario 2 de `quickstart.md`
   contra los tres discos reales
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar un disco con el mismo rigor que un contenedor

### Entrega incremental

1. Foundational → modelo y esquema generalizados, sin romper 007
2. US1 → diagnóstico de disco en vivo, demo posible
3. US2 → diagnóstico de disco en diferido, reproducible
4. Polish → migración aplicada de verdad, validación completa,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre ningún disco (FR-008) — restricción del propio
  feature, no algo pendiente de implementar
- `gasto.py` no aparece en ninguna tarea — ya es agnóstico al origen
  del episodio, confirmado en `research.md`/`plan.md`, sin cambios que
  hacer
