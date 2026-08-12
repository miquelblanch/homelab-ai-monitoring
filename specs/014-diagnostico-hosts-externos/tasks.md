# Tasks: Generalizar el Diagnóstico a los Hosts Externos

**Input**: Design documents from `/specs/014-diagnostico-hosts-externos/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007-013) —
verificación de lógica pura contra datos simulados (`beszel_hosts.json`
de prueba, filas de `system_stats` simuladas), sin tocar Docker real
ni DeepSeek, salvo en las tareas de validación manual explícitas de
Polish.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo. Sin cambios en
`src/diagnostico/store.py`, `src/diagnostico/gasto.py` ni
`src/diagnostico/_homelab_bridge.py` — ninguna tarea los toca.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: el molde de snapshot vacío que las dos historias
necesitan — mismo patrón que el Foundational de 009-013.

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el séptimo valor real de
  `origen` (`"host_externo"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`/`"inventario"`)
  — sin cambio de esquema ni de campos, solo el docstring
  (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_host_externo_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más
  `host_externo_actual`/`host_externo_stats` a `null`, mismo patrón
  que `_snapshot_inventario_vacio()` de 013 (data-model.md)

**Checkpoint**: el molde de snapshot está listo para que cualquier
historia lo use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo el estado actual de un host externo (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquiera de
los 2 hosts físicos externos que Beszel vigila, leyendo el estado ya
calculado, con el mismo rigor que ya tiene un contenedor, un disco, un
check de HA, un backup, un relay o una brecha de inventario (spec.md
FR-001 a FR-007).

**Independent Test**: `congelar --host-externo-vivo NOMBRE` +
`diagnosticar` contra un host sano concluye `no_diagnosticable` sin
inventar una causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [P] [US1] En `src/diagnostico/evidencia.py`: constante
  `HOSTS_EXTERNOS` (`{"Host de Uptime Kuma": "UptimeKuma", "Host de
  AdGuard Home (DNS primario)": "AdGuardHome"}`, mismos literales que
  `app.py::EXTERNAL_HOSTS`/`beszel_hosts_monitor.py::HOSTS`, fuera de
  este repo) + `BESZEL_HOSTS_JSON`/`BESZEL_HOSTS_HEARTBEAT`
  (configurables) + `BESZEL_HOSTS_MAX_AGE_S = 900` (mismo valor exacto
  que `app.py`) + implementar `_host_externo_actual(nombre)` — lee
  `beszel_hosts.json` + el latido, aplica la misma política de
  frescura de las dos edades a la vez, devuelve
  `{nombre, beszel_name, status, raw_status, data_age_s, hb_age_s}`
  con `status` ∈ `{"arriba","caido","sin_evidencia"}`, `None` si
  `nombre` no está en `HOSTS_EXTERNOS` (research.md §2/§3)
- [X] T004 [US1] Implementar `congelar_host_externo_vivo(conn, nombre)`
  en `src/diagnostico/evidencia.py` — resuelve el estado (T003); arma
  el snapshot (T002) con `host_externo_actual=<resultado o None>`;
  `componente=nombre`, `es_critico=False` siempre, `origen=
  "host_externo"`, `en_vivo=True`, `restart_history_id=None`
  (data-model.md) — depende de T002, T003
- [X] T005 [US1] Conectar el flag `--host-externo-vivo NOMBRE` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — `NOMBRE` puede tener espacios, entrecomillado igual que
  `--relay-vivo`/`--inventario-vivo` (contracts/cli.md) — depende de
  T004
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o un host físico externo
  que Beszel ya vigila" a la lista ya existente; **y** añadir la
  cláusula nueva FR-006a (aplicable cuando
  `snapshot["host_externo_stats"]` no es `null`): el modelo NUNCA debe
  presentar `total_muestras == 0` como prueba de que el host estaba
  caído, debe considerar otras causas posibles antes de concluir
  (research.md §8) — independiente de T003-T005
- [X] T007 [P] [US1] Autocomprobación `tests/selftest/test_evidencia.py`
  — `_host_externo_actual()` contra un `beszel_hosts.json`/latido de
  prueba: caso fresco con host "arriba", caso fresco con host "caido",
  caso con dato o latido caducado (`"sin_evidencia"`), caso nombre
  inexistente (`None`); `congelar_host_externo_vivo()` arma el
  snapshot correctamente en los cuatro casos
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "host externo", sigue sin incluir
  la cláusula de crítico (`es_critico=False` siempre); la cláusula
  FR-006a aparece solo cuando `host_externo_stats` está poblado (no
  cuando `host_externo_actual` lo está); **y** (mismo hallazgo
  recurrente que motivó C1 en 009-012, corregido desde el diseño en
  013 y aquí también) `test_parsear_respuesta_host_externo_con_varias_hipotesis`:
  una respuesta simulada con `len(hipotesis) > 1` se acepta
  correctamente (SC-002)

**Checkpoint**: Miquel puede diagnosticar en vivo cualquiera de los 2
hosts externos con el mismo rigor que los demás orígenes — User Story
1 completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un momento pasado de un host externo, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar un momento pasado concreto y
diagnosticar si un host externo seguía reportando datos de rendimiento
en una ventana alrededor de ese momento, con la misma garantía de
reproducibilidad que los demás orígenes, incluida la avería real ya
documentada del 2026-07-30 al 2026-08-07 (spec.md FR-001, FR-002,
FR-006a; SC-001, SC-005).

**Independent Test**: `congelar --host-externo-historico` dos veces
sobre el mismo `NOMBRE@MOMENTO_ISO` y comprobar que `diagnosticar`
produce el mismo `conclusion_tipo` las dos veces — quickstart.md
Escenario 5.

### Implementación para User Story 2

- [X] T009 [US2] Implementar `_a_utc_madrid(momento)` en
  `src/diagnostico/evidencia.py` — interpreta `momento` (naive) como
  hora de `zoneinfo.ZoneInfo("Europe/Madrid")` y lo convierte a UTC,
  formateado como espera `system_stats.created` — primera conversión
  de huso horario de este motor (research.md §4) — independiente de
  T003-T008
- [X] T010 [US2] Implementar `_consultar_beszel_hub(beszel_name,
  inicio_utc, fin_utc)` en `src/diagnostico/evidencia.py` + constante
  `BESZEL_HUB_VOLUME = "beszel_hub_data"` — ejecuta `docker run --rm
  -v beszel_hub_data:/data python:3.11-alpine python3 -c "..."` con
  `beszel_name`/`inicio_utc`/`fin_utc` pasados por `sys.argv`, nunca
  interpolados en el texto del script; la consulta SQL usa `?`
  parametrizado (`SELECT created, type FROM system_stats WHERE system
  = (SELECT id FROM systems WHERE name = ?) AND created BETWEEN ? AND
  ? ORDER BY created`); `None` si Docker no está disponible o el
  proceso falla, nunca lanza (research.md §7) — independiente de
  T003-T009 salvo compartir fichero
- [X] T011 [US2] Implementar `_resumen_system_stats(filas)` en
  `src/diagnostico/evidencia.py` — reduce la lista de `(created,
  type)` a `{total_muestras, primera, ultima, por_tipo}`, `{0, None,
  None, {}}` si `filas` está vacía — nunca un booleano "caído"
  (research.md §5) — independiente de T003-T010
- [X] T012 [US2] Implementar `congelar_host_externo_historico(conn,
  nombre, momento)` en `src/diagnostico/evidencia.py` + constante
  `VENTANA_HOST_EXTERNO_MINUTOS = 1440` — resuelve `beszel_name` de
  `HOSTS_EXTERNOS` (T003, `None` si `nombre` no está ahí — en ese caso
  `host_externo_stats=None` directamente, sin llamar a T010); si
  `beszel_name` se resuelve, convierte la ventana `momento ± 1440min`
  a UTC (T009) y consulta el hub (T010) — **si T010 devuelve `None`
  (consulta fallida), `host_externo_stats=None`; si devuelve una lista
  (aunque vacía), `host_externo_stats=_resumen_system_stats(lista)`
  (T011)** — nunca pasar `None` a T011 (research.md §10, hallazgo real
  de `/speckit-analyze`, 2026-08-12); arma el snapshot (T002);
  `componente=nombre` (**nunca**
  `nombre@momento_iso` — research.md §2, mismo patrón que
  `check_id`/`label` de HA/discos); `ventana_inicio`/`ventana_fin` =
  `momento ± 1440min` en hora local; `en_vivo=False` — depende de
  T002, T003, T009, T010, T011
- [X] T013 [US2] Conectar el flag `--host-externo-historico
  "NOMBRE@MOMENTO_ISO"` en `src/diagnostico/cli.py` — `partition("@")`
  igual que `--disco-historico`/`--ha-historico`, mismo orden
  `identificador@localizador-temporal` (research.md §2/§9;
  contracts/cli.md) — depende de T012
- [X] T014 [P] [US2] Autocomprobación `tests/selftest/test_evidencia.py`
  (ampliar T007) — `_a_utc_madrid()` con un caso de invierno (CET,
  UTC+1) y uno de verano (CEST, UTC+2); `_resumen_system_stats()` con
  filas de varios tipos y con lista vacía;
  `congelar_host_externo_historico()` (con `_consultar_beszel_hub`
  simulado vía `patch.object`) reproducible, con `componente` igual al
  nombre pedido; **distinguiendo los tres casos reales** (hallazgo de
  `/speckit-analyze`, research.md §10): consulta simulada devolviendo
  `[]` → `host_externo_stats.total_muestras=0` (evidencia real);
  consulta simulada devolviendo `None` (fallo) →
  `host_externo_stats=None`, sin lanzar `TypeError`; nombre fuera de
  `HOSTS_EXTERNOS` → `host_externo_stats=None` sin llegar a llamar a
  `_consultar_beszel_hub`
- [X] T015 [P] [US2] Autocomprobación `tests/selftest/test_deepseek.py`
  (ampliar T008) — prueba de integración de
  `deepseek.diagnosticar_episodio()` con `origen="host_externo"` y
  `host_externo_stats.total_muestras=0`: confirma que ningún
  tratamiento especial de otro origen (relay F1, HA) se dispara por
  error, y que una respuesta simulada que SÍ respeta FR-006a (describe
  ausencia de datos, no afirma "caído confirmado") se acepta
  normalmente — mismo patrón que T014 de 013

**Checkpoint**: las dos historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido (FR-007,
`gasto.py` sin cambios) protegiendo también a los hosts externos.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T016 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir hosts externos a la lista de
  orígenes soportados y referenciar
  `specs/014-diagnostico-hosts-externos/`; dejar solo el hub de Beszel
  y agentes en la lista de "orígenes que siguen fuera de alcance"
- [X] T017 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (sin migración de esquema; depende de que T001-T015 estén
  desplegadas)
- [X] T018 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra los 2 hosts reales sanos —
  SC-004 (depende de US1)
- [X] T019 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — host inexistente, evidencia vacía
  sin lanzar (depende de US1)
- [X] T020 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) contra los 2 hosts reales dentro de
  la avería real conocida (2026-07-30 a 2026-08-07) — SC-005, la
  garantía central de este feature (primera línea base con causa raíz
  ya documentada de forma independiente); confirmar que la
  `conclusion_texto` real respeta FR-006a; validar **antes** que el
  resto de escenarios de diferido, mismo criterio que 011/012/013
  dieron prioridad a su propia garantía central (depende de US2)
- [X] T021 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido —
  SC-001 (depende de US2)
- [X] T022 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de
  host externo cuenta contra el mismo límite diario que los demás
  orígenes — FR-007 (depende de US1 o US2)
- [X] T023 [P] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — momento sin ningún dato, fuera de
  cualquier avería conocida, `componente` refleja el nombre pedido
  (depende de US2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real; T003
  define `HOSTS_EXTERNOS`, que también reutiliza US2 (T012)
- **US2 (Phase 3)**: depende de la Fase 1 y de T003 (US1, para
  `HOSTS_EXTERNOS`) — T009/T010/T011 son independientes entre sí y del
  resto de US1 hasta que T012 las una
- **Polish (Phase 4)**: T016 es independiente de todo lo demás; T017
  depende de que US1/US2 estén desplegadas; T020 es la validación más
  importante de Polish — confirma la garantía central del feature
  contra una avería real con causa raíz ya conocida, no simulada

### Parallel Opportunities

- T001, T002 (Foundational) son paralelas entre sí
- T006 (US1, prompt) es paralelo a T003-T005
- T007, T008 (autocomprobaciones US1) son paralelas entre sí
- T009, T010, T011 (US2) son paralelas entre sí hasta que T012 las una
- T014, T015 (autocomprobaciones US2) son paralelas entre sí, e
  independientes de T007/T008 salvo por compartir fichero
- T016-T023 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende

---

## Parallel Example: User Story 2

```bash
# T009 (huso horario), T010 (consulta al hub) y T011 (resumen) pueden ir en paralelo:
Task: "Implementar _a_utc_madrid() en src/diagnostico/evidencia.py"
Task: "Implementar _consultar_beszel_hub() en src/diagnostico/evidencia.py"
Task: "Implementar _resumen_system_stats() en src/diagnostico/evidencia.py"
```

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (molde de snapshot)
2. Completar Fase 2: US1 (diagnóstico de host externo en vivo)
3. **PARAR Y VALIDAR**: Escenario 2 de `quickstart.md` contra los 2
   hosts reales
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar un host externo caído con el mismo rigor que los
   demás orígenes

### Entrega incremental

1. Foundational → molde de snapshot listo, sin romper 007-013
2. US1 → diagnóstico de host externo en vivo, demo posible (MVP!)
3. US2 → diagnóstico en diferido, reproducible, con FR-006a en el
   prompt — **y la validación contra una línea base real con causa
   raíz ya conocida de forma independiente**, la más fuerte de todo el
   proyecto (T020, la avería del 30 de julio al 7 de agosto)
4. Polish → validación manual completa de los 7 escenarios,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre ningún host externo ni sobre Beszel (FR-008)
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py` —
  sin migración de esquema, el gasto ya es agnóstico al origen, y este
  feature no puentea ningún script externo (implementa su propia
  consulta a Docker en `evidencia.py`)
- Ninguna tarea diagnostica el propio hub de Beszel (FR-010) — es el
  origen #8, con su propia investigación pendiente
- **T009/T010/T011 son las primeras funciones de este motor que
  ejecutan `docker run` (no solo `docker inspect`/`logs`/`ps`) y que
  convierten entre husos horarios** — dos piezas de infraestructura
  genuinamente nuevas, cada una con su propia tarea dedicada en vez de
  mezclarse con patrones ya existentes que no encajan del todo
  (research.md §4/§7)
- **T008/T015 incluyen desde el principio la prueba de SC-002 y la
  validación de FR-006a**, sin esperar a que `/speckit-analyze` las
  encuentre — mismo criterio ya aplicado en 013 tras el patrón
  recurrente C1 de 009-012
