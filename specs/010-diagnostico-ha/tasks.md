# Tasks: Generalizar el Diagnóstico a Home Assistant

**Input**: Design documents from `/specs/010-diagnostico-ha/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007/009) —
verificación de lógica pura simulando `ha_monitor.CHECKS`/
`ha_get_detallado`, sin tocar la API de HA/Docker/DeepSeek reales, salvo
en las tareas de validación manual explícitas de Polish.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2 / US3, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo, ningún fichero nuevo en
`homelab-ai-monitoring` fuera de `tests/selftest/`. Sin cambios en
`src/diagnostico/store.py` ni `src/diagnostico/gasto.py` (research.md
§1; plan.md) — ninguna tarea los toca.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: resolución de un `check_id` de HA y el bloqueo de la
cerradura (FR-010) que las tres historias necesitan.

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase — en
particular, el bloqueo de cerradura de T002 es lo primero que debe
comprobar cualquier `congelar_ha_*`, antes de intentar resolver el
check contra `ha_monitor.CHECKS`.

- [X] T001 [P] Añadir `ha_checks()` a `src/diagnostico/_homelab_bridge.py`
  — expone `ha_monitor.CHECKS` tal cual (nunca lo copia), mismo
  contrato "nunca lanza, `[]` si `ha_monitor.py` no está disponible" ya
  usado por `docker_critical()`/`docker_never_restart()` del mismo
  fichero (research.md §3; fichero independiente del resto de esta
  fase)
- [X] T002 Implementar `ha_check_by_id(check_id)` en
  `src/diagnostico/evidencia.py` (usa `bridge.ha_checks()`, `None` si
  no existe) y la constante `CHECKS_HA_EXCLUIDOS_CERRADURA =
  {"cerradura_up", "bateria_cerradura", "bateria_critica_cerradura"}`
  (research.md §2/§7, FR-010) — depende de T001 (mismo fichero,
  requiere que `ha_checks()` ya exista)
- [X] T003 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el tercer valor real de
  `origen` (`"ha"`, además de `"contenedor"`/`"disco"`) — sin cambio de
  esquema ni de campos, solo el docstring (data-model.md; research.md
  §1; fichero independiente de T001/T002)

**Checkpoint**: la resolución de checks de HA y el bloqueo de cerradura
están listos para que cualquier historia los use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo un episodio de entidad de Home Assistant (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquier check
de entidad de `ha_monitor.py` (batería, disponibilidad, estado), con el
mismo rigor que ya tiene un contenedor o un disco (spec.md FR-001 a
FR-007, FR-010).

**Independent Test**: `congelar --ha-vivo z2m_bridge` (o cualquier
check `entity_*` sano) + `diagnosticar` concluye `no_diagnosticable`
sin inventar una causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T004 [P] [US1] Añadir `ha_history()` a
  `src/diagnostico/_homelab_bridge.py` — envuelve
  `ha_monitor.ha_get_detallado(f"/api/history/period/{inicio_iso}?filter_entity_id={entity}&end_time={fin_iso}")`,
  `None` si `ha_monitor.py` no está disponible o la llamada falla
  (research.md §4; mismo fichero que T001, función independiente)
- [X] T005 [US1] Implementar `ha_history_window(entity, inicio, fin)`
  en `src/diagnostico/evidencia.py` (usa `bridge.ha_history()`) y la
  constante `VENTANA_HA_ENTIDAD_HORAS = 12` (research.md §6) — depende
  de T004
- [X] T006 [US1] Implementar `congelar_ha_vivo(conn, check_id)` en
  `src/diagnostico/evidencia.py` para los cuatro tipos `entity_state`/
  `entity_available`/`entity_value_below`/`entity_age_below` —
  comprueba primero `CHECKS_HA_EXCLUIDOS_CERRADURA` (T002, lanza
  `ValueError` si coincide, FR-010); resuelve el check con
  `ha_check_by_id()` (T002, `None` si no existe → todos los campos de
  evidencia de HA quedan en `null`, sin error, spec.md Edge Cases);
  para un check de entidad reconocido, ventana `[ahora -
  VENTANA_HA_ENTIDAD_HORAS, ahora]` vía T005; snapshot con `ha_check`/
  `ha_history` poblados y el resto de claves heredadas (`disco`,
  `restart_history`, `container_metrics*`, `disk_metrics`,
  `docker_inspect`, `docker_logs_tail`, `ha_recorder_corrupt_files`) a
  `null` (data-model.md); `es_critico=False` siempre, `origen="ha"`,
  `restart_history_id=None` — depende de T002, T005
- [X] T007 [US1] Conectar el flag `--ha-vivo CHECK_ID` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — el `ValueError` de la exclusión de cerradura debe
  imprimir un mensaje claro por `stderr` y terminar con código de
  salida 1 (contracts/cli.md; depende de T006)
- [X] T008 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — cambiar solo la frase de encuadre
  inicial para cubrir también HA ("...puede ser un contenedor Docker
  caído, un disco con uso alto, o un check de Home Assistant — una
  entidad con batería baja o estado inesperado, su recorder corrupto, o
  su API sin responder"), sin tocar la estructura del JSON pedido ni la
  aclaración de "confirmada" ya corregida (research.md §8; independiente
  de T004-T007)
- [X] T009 [P] [US1] Autocomprobación
  `tests/selftest/test_evidencia.py` — `congelar_ha_vivo()` contra un
  `ha_monitor.CHECKS`/`ha_get_detallado` simulados, para los cuatro
  subtipos `entity_*`, forma del snapshot, `es_critico=False`,
  `origen="ha"`; el bloqueo de cerradura lanza `ValueError` para los 3
  checks excluidos; un `check_id` inexistente congela igual con
  evidencia `null`, sin lanzar
- [X] T010 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado sigue incluyendo la cláusula "sin acción"
  solo cuando `es_critico=True` (caso de contenedor crítico, regresión)
  y nunca para un episodio de HA (`es_critico=False` siempre); la
  evidencia de HA (`ha_check`/`ha_history`) aparece correctamente en el
  JSON del prompt

**Checkpoint**: Miquel puede diagnosticar en vivo cualquier check de
entidad de HA con el mismo rigor que un contenedor o un disco — User
Story 1 completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar en vivo un episodio de recorder de HA corrupto (Priority: P2)

**Goal**: Miquel puede diagnosticar en vivo el check del recorder
corrupto y el check `ha_api` (sin entidad asociada — gap encontrado en
`/speckit-clarify`, Clarifications 2026-08-12), con la misma garantía
de nunca inventar una causa sin evidencia (spec.md FR-003).

**Independent Test**: simular una corrupción
(`docker exec homeassistant sh -c 'touch /recorder/x.corrupt.1'`),
`congelar --ha-vivo ha_recorder_corrupto` + `diagnosticar` concluye
`causa_probable` citando el fichero — quickstart.md Escenario 4.
`congelar --ha-vivo ha_api` sobre la API sana concluye
`no_diagnosticable` — quickstart.md Escenario 3.

### Implementación para User Story 2

- [X] T011 [P] [US2] Añadir `ha_recorder_corrupt_files(contenedor,
  ruta)` a `src/diagnostico/_homelab_bridge.py` — envuelve
  `ha_monitor._recorder_corrupt_files()` (función privada, reutilizada
  igual que `inventory/_homelab_bridge.py` ya reutiliza `STATE_FILE`,
  research.md §4), `[]` si `ha_monitor.py` no está disponible (mismo
  fichero que T001/T004, función independiente)
- [X] T012 [US2] Extender `congelar_ha_vivo(conn, check_id)` en
  `src/diagnostico/evidencia.py` (T006) con dos ramas nuevas: tipo
  `recorder_corrupto` → `ha_recorder_corrupt_files(check["contenedor"],
  check["ruta"])` (T011) + `docker_logs_tail("homeassistant")` (ya
  existente desde 007); tipo `api_ping` → solo
  `docker_logs_tail(_HA_API_CONTENEDOR)`, constante nueva
  `_HA_API_CONTENEDOR = "homeassistant"` (research.md §5, Clarificaciones
  2026-08-12) — depende de T006, T011
- [X] T013 [P] [US2] Autocomprobación
  `tests/selftest/test_evidencia.py` (ampliar T009) —
  `congelar_ha_vivo()` para `ha_recorder_corrupto` (con y sin ficheros
  simulados) y para `ha_api`; `ha_history` queda `null` en ambos casos,
  `docker_logs_tail`/`ha_recorder_corrupt_files` se pueblan
  correctamente según el tipo

**Checkpoint**: los tres tipos de check de HA se pueden diagnosticar en
vivo — `--ha-vivo` completo según contracts/cli.md.

---

## Phase 4: User Story 3 - Diagnosticar un episodio de HA en diferido, reproduciblemente (Priority: P3)

**Goal**: Miquel puede señalar un momento pasado de cualquiera de los
tres tipos de check de HA y diagnosticarlo más tarde, con la misma
garantía de reproducibilidad que ya tienen contenedores y discos
(spec.md FR-001, FR-002; SC-001).

**Independent Test**: `congelar --ha-historico` dos veces sobre el
mismo `"CHECK_ID@MOMENTO_ISO"` de un check de entidad y comprobar que
`diagnosticar` produce el mismo `conclusion_tipo` las dos veces —
quickstart.md Escenario 5.

### Implementación para User Story 3

- [X] T014 [US3] Implementar `congelar_ha_historico(conn, check_id,
  momento)` en `src/diagnostico/evidencia.py` — misma resolución de
  check y bloqueo de cerradura que T006 (T002); para checks de entidad,
  ventana `[momento - VENTANA_HA_ENTIDAD_HORAS, momento +
  VENTANA_HA_ENTIDAD_HORAS]` vía T005; para `recorder_corrupto`/
  `api_ping`, la misma evidencia de *estado actual* que T012 (ficheros/
  logs de ahora mismo), etiquetada con `ventana_inicio`/`ventana_fin`
  del `momento` pedido — limitación aceptada y documentada, no un bug
  (research.md §6); `en_vivo=False` — depende de T006, T012
- [X] T015 [US3] Conectar el flag `--ha-historico
  "CHECK_ID@MOMENTO_ISO"` en `src/diagnostico/cli.py` — parseo con
  `str.partition("@")`, mismo patrón que `--disco-historico`
  (contracts/cli.md; misma convención de hora local sin zona,
  research.md §9) — depende de T014
- [X] T016 [P] [US3] Autocomprobación
  `tests/selftest/test_evidencia.py` (ampliar T009/T013) —
  `congelar_ha_historico()` para los tres tipos de check; dos
  congelados del mismo `"CHECK_ID@MOMENTO"` para un check de entidad
  producen ventanas idénticas (base de SC-001); para
  `recorder_corrupto`/`api_ping`, el snapshot usa el estado actual bajo
  la ventana etiquetada (research.md §6)

**Checkpoint**: las tres historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido (FR-007,
`gasto.py` sin cambios) protegiendo también a HA.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T017 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir Home Assistant a la lista de
  orígenes soportados y referenciar `specs/010-diagnostico-ha/`; quitar
  HA de la lista de "orígenes que siguen fuera de alcance"
- [X] T018 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (sin migración de esquema esta vez, research.md §1; depende de
  que T001-T016 estén desplegadas). **Validado el 2026-08-12**: `mostrar
  6` (episodio real de 007) se lee exactamente igual que antes de este
  feature.
- [X] T019 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra al menos un check de cada uno
  de los cuatro subtipos `entity_*` reales y sanos — SC-004 (depende de
  US1). **Validado el 2026-08-12 con DeepSeek real** (episodios 19-22,
  30): `z2m_bridge` (`entity_state`), `shelly_riego`
  (`entity_available`), `sal_nivel` (`entity_value_below`),
  `ha_backup_reciente` (`entity_age_below`) — los cuatro concluyeron
  `no_diagnosticable` con evidencia real (2-4 hipótesis cada uno).
  Encontró y corrigió tres problemas reales del propio motor durante la
  validación: `parsear_respuesta()` perdía respuestas completas
  atrapadas en `reasoning_content` (research.md §10, afecta también a
  007/009); `sal_nivel` reventaba el prompt a 280K tokens sin límite de
  historial (research.md §13); el prompt no le decía al modelo si el
  check estaba realmente sano, lo que en `ha_backup_reciente` alargaba
  el razonamiento hasta agotar el presupuesto (resuelto junto con T020,
  research.md §12).
- [X] T020 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — `ha_api` sano, cierra el gap de
  Clarifications 2026-08-12 (depende de US2). **Validado el 2026-08-12
  con DeepSeek real** (episodios 24-27): la primera validación reveló
  un hallazgo real — `docker_logs_tail("homeassistant")` devolvía `""`
  porque ese contenedor escribe en `stderr`, no en `stdout`
  (research.md §11), y sin logs reales el check sano aun así concluía
  `causa_probable` citando ruido no relacionado de otras integraciones
  (violación de SC-004). Corregido con `ha_check_status` (research.md
  §12): tras el arreglo, dos intentos consecutivos concluyeron
  `no_diagnosticable`, citando explícitamente que los errores de log
  "son ajenos a este check".
- [X] T021 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — recorder corrupto simulado,
  `causa_probable` con evidencia real — SC-002 (depende de US2).
  **Validado el 2026-08-12 con DeepSeek real** (episodios 28-29,
  corrupción simulada con `docker exec homeassistant touch/rm` y
  limpiada de inmediato): sano → `no_diagnosticable` explícito citando
  `ha_check_status.ok=true` (cierra también el hallazgo C1 de
  `/speckit-analyze`, sin cobertura de validación real del caso sano);
  con un fichero `*.corrupt.*` simulado → `causa_probable` correcto,
  citando el fichero y `ha_check_status.motivo="corrupcion"`.
- [X] T022 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido de un
  check de entidad — SC-001 (depende de US3). **Validado el 2026-08-12
  con DeepSeek real** (episodio 30, `z2m_bridge@hace 2h`, diagnosticado
  dos veces): mismo `conclusion_tipo` (`no_diagnosticable`) en los dos
  intentos — el snapshot ya congelado nunca vuelve a tocar la API de HA.
- [X] T023 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de HA
  cuenta contra el mismo límite diario que contenedor/disco — FR-007
  (depende de US1 o US2). **Validado el 2026-08-12**: `gasto_diario` de
  hoy (0,236€) es exactamente la suma de los 35 diagnósticos de HA
  reales de la sesión — un único acumulado, confirmado por consulta
  directa, muy por debajo del límite de 5€/día.
- [X] T024 [P] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — `congelar --ha-vivo
  bateria_cerradura` se rechaza con error, ningún episodio creado —
  FR-010 (depende de Foundational, T002, **y de T007** — corregido tras
  hallazgo F1 de `/speckit-analyze`: la validación real usa el flag
  `--ha-vivo`, que no existe hasta T007). **Validado el 2026-08-12**:
  código de salida 1, mensaje explícito citando FR-010, sin traceback.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las tres
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real
- **US2 (Phase 3)**: depende de la Fase 1 y de T006 (US1) — extiende la
  misma función `congelar_ha_vivo` en vez de duplicarla
- **US3 (Phase 4)**: depende de T006 (US1) y T012 (US2) — extiende la
  misma pareja de resolución de check a un `congelar_ha_historico`
  nuevo
- **Polish (Phase 5)**: T017 es independiente de todo lo demás; T018
  depende de que las tres historias estén desplegadas; T019-T024
  dependen cada una de la historia que validan (ver arriba)

### Parallel Opportunities

- T001, T003 (Foundational) son paralelas entre sí; T002 depende de T001
  (mismo fichero, usa `ha_checks()`)
- T004 (US1) es paralelo a T001/T003 y al resto de la Fase 2 hasta que
  T005 lo use
- T009, T010 (autocomprobaciones US1) son paralelas entre sí
- T011 (US2) es paralelo al resto de su fase hasta que T012 lo use
- T013 (autocomprobación US2) es independiente de T009/T010 salvo por
  compartir fichero
- T016 (autocomprobación US3) es independiente de T009/T010/T013 salvo
  por compartir fichero
- T017-T024 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende (ver Phase Dependencies)

---

## Parallel Example: User Story 1

```bash
# T004 (bridge) puede ir en paralelo con T001/T003 (Foundational) y con T008 (prompt):
Task: "Añadir ha_history() a src/diagnostico/_homelab_bridge.py"
Task: "Generalizar _PROMPT_INSTRUCCIONES en src/diagnostico/deepseek.py"

# Autocomprobaciones de US1, en paralelo entre sí una vez T006/T007 estén listas:
Task: "Autocomprobación congelar_ha_vivo (entidad) en tests/selftest/test_evidencia.py"
Task: "Autocomprobación prompt generalizado en tests/selftest/test_deepseek.py"
```

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (resolución de check + bloqueo de
   cerradura)
2. Completar Fase 2: US1 (diagnóstico de entidad de HA en vivo)
3. **PARAR Y VALIDAR**: Escenario 2 de `quickstart.md` contra checks de
   entidad reales sanos (SC-004)
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar el tipo de check más numeroso de `ha_monitor.py` con el
   mismo rigor que un contenedor o un disco

### Entrega incremental

1. Foundational → resolución de check y exclusión de cerradura listas,
   sin romper 007/009
2. US1 → diagnóstico de entidad de HA en vivo, demo posible (MVP!)
3. US2 → recorder corrupto y `ha_api` en vivo — `--ha-vivo` completo
4. US3 → diagnóstico en diferido de los tres tipos, reproducible
5. Polish → validación manual completa de los 7 escenarios,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre HA ni sobre ningún dispositivo físico (FR-008) —
  restricción del propio feature, no algo pendiente de implementar
- Ninguna tarea toca `src/diagnostico/store.py` ni
  `src/diagnostico/gasto.py` — sin migración de esquema (research.md
  §1) y el gasto ya es agnóstico al origen del episodio, confirmado en
  007/009 y de nuevo en plan.md de este feature
- T012/T014 dejan escrita, no oculta, la limitación de research.md §6
  (`recorder_corrupto`/`ha_api` en modo histórico leen estado actual,
  no un registro verdaderamente pasado) — coherente con spec.md
  Assumptions, que ya la anticipa
