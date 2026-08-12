# Tasks: Generalizar el Diagnóstico a los Relays

**Input**: Design documents from `/specs/012-diagnostico-relays/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007/009/010/011)
— verificación de lógica pura contra un `socat_relays.json`/
`dashboard-socat.log` simulados, sin tocar los ficheros reales de
producción ni DeepSeek, salvo en las tareas de validación manual
explícitas de Polish.

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
`src/diagnostico/_homelab_bridge.py` (research.md §1/§6; plan.md) —
ninguna tarea los toca.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: el molde de snapshot vacío que las dos historias
necesitan — a diferencia de 011, aquí no hay una única función de
parseo compartida (vivo lee JSON, diferido lee texto), así que la
única pieza realmente común es el molde del snapshot.

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el quinto valor real de
  `origen` (`"relay"`, además de
  `"contenedor"`/`"disco"`/`"ha"`/`"backup"`) — sin cambio de esquema
  ni de campos, solo el docstring (data-model.md; research.md §1)
- [X] T002 [P] Implementar `_snapshot_relay_vacio()` en
  `src/diagnostico/evidencia.py` — devuelve el dict con todos los
  campos heredados de orígenes anteriores a `null` más
  `relay_nombre`/`relay_estado_actual`/`relay_agregado` a `null`,
  mismo patrón que `_snapshot_backup_vacio()` de 011 (data-model.md)

**Checkpoint**: el molde de snapshot está listo para que cualquier
historia lo use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo un relay concreto (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo de cualquiera de
los 10 relays vigilados, con detalle real (`socat_relays.json`) y el
mismo rigor que ya tiene un contenedor, un disco, un check de HA o un
backup (spec.md FR-001 a FR-007).

**Independent Test**: `congelar --relay-vivo NOMBRE` + `diagnosticar`
contra un relay sano concluye `no_diagnosticable` sin inventar una
causa — quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T003 [P] [US1] Implementar `_relay_actual(nombre)` en
  `src/diagnostico/evidencia.py` + constante nueva `SOCAT_RELAYS_JSON`
  (configurable, por defecto
  `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json`)
  — lee el JSON, busca la entrada cuyo `name` coincide exactamente con
  `nombre`, `None` si no existe (research.md §3)
- [X] T004 [US1] Implementar `congelar_relay_vivo(conn, nombre)` en
  `src/diagnostico/evidencia.py` — resuelve el relay (T003); arma el
  snapshot (T002) con `relay_nombre=nombre`,
  `relay_estado_actual=<entrada o None>`; `componente=nombre`,
  `es_critico=False` siempre, `origen="relay"`, `en_vivo=True`,
  `restart_history_id=None` (data-model.md) — depende de T002, T003
- [X] T005 [US1] Conectar el flag `--relay-vivo NOMBRE` en
  `src/diagnostico/cli.py` (`congelar`, grupo mutuamente excluyente ya
  existente) — `NOMBRE` puede tener espacios, el usuario lo entrecomilla
  (research.md §8; contracts/cli.md) — depende de T004
- [X] T006 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o un relay `socat` caído"
  a la lista ya existente; **y** añadir la cláusula nueva (aplicable
  cuando `snapshot["relay_agregado"]` no es `null`): el modelo NUNCA
  debe nombrar un relay concreto como causa cuando la evidencia es
  agregada, porque esa información no existe (research.md §7; FR-006)
  — independiente de T003-T005
- [X] T007 [P] [US1] Autocomprobación
  `tests/selftest/test_evidencia.py` — `_relay_actual()` contra un
  `socat_relays.json` de prueba (relay existente y relay inexistente);
  `congelar_relay_vivo()` arma el snapshot correctamente en ambos casos,
  sin lanzar cuando el nombre no existe
- [X] T008 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "relay", sigue sin incluir la
  cláusula de crítico (`es_critico=False` siempre); la cláusula de
  "nunca nombres un relay concreto" aparece en el prompt cuando el
  snapshot simulado tiene `relay_agregado` poblado, y NO aparece
  cuando tiene `relay_estado_actual` poblado (episodio en vivo); **y**
  (hallazgo C1 de `/speckit-analyze`, 2026-08-12, SC-002)
  `test_parsear_respuesta_relay_con_varias_hipotesis` — mismo patrón
  que `test_parsear_respuesta_disco_con_varias_hipotesis` (009),
  `..._ha_...` (010) y `..._backup_...` (011): una respuesta simulada
  de un episodio de relay con `len(hipotesis) > 1` se acepta
  correctamente

**Checkpoint**: Miquel puede diagnosticar en vivo cualquiera de los 10
relays vigilados con el mismo rigor que los demás orígenes — User
Story 1 completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un momento pasado de los relays, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar un momento pasado dentro del histórico
real conservado y diagnosticarlo más tarde, con evidencia agregada
honesta —**y validada en código, no solo pedida al modelo**— y la
misma garantía de reproducibilidad que los demás orígenes (spec.md
FR-001, FR-002, FR-006; SC-001, SC-005).

**Independent Test**: `congelar --relay-historico` dos veces sobre el
mismo momento y comprobar que `diagnosticar` produce el mismo
`conclusion_tipo` las dos veces — quickstart.md Escenario 5.

### Implementación para User Story 2

- [X] T009 [US2] Implementar `_agregado_relays_ventana(momento,
  ventana_minutos)` en `src/diagnostico/evidencia.py` + constantes
  nuevas `DASHBOARD_SOCAT_LOG` (configurable, por defecto
  `~/Library/Logs/dashboard-socat.log`, expandida con
  `Path.expanduser()`), `VENTANA_RELAY_MINUTOS = 180`,
  `RELAY_AGREGADO_MAX_LINEAS = 100` — parsea cada línea con el patrón
  `\[(?P<ts>[^\]]+)\].*?(?P<ok>\d+)/(?P<total>\d+) ok`, se queda con
  las que caen en `[momento - ventana, momento + ventana]`, acotadas al
  límite defensivo (research.md §5) — independiente de T003-T008 salvo
  compartir fichero
- [X] T010 [US2] Implementar `congelar_relay_historico(conn, momento)`
  en `src/diagnostico/evidencia.py` — reúne el agregado (T009); arma el
  snapshot (T002) con `relay_agregado=<lista>`, `relay_nombre=None`,
  `relay_estado_actual=None`; `componente=momento.isoformat()` **usando
  siempre el momento pedido, nunca `datetime.now()`**, incluso cuando
  `relay_agregado` queda `[]` (lección de 011 aplicada por diseño,
  research.md §9); `ventana_inicio`/`ventana_fin` = `momento ±
  VENTANA_RELAY_MINUTOS`; `en_vivo=False` — depende de T002, T009
- [X] T011 [US2] Implementar la validación en código de "nunca
  nombres un relay concreto" — hallazgo F1 de `/speckit-analyze`
  (2026-08-12): FR-006 solo estaba pedido en el prompt (T006), sin
  ninguna validación en código, a diferencia del invariante hermano
  ("exactamente una hipótesis `confirmada`") que sí se valida en
  `parsear_respuesta()` desde 007. Implementar
  `listar_nombres_relay()` en `src/diagnostico/evidencia.py` (lee los
  `name` de `socat_relays.json` ahora mismo, `set()` si el fichero no
  existe) y `_menciona_relay_concreto(parsed, nombres)` en
  `src/diagnostico/deepseek.py` (busca cada nombre, en minúsculas, como
  subcadena de `conclusion_texto` + `descripcion`/`comprobacion` de
  cada hipótesis). En `diagnosticar_episodio()`, tras un `parsear_respuesta()`
  exitoso, si `episodio.origen == "relay"` y
  `episodio.snapshot_evidencia["relay_agregado"]` no es `None` y
  `_menciona_relay_concreto(...)` es cierto, rechazar la respuesta —
  mismo tratamiento que una respuesta inconsistente: se registra el
  coste real (la llamada sí ocurrió), pero se persiste
  `no_diagnosticable` con un motivo explícito citando FR-006 — depende
  de T006, T009, T010
- [X] T012 [US2] Conectar el flag `--relay-historico MOMENTO_ISO` en
  `src/diagnostico/cli.py` — sin prefijo `NOMBRE@`, a diferencia de
  `--disco-historico`/`--ha-historico` (research.md §2/§8; mismo
  criterio que `--backup-historico` de 011) — depende de T010
- [X] T013 [P] [US2] Autocomprobación
  `tests/selftest/test_evidencia.py` (ampliar T007) —
  `_agregado_relays_ventana()` con momentos dentro y fuera de la
  ventana de ±180 min, y un log simulado con más de
  `RELAY_AGREGADO_MAX_LINEAS` para comprobar el límite defensivo;
  `congelar_relay_historico()` reproducible (dos congelados del mismo
  momento producen la misma evidencia) y con `componente` igual al
  momento pedido incluso sin ningún dato en la ventana; **y**
  `listar_nombres_relay()` contra un `socat_relays.json` de prueba
- [X] T014 [P] [US2] Autocomprobación `tests/selftest/test_deepseek.py`
  (ampliar T008) — `_menciona_relay_concreto()` detecta un nombre real
  citado en `conclusion_texto` y en una `hipotesis`, y no da falsos
  positivos con texto que no menciona ningún nombre de la lista;
  `diagnosticar_episodio()` con una respuesta simulada que nombra un
  relay concreto para un episodio en diferido se rechaza y registra el
  coste real igual que una respuesta inconsistente (F1)

**Checkpoint**: las dos historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido (FR-007,
`gasto.py` sin cambios) protegiendo también a los relays, y FR-006
validado en código, no solo pedido al modelo.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T015 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir relays a la lista de orígenes
  soportados y referenciar `specs/012-diagnostico-relays/`; quitar
  relays de la lista de "orígenes que siguen fuera de alcance"
- [X] T016 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (sin migración de esquema; depende de que T001-T014 estén
  desplegadas)
- [X] T017 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra al menos dos relays reales
  sanos — SC-004 (depende de US1)
- [X] T018 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — relay inexistente, evidencia
  vacía sin lanzar (depende de US1)
- [X] T019 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — diagnóstico en diferido contra el
  episodio real conocido del 2026-05-24 (~10h de caída) — SC-005, la
  garantía central de este feature (primera línea base real del
  proyecto); confirmar también que la `conclusion_texto` real no
  nombra ningún relay concreto (F1, validado en código por T011);
  validar **antes** que el resto de escenarios de diferido, mismo
  criterio que 011 dio prioridad a su propia garantía central (depende
  de US2)
- [X] T020 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido —
  SC-001 (depende de US2)
- [X] T021 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de
  relay cuenta contra el mismo límite diario que los demás orígenes —
  FR-007 (depende de US1 o US2)
- [X] T022 [P] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — momento sin ningún dato en la
  ventana, `componente` refleja el momento pedido (depende de US2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real
- **US2 (Phase 3)**: depende de la Fase 1; T009 es independiente de
  T003-T008 (US1) salvo por compartir `evidencia.py`; T011 depende de
  T006 (US1, mismo fichero `deepseek.py`) además de T009/T010 (US2) —
  es la única tarea de US2 con una dependencia real hacia US1
- **Polish (Phase 4)**: T015 es independiente de todo lo demás; T016
  depende de que US1/US2 estén desplegadas; T019 es la validación más
  importante de Polish — confirma la garantía central del feature
  contra un episodio real ya conocido, no simulado, y confirma en vivo
  que T011 funciona de verdad

### Parallel Opportunities

- T001, T002 (Foundational) son paralelas entre sí
- T003 (US1) es paralelo al resto de la Fase 2 hasta que T004 lo use
- T006 (US1, prompt) es paralelo a T003-T005
- T007, T008 (autocomprobaciones US1) son paralelas entre sí
- T009 (US2) es paralelo a toda la Fase 2 (US1) hasta que T011 necesite
  también T006
- T013, T014 (autocomprobaciones US2) son paralelas entre sí, e
  independientes de T007/T008 salvo por compartir fichero
- T015-T022 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende

---

## Parallel Example: User Story 1

```bash
# T003 (resolución) y T006 (prompt) pueden ir en paralelo:
Task: "Implementar _relay_actual() en src/diagnostico/evidencia.py"
Task: "Generalizar _PROMPT_INSTRUCCIONES en src/diagnostico/deepseek.py"

# Autocomprobaciones de US1, en paralelo entre sí una vez T004/T005 estén listas:
Task: "Autocomprobación _relay_actual/congelar_relay_vivo en tests/selftest/test_evidencia.py"
Task: "Autocomprobación prompt generalizado en tests/selftest/test_deepseek.py"
```

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (molde de snapshot)
2. Completar Fase 2: US1 (diagnóstico de relay en vivo)
3. **PARAR Y VALIDAR**: Escenario 2 de `quickstart.md` contra al menos
   dos relays reales sanos
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar un relay caído con el mismo rigor que los demás
   orígenes

### Entrega incremental

1. Foundational → molde de snapshot listo, sin romper 007/009/010/011
2. US1 → diagnóstico de relay en vivo, demo posible (MVP!)
3. US2 → diagnóstico en diferido, reproducible, con FR-006 validado en
   código (T011) — **y la primera comprobación real de este proyecto
   contra una línea base real desde el arranque** (T019, el episodio
   del 2026-05-24)
4. Polish → validación manual completa de los 7 escenarios,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre ningún relay ni su LaunchAgent (FR-008)
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py` —
  sin migración de esquema, el gasto ya es agnóstico al origen, y este
  feature no necesita puentear ningún script externo
- Ninguna tarea amplía `dump_socat_status.py::SOCAT_RELAYS` a los
  relays de HA sin cubrir (HEOS, Marantz, ESPHome, Android TV, Tapo) —
  FR-010, es cobertura nueva (Frente 1), no diagnóstico
- **T011 es la tarea que corrige el hallazgo F1 de `/speckit-analyze`**:
  FR-006 ("nunca nombres un relay concreto") pasa de ser solo una
  petición al prompt a ser un invariante validado en código, igual que
  ya lo está "exactamente una hipótesis confirmada" desde 007 — la
  primera vez en este proyecto que un invariante de "nunca inventar"
  se refuerza en código específicamente para un origen, no solo de
  forma genérica
