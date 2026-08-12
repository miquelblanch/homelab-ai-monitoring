# Tasks: Generalizar el Diagnóstico al Hub de Beszel

**Input**: Design documents from `/specs/015-diagnostico-hub-beszel/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007-014) —
verificación de lógica pura contra datos simulados, sin tocar Docker
real ni DeepSeek, salvo en las tareas de validación manual explícitas
de Polish.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo. Reutiliza tal cual de 014:
`BESZEL_HOSTS_JSON`, `BESZEL_HOSTS_MAX_AGE_S`, `BESZEL_HUB_VOLUME`,
`_docker_bin()`, `_a_utc_madrid()`, `_resumen_system_stats()` — ninguna
tarea las reimplementa. Sin cambios en `src/diagnostico/store.py`,
`src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py`.

---

## Phase 1: Foundational (Blocking Prerequisites)

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el octavo valor real de
  `origen` (`"hub_beszel"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`/`"inventario"`/`"host_externo"`)
  — sin cambio de esquema ni de campos, solo el docstring
  (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_hub_beszel_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más
  `hub_beszel_actual`/`hub_beszel_stats` a `null`, mismo patrón que
  `_snapshot_host_externo_vacio()` de 014 (data-model.md)

**Checkpoint**: el molde de snapshot está listo para que cualquier
historia lo use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo si el hub sigue vigilando algo de verdad (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo del hub de Beszel
— si todos los sistemas registrados dejaron de reportar a la vez, no
solo uno — con el mismo rigor que los demás orígenes (spec.md FR-001 a
FR-007).

**Independent Test**: `congelar --hub-beszel-vivo` + `diagnosticar`
contra el hub sano concluye `no_diagnosticable` sin inventar una
causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [US1] Implementar `_hub_beszel_actual()` en
  `src/diagnostico/evidencia.py` — lee `hub_systems` de
  `BESZEL_HOSTS_JSON` (constante ya definida en 014, no se duplica),
  calcula `age_s`/`stale` por sistema contra `BESZEL_HOSTS_MAX_AGE_S`
  (900s, misma constante exacta de 014), `sano = bool(systems) and not
  all(s["stale"] for s in systems)` — mismo cálculo exacto que
  `app.py::get_beszel_hub_status()` (research.md §3)
- [X] T004 [US1] Implementar `congelar_hub_beszel_vivo(conn)` en
  `src/diagnostico/evidencia.py` — **sin argumento** (research.md §2,
  mismo patrón que `congelar_backup_vivo()` de 011); arma el snapshot
  (T002) con `hub_beszel_actual=<resultado de T003>`;
  `componente=ahora.isoformat()`, `es_critico=False` siempre,
  `origen="hub_beszel"`, `en_vivo=True`, `restart_history_id=None`
  (data-model.md) — depende de T002, T003
- [X] T005 [US1] Conectar el flag `--hub-beszel-vivo` (booleano, sin
  metavar, mismo tipo que `--backup-vivo`) en `src/diagnostico/cli.py`
  (`congelar`, grupo mutuamente excluyente ya existente) —
  (contracts/cli.md) — depende de T004
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o el propio hub de
  Beszel, si deja de vigilar todos sus sistemas a la vez" a la lista
  ya existente; **y** añadir la cláusula nueva FR-006a propia
  (aplicable cuando `snapshot["hub_beszel_stats"]` no es `null`): el
  modelo NUNCA debe presentar una ausencia parcial (algunos sistemas
  sin muestras, otros con muestras) como si el hub entero estuviera
  caído, y tampoco debe tratar `todos_sin_muestras=true` como prueba
  concluyente sin considerar otras causas (research.md §8) —
  independiente de T003-T005
- [X] T007 [P] [US1] Autocomprobación `tests/selftest/test_evidencia.py`
  — `_hub_beszel_actual()` contra un `beszel_hosts.json` de prueba:
  todos los sistemas frescos (`sano=true`), uno caducado entre varios
  frescos (`sano=true` igual — un solo sistema viejo no cuenta), todos
  caducados (`sano=false`), sin ningún sistema en `hub_systems`
  (`sano=false`, `systems=[]`); `congelar_hub_beszel_vivo()` arma el
  snapshot correctamente en los cuatro casos
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "hub de Beszel", sigue sin incluir
  la cláusula de crítico; la cláusula FR-006a aparece solo cuando
  `hub_beszel_stats` está poblado (no cuando `hub_beszel_actual` lo
  está); **y** (mismo hallazgo recurrente ya corregido desde el diseño
  en 013/014) `test_parsear_respuesta_hub_beszel_con_varias_hipotesis`:
  una respuesta simulada con `len(hipotesis) > 1` se acepta
  correctamente (SC-002)

**Checkpoint**: Miquel puede diagnosticar en vivo el hub de Beszel con
el mismo rigor que los demás orígenes — User Story 1 completa e
independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un momento pasado del hub, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar un momento pasado concreto y
diagnosticar si todos los sistemas del hub dejaron de reportar a la
vez en una ventana alrededor de ese momento, con la misma garantía de
reproducibilidad que los demás orígenes, sin línea base real de "hub
caído" disponible (spec.md FR-001, FR-002, FR-006a; SC-001, SC-005).

**Independent Test**: `congelar --hub-beszel-historico` dos veces
sobre el mismo `MOMENTO_ISO` y comprobar que `diagnosticar` produce el
mismo `conclusion_tipo` las dos veces — quickstart.md Escenario 4.

### Implementación para User Story 2

- [X] T009 [US2] Implementar `_consultar_beszel_hub_todos_sistemas(
  inicio_utc, fin_utc)` en `src/diagnostico/evidencia.py` —
  generaliza `_consultar_beszel_hub()` de 014: mismo patrón de `docker
  run` parametrizado (reutiliza `_docker_bin()`/`BESZEL_HUB_VOLUME` de
  014), pero la consulta SQL usa `LEFT JOIN systems s ON ... LEFT JOIN
  system_stats ss ON ss.system = s.id AND ss.created BETWEEN ? AND ?`
  para no perder sistemas sin ninguna muestra (research.md §4); `None`
  si Docker no está disponible o el proceso falla — independiente de
  T003-T008 salvo compartir fichero
- [X] T010 [US2] Implementar `_resumen_por_sistema(filas)` en
  `src/diagnostico/evidencia.py` — agrupa `(nombre, created, tipo)`
  por `nombre`, reutiliza `_resumen_system_stats()` de 014 tal cual
  para cada grupo, calcula `todos_sin_muestras = bool(resumen) and
  all(r["total_muestras"] == 0 for r in resumen.values())`
  (research.md §4/§5) — independiente de T009 salvo compartir fichero
- [X] T011 [US2] Implementar `congelar_hub_beszel_historico(conn,
  momento)` en `src/diagnostico/evidencia.py` + constante
  `VENTANA_HUB_BESZEL_MINUTOS = 1440` — **sin argumento de nombre**
  (research.md §2); convierte la ventana `momento ± 1440min` a UTC
  (`_a_utc_madrid()` de 014); consulta el hub (T009) — **si devuelve
  `None`, `hub_beszel_stats=None`; si devuelve una lista (aunque
  vacía), `hub_beszel_stats=_resumen_por_sistema(lista)` (T010)**,
  nunca pasar `None` a T010 (mismo hallazgo real ya corregido en 014
  §10, aplicado aquí desde el diseño); arma el snapshot (T002);
  `componente=momento.isoformat()`; `ventana_inicio`/`ventana_fin` =
  `momento ± 1440min`; `en_vivo=False` — depende de T002, T009, T010
- [X] T012 [US2] Conectar el flag `--hub-beszel-historico MOMENTO_ISO`
  en `src/diagnostico/cli.py` — mismo patrón que `--backup-historico`
  (sin prefijo `@`, un solo valor) — depende de T011
- [X] T013 [P] [US2] Autocomprobación `tests/selftest/test_evidencia.py`
  (ampliar T007) — `_consultar_beszel_hub_todos_sistemas()` simulada
  vía `patch.object`; `_resumen_por_sistema()` con filas de varios
  sistemas (algunos con muestras, otros sin ninguna vía `LEFT JOIN`
  simulado con `created=None`), verificando `todos_sin_muestras` en
  los tres casos (ninguno sin muestras, alguno sin muestras, todos sin
  muestras); `congelar_hub_beszel_historico()` reproducible, y
  distinguiendo consulta fallida (`None` → `hub_beszel_stats=None`,
  sin `TypeError`) de consulta con éxito sin filas
  (`hub_beszel_stats` con `todos_sin_muestras` calculado)
- [X] T014 [P] [US2] Autocomprobación `tests/selftest/test_deepseek.py`
  (ampliar T008) — prueba de integración de
  `deepseek.diagnosticar_episodio()` con `origen="hub_beszel"`:
  confirma que ningún tratamiento especial de otro origen (relay F1,
  HA, host externo FR-006a) se dispara por error, y que una respuesta
  que respeta la cláusula FR-006a propia de este origen se acepta
  normalmente — mismo patrón que T015 de 014

**Checkpoint**: las dos historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido
protegiendo también al hub de Beszel.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T015 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir el hub de Beszel a la lista
  de orígenes soportados y referenciar
  `specs/015-diagnostico-hub-beszel/`; dejar solo agentes en la lista
  de "orígenes que siguen fuera de alcance" — el último de los 9
- [X] T016 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (depende de que T001-T014 estén desplegadas)
- [X] T017 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra el hub real sano — SC-004
  (depende de US1)
- [X] T018 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — momento dentro de la avería real
  de 014, confirmando ausencia parcial (no total) y `no_diagnosticable`
  honesto que respeta FR-006a — SC-005, sin línea base real de "hub
  caído" (depende de US2)
- [X] T019 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido —
  SC-001 (depende de US2)
- [X] T020 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — el gasto del hub cuenta contra el
  mismo límite diario — FR-007 (depende de US1 o US2)
- [X] T021 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — momento sin ningún dato en
  ningún sistema, `todos_sin_muestras=true`, `componente` refleja el
  momento pedido (depende de US2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real
- **US2 (Phase 3)**: depende de la Fase 1; T009/T010 son
  independientes de T003-T008 (US1) salvo compartir `evidencia.py`
- **Polish (Phase 4)**: T015 es independiente de todo lo demás; T016
  depende de que US1/US2 estén desplegadas; T018 es la validación más
  importante de Polish, aunque esta vez sin un episodio real de "hub
  caído" que reproducir — confirma que la ausencia de línea base real
  se documentó honestamente (research.md §6), no que se ocultó

### Parallel Opportunities

- T001, T002 (Foundational) son paralelas entre sí
- T006 (US1, prompt) es paralelo a T003-T005
- T007, T008 (autocomprobaciones US1) son paralelas entre sí
- T009, T010 (US2) son paralelas entre sí hasta que T011 las una
- T013, T014 (autocomprobaciones US2) son paralelas entre sí, e
  independientes de T007/T008 salvo por compartir fichero
- T015-T021 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (molde de snapshot)
2. Completar Fase 2: US1 (diagnóstico del hub en vivo)
3. **PARAR Y VALIDAR**: Escenario 2 de `quickstart.md` contra el hub
   real sano
4. Ese es el punto en el que el feature ya demuestra su valor central

### Entrega incremental

1. Foundational → molde de snapshot listo, sin romper 007-014
2. US1 → diagnóstico del hub en vivo, demo posible (MVP!)
3. US2 → diagnóstico en diferido, reproducible, con FR-006a propia —
   **sin línea base real de "hub caído"**, documentado explícitamente
   como limitación, no oculto (T018, research.md §6)
4. Polish → validación manual completa de los 6 escenarios,
   documentación del paquete actualizada — cierra el octavo de los 9
   orígenes

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre Beszel (FR-008)
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py`
- Ninguna tarea diagnostica un host externo concreto (FR-010) — es el
  origen #7 (014), ya cerrado
- **Es el feature con menos infraestructura genuinamente nueva de toda
  la serie**: T003/T004/T005/T006 (US1) y T009/T010/T011/T012 (US2)
  reutilizan explícitamente `BESZEL_HOSTS_JSON`,
  `BESZEL_HOSTS_MAX_AGE_S`, `BESZEL_HUB_VOLUME`, `_docker_bin()`,
  `_a_utc_madrid()` y `_resumen_system_stats()` de 014 sin
  reimplementar nada de eso — la única lógica realmente nueva es "para
  todos los sistemas a la vez" en vez de "para un sistema concreto"
- **T018 valida honestidad, no un episodio real** — a diferencia de
  012/013/014, este feature no tiene una avería real conocida que
  reproducir (research.md §6); la validación de Polish confirma que el
  mecanismo distingue correctamente ausencia parcial de ausencia
  total, no que "encontró" un caso que en realidad no existe
