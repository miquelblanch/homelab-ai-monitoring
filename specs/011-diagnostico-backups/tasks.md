# Tasks: Generalizar el Diagnóstico a los Backups

**Input**: Design documents from `/specs/011-diagnostico-backups/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest que ya usa `diagnostico` (features 007/009/010)
— verificación de lógica pura contra logs de backup simulados, sin
tocar los logs reales de producción ni DeepSeek, salvo en las tareas de
validación manual explícitas de Polish.

**Organization**: agrupadas por historia de usuario (spec.md).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos, sin
  dependencia de datos entre ellas)
- **[Story]**: US1 / US2, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Generaliza el paquete ya existente `src/diagnostico/` (plan.md, Project
Structure) — ningún paquete nuevo, ningún fichero nuevo en
`homelab-ai-monitoring` fuera de `tests/selftest/`. Sin cambios en
`src/diagnostico/store.py`, `src/diagnostico/gasto.py` ni
`src/diagnostico/_homelab_bridge.py` (research.md §1/§6; plan.md) —
ninguna tarea los toca.

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: el parseo acotado del log (research.md §3) y el listado
de logs disponibles que las dos historias necesitan.

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase — en
particular, T002 es la pieza que evita repetir el reventón de prompt
ya visto en 010 (research.md §3), así que debe quedar bien probada
antes de que T005/T011 la usen.

- [X] T001 [P] Actualizar el docstring de `Episodio` en
  `src/diagnostico/model.py` para documentar el cuarto valor real de
  `origen` (`"backup"`, además de `"contenedor"`/`"disco"`/`"ha"`) —
  sin cambio de esquema ni de campos, solo el docstring (data-model.md;
  research.md §1)
- [X] T002 Implementar `_parsear_log_backup(texto)` en
  `src/diagnostico/evidencia.py` — extrae `dumps` (líneas ✅/⚠️),
  `rsync_stats` (bloque `--stats`), `resumen_final`, `rsync_estado`
  (`"ok"`/`"error"`, parseado del propio texto que ya lo clasifica) y
  `anomalias` (líneas que coinciden con patrones de error real de
  rsync — `rsync:`, `rsync error:`, `IO error`, `Permission denied` —
  en cualquier punto del log, **excluidas las que ya coincidieron con
  el patrón de `dumps`** para no contar dos veces un dump fallido
  — hallazgo I1 de `/speckit-analyze`, 2026-08-12 — acotadas a la
  constante nueva `BACKUP_ANOMALIA_MAX_LINEAS = 30`) — research.md §3
- [X] T003 Implementar `_listar_logs_backup()` en
  `src/diagnostico/evidencia.py` (glob `backup_*.log` en
  `BACKUP_LOG_DIR`, constante nueva configurable vía la variable de
  entorno `BACKUP_LOG_DIR`, por defecto
  `/Volumes/FastData/homelab/logs`, orden lexicográfico ascendente —
  research.md §5; mismo fichero que T002, función independiente)

**Checkpoint**: el parseo acotado y el listado de logs están listos
para que cualquier historia los use.

---

## Phase 2: User Story 1 - Diagnosticar en vivo el backup más reciente (Priority: P1) 🎯 MVP

**Goal**: Miquel puede pedir un diagnóstico en vivo del backup nocturno
más reciente, con el mismo rigor que ya tiene un contenedor, un disco
o un check de HA (spec.md FR-001 a FR-007).

**Independent Test**: `congelar --backup-vivo` + `diagnosticar` contra
un backup sano concluye `no_diagnosticable` sin inventar una causa —
quickstart.md Escenario 2.

### Implementación para User Story 1

- [X] T004 [US1] Implementar `_log_backup_mas_reciente()` en
  `src/diagnostico/evidencia.py` (usa `_listar_logs_backup()` de T003,
  devuelve el último de la lista o `None` si no hay ninguno) —
  research.md §5; depende de T003
- [X] T005 [US1] Implementar `congelar_backup_vivo(conn)` en
  `src/diagnostico/evidencia.py` — resuelve el log más reciente
  (T004); si no hay ninguno, congela igual con toda la evidencia de
  backup en `null`/`[]` (contracts/cli.md, sin lanzar); si lo hay, lo
  parsea (T002) y arma el snapshot con `backup_log_path`,
  `backup_dumps`, `backup_rsync_stats`, `backup_resumen_final`,
  `backup_rsync_estado`, `backup_anomalias`, y el resto de claves
  heredadas de orígenes anteriores a `null` (data-model.md);
  `componente` = momento ISO extraído del nombre del fichero;
  `es_critico=False` siempre, `origen="backup"`,
  `restart_history_id=None` — depende de T002, T004
- [X] T006 [US1] Conectar el flag `--backup-vivo` (sin argumento,
  `action="store_true"`) en `src/diagnostico/cli.py` (`congelar`,
  grupo mutuamente excluyente ya existente) — research.md §8; depende
  de T005
- [X] T007 [US1] Generalizar `_PROMPT_INSTRUCCIONES` en
  `src/diagnostico/deepseek.py` — añadir "...o un backup nocturno
  fallido o parcial (rsync, o algún dump de base de datos)" a la lista
  ya existente de contenedor/disco/HA, sin tocar la estructura del
  JSON pedido (research.md §7; independiente de T004-T006)
- [X] T008 [P] [US1] Autocomprobación
  `tests/selftest/test_evidencia.py` — `_parsear_log_backup()` contra
  logs de backup simulados (con y sin fallos, y uno artificialmente
  grande con más de 30 líneas de anomalía para comprobar el recorte);
  `congelar_backup_vivo()` contra un directorio de logs de prueba en un
  fichero temporal; el caso sin ningún log disponible congela igual
  sin lanzar
- [X] T009 [P] [US1] Autocomprobación `tests/selftest/test_deepseek.py`
  — el prompt generalizado menciona "backup" y sigue sin incluir la
  cláusula de crítico para un episodio de backup (`es_critico=False`
  siempre); **y** (hallazgo C1 de `/speckit-analyze`, 2026-08-12,
  SC-002) `test_parsear_respuesta_backup_con_varias_hipotesis` — mismo
  patrón que `test_parsear_respuesta_disco_con_varias_hipotesis` (009)
  y `test_parsear_respuesta_ha_con_varias_hipotesis` (010): una
  respuesta simulada de un episodio de backup con `len(hipotesis) > 1`
  se acepta correctamente

**Checkpoint**: Miquel puede diagnosticar en vivo el backup más
reciente con el mismo rigor que un contenedor, un disco o un check de
HA — User Story 1 completa e independientemente comprobable.

---

## Phase 3: User Story 2 - Diagnosticar un backup pasado, reproduciblemente (Priority: P2)

**Goal**: Miquel puede señalar un momento pasado dentro de la ventana
de 7 días retenidos y diagnosticarlo más tarde, con la misma garantía
de reproducibilidad que ya tienen los demás orígenes (spec.md FR-001,
FR-002; SC-001).

**Independent Test**: `congelar --backup-historico` dos veces sobre el
mismo momento y comprobar que `diagnosticar` produce el mismo
`conclusion_tipo` las dos veces — quickstart.md Escenario 4.

### Implementación para User Story 2

- [X] T010 [US2] Implementar `_log_backup_cercano(momento)` en
  `src/diagnostico/evidencia.py` (usa `_listar_logs_backup()` de T003;
  parsea el timestamp embebido en cada nombre de fichero; devuelve el
  más cercano a `momento` dentro de la constante nueva
  `VENTANA_BACKUP_HORAS = 12`, o `None` si ninguno cae dentro de la
  ventana) — research.md §5; depende de T003
- [X] T011 [US2] Implementar `congelar_backup_historico(conn, momento)`
  en `src/diagnostico/evidencia.py` — misma lógica de armado de
  snapshot que T005, pero resolviendo el log con `_log_backup_cercano`
  (T010) en vez de `_log_backup_mas_reciente`; `ventana_inicio`/
  `ventana_fin` = el momento del propio log encontrado (data-model.md);
  `en_vivo=False` — depende de T002, T010
- [X] T012 [US2] Conectar el flag `--backup-historico MOMENTO_ISO` en
  `src/diagnostico/cli.py` — sin prefijo `LABEL@`/`CHECK_ID@`, a
  diferencia de `--disco-historico`/`--ha-historico` (research.md §2/§8
  de 011; contracts/cli.md); depende de T011
- [X] T013 [P] [US2] Autocomprobación
  `tests/selftest/test_evidencia.py` (ampliar T008) —
  `_log_backup_cercano()` con momentos dentro y fuera de la ventana de
  ±12h; `congelar_backup_historico()` contra el mismo directorio de
  prueba; dos congelados del mismo momento producen la misma evidencia
  (base de SC-001); **y** (hallazgo U1 de `/speckit-analyze`,
  2026-08-12) `congelar_backup_historico()` con un momento fuera de la
  ventana (ningún log cercano) congela igual, sin lanzar — mismo
  patrón que T008 ya prueba para `congelar_backup_vivo()` sin ningún
  log disponible

**Checkpoint**: las dos historias funcionan juntas — feature completo
según spec.md, con el mismo cortacircuitos de gasto compartido (FR-007,
`gasto.py` sin cambios) protegiendo también a los backups.

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T014 [P] Actualizar el docstring de módulo de
  `src/diagnostico/__init__.py` — añadir backups a la lista de
  orígenes soportados y referenciar `specs/011-diagnostico-backups/`;
  quitar backups de la lista de "orígenes que siguen fuera de alcance"
- [X] T015 [P] Validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) — ningún episodio ya persistido
  cambia (sin migración de esquema, research.md §1; depende de que
  T001-T013 estén desplegadas). **Validado el 2026-08-12**: `mostrar 6`
  (episodio real de 007) se lee exactamente igual que antes de este
  feature.
- [X] T016 [P] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) contra el backup real más reciente,
  sano — SC-004 (depende de US1). **Validado el 2026-08-12 con
  DeepSeek real** (episodio 31): `no_diagnosticable` al primer intento,
  citando explícitamente que todos los dumps están OK, rsync 'ok' y sin
  anomalías — 4 hipótesis contrastadas.
- [X] T017 [P] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — `_parsear_log_backup()` contra el
  log real más grande retenido (`backup_2026-08-07_02-00-02.log`, 955
  KB, 9.878 líneas), confirmando que `backup_anomalias` nunca supera
  `BACKUP_ANOMALIA_MAX_LINEAS` (depende de T002, sin esperar a US1/US2).
  **Validado el 2026-08-12**: de 951.031 caracteres / 9.878 líneas
  originales, la evidencia extraída quedó en 1.684 caracteres (8 líneas
  de dumps, 30 de stats — dos rsyncs por noche, Hermes + FastData
  principal — 0 anomalías) — la garantía central del feature, confirmada
  contra el caso real más exigente antes que ningún otro escenario.
- [X] T018 [P] Validar manualmente el Escenario 4 de
  [quickstart.md](./quickstart.md) — reproducibilidad en diferido
  contra un log real dentro de los 7 días — SC-001 (depende de US2).
  **Validado el 2026-08-12 con DeepSeek real** (episodio 32,
  2026-08-10T02:00:00, diagnosticado dos veces): mismo `conclusion_tipo`
  (`no_diagnosticable`) en los dos intentos.
- [X] T019 [P] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — el gasto de un diagnóstico de
  backup cuenta contra el mismo límite diario que contenedor/disco/HA
  — FR-007 (depende de US1 o US2). **Validado el 2026-08-12**:
  `gasto_diario` de hoy (0,24332864€) es exactamente la suma del coste
  real de los diagnósticos de HA (0,23607837€) y de backup
  (0,00725027€, 4 diagnósticos) — un único acumulado, confirmado por
  consulta directa.
- [X] T020 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — un momento sin ningún log dentro
  de la ventana congela igual, sin lanzar — FR-001, Edge Cases (depende
  de US2). **Validado el 2026-08-12**: encontró y corrigió un hallazgo
  real — sin log, el episodio caía en el momento *actual* en vez del
  *pedido* (`_congelar_backup` ahora recibe `momento_solicitado`
  explícito); tras el arreglo, pedir `2020-01-01T02:00:00` muestra ese
  mismo momento en `mostrar`, con evidencia vacía y diagnóstico
  `no_diagnosticable` honesto.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: sin dependencias — BLOQUEA las dos
  historias
- **US1 (Phase 2)**: depende solo de la Fase 1 — es el MVP real
- **US2 (Phase 3)**: depende de la Fase 1; T010 reutiliza
  `_listar_logs_backup()` (T003) igual que T004, pero es independiente
  de T004-T009 (US1) salvo por compartir `evidencia.py`
- **Polish (Phase 4)**: T014 es independiente de todo lo demás; T015
  depende de que US1/US2 estén desplegadas; T017 solo depende de T002
  (Foundational), no de ninguna historia completa; T016/T018/T019/T020
  dependen cada una de la historia que validan

### Parallel Opportunities

- T001 (Foundational) es paralelo a T002/T003
- T002 y T003 están en el mismo fichero pero son funciones
  independientes entre sí
- T007 (US1, prompt) es paralelo al resto de la Fase 2 hasta que
  T008/T009 lo prueben
- T008, T009 (autocomprobaciones US1) son paralelas entre sí
- T013 (autocomprobación US2) es independiente de T008/T009 salvo por
  compartir fichero
- T014-T020 (Polish) son paralelas entre sí, cada una limitada por la
  historia de la que depende (ver Phase Dependencies) — T017 en
  particular no depende de ninguna historia, solo de Foundational

---

## Parallel Example: User Story 1

```bash
# T007 (prompt) puede ir en paralelo con T004-T006 (resolución + congelar + CLI):
Task: "Generalizar _PROMPT_INSTRUCCIONES en src/diagnostico/deepseek.py"

# Autocomprobaciones de US1, en paralelo entre sí una vez T005/T006 estén listas:
Task: "Autocomprobación _parsear_log_backup/congelar_backup_vivo en tests/selftest/test_evidencia.py"
Task: "Autocomprobación prompt generalizado en tests/selftest/test_deepseek.py"
```

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Foundational (parseo acotado + listado de logs)
2. Completar Fase 2: US1 (diagnóstico de backup en vivo)
3. **PARAR Y VALIDAR**: Escenario 3 de `quickstart.md` (el log real más
   grande no revienta el prompt) antes que ningún otro, ya que es la
   garantía que motivó el diseño completo de este feature; después,
   Escenario 2 contra el backup real más reciente
4. Ese es el punto en el que el feature ya demuestra su valor central:
   diagnosticar un backup nocturno con el mismo rigor que un
   contenedor, un disco o un check de HA, sin arriesgar el mismo
   reventón de prompt que ya costó dinero real en 010

### Entrega incremental

1. Foundational → parseo acotado y listado de logs listos, sin romper
   007/009/010
2. US1 → diagnóstico de backup en vivo, demo posible (MVP!)
3. US2 → diagnóstico en diferido dentro de los 7 días, reproducible
4. Polish → validación manual completa de los 6 escenarios,
   documentación del paquete actualizada

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni propone una acción
  correctiva sobre el backup ni sobre `/Volumes/Storage/backup/`
  (FR-008) — restricción del propio feature, no algo pendiente de
  implementar
- Ninguna tarea toca `src/diagnostico/store.py`,
  `src/diagnostico/gasto.py` ni `src/diagnostico/_homelab_bridge.py` —
  sin migración de esquema (research.md §1), el gasto ya es agnóstico
  al origen, y este feature no necesita puentear ningún script externo
  (research.md §6)
- T002/T008/T017 dejan escrita, no oculta, la razón de ser de todo el
  feature: el log crudo nunca llega a DeepSeek (research.md §3) —
  coherente con el hallazgo real de 010 que motivó este diseño desde
  el principio
