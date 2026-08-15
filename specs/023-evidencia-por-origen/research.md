# Phase 0 — Research: Evidencia de Diagnóstico Organizada por Origen

No quedaba ningún `NEEDS CLARIFICATION` en el Technical Context del plan —
todo lo técnico se deriva de cómo ya funciona el repo. Este documento resuelve
en su lugar las tres preguntas de diseño que sí exigían leer el código
(`src/diagnostico/evidencia.py`, `tests/selftest/test_evidencia.py`) antes de
poder plantear `data-model.md` y `tasks.md` con confianza.

## 1. Cómo preservar la superficie pública sin tocar a los consumidores

**Decisión**: `evidencia.py` se convierte en un paquete
(`diagnostico/evidencia/`) cuyo `__init__.py` actúa como fachada: importa y
reexporta los nombres que los consumidores reales usan hoy, nada más.

**Evidencia real de qué usan los tres consumidores** (comprobado con `grep`
sobre el código, no supuesto):

| Consumidor | Qué llama de `evidencia` |
|---|---|
| `diagnostico/cli.py` (dispatch por episodio) | los 18 `congelar_<origen>_vivo` / `_historico` de los diez orígenes |
| `remediacion/acciones.py:518` | solo `congelar_vivo` (origen contenedor) |
| `diagnostico/deepseek.py:388-391` | `nombres_relay_evidenciados()` y `listar_nombres_relay()` (origen relay, para rechazar una hipótesis que nombre un relay sin evidencia real — FR-006 de 012) |

**Rationale**: los tres importan hoy con `from diagnostico import evidencia`
y llaman `evidencia.<función>` — nunca `from diagnostico.evidencia import
<función>` directo. Un paquete con `__init__.py` que reexporta preserva ese
patrón exacto sin tocar una sola línea de los tres ficheros. Cumple FR-002
con el radio de cambio más pequeño posible.

**Alternativas consideradas**:
- *Actualizar los tres consumidores para importar desde el submódulo
  correspondiente* (`from diagnostico.evidencia import contenedor` →
  `contenedor.congelar_vivo(...)`). Rechazada para esta feature: multiplica
  el número de ficheros tocados sin ningún beneficio medible — los tres
  consumidores no tienen relación entre sí ni con este refactor, y FR-002
  exige justo lo contrario, cambiar lo mínimo posible en ellos. Queda como
  opción legítima para una limpieza futura, no como parte de esta.
- *Dejar `evidencia.py` como fichero único y solo dividir internamente con
  comentarios de sección*. Rechazada: no cumple FR-001 ni FR-003 — seguiría
  siendo un único fichero que crece con cada origen nuevo.

## 2. Qué es de verdad "mecanismo compartido" (FR-004/FR-006)

**Decisión**: solo entra en `_compartido.py` lo que usan **más de un**
origen a la vez, comprobado por uso real, no por apariencia genérica del
nombre.

**Evidencia real** (grep de cada función candidata contra el fichero
completo):

Comprobado con un barrido programático de cada `def` contra sus llamadas
reales en todo el fichero (no por lectura visual, que ya se demostró
engañosa con `es_critico` y con `disk_metrics_near`, ver abajo):

| Función / constante | Usada por | ¿Compartida? |
|---|---|---|
| `homelab_db_path`, `_connect_homelab_db` | contenedor (5 puntos) y disco (3 puntos) | Sí |
| `_run_ro` | solo dentro de `docker_inspect`/`docker_logs_tail` (la mención en la línea 1298 es un comentario de prosa, no una llamada) | Sí, por ser la base de `docker_logs_tail` |
| `docker_logs_tail` | contenedor (snapshot completo) y ha (log del contenedor de Home Assistant, dos puntos) | **Sí** |
| `docker_inspect`, `_parse_docker_inspect` | **solo contenedor** (una llamada cada una) | **No**, pese a estar justo al lado de `docker_logs_tail` — se mueven a `contenedor.py` |
| `restart_history_row`, `container_metrics_window`, `container_metrics_hourly_window`, `container_metrics_recientes`, `disk_metrics_near` | **solo contenedor** — las cinco, incluida `disk_metrics_near` (correlaciona el disco alrededor de un evento de contenedor; el origen "disco" tiene sus propias `disk_metrics_window`/`disk_metrics_recientes`, funciones distintas) | **No** — el nombre de `disk_metrics_near` sugiere "disco" y engaña; se mueve a `contenedor.py` |
| `insert_episodio` | los diez orígenes, vía `store.py` (ya vive fuera de `evidencia.py`, sin cambios) | Sí (ya extraída) |
| `es_critico` | solo contenedor (dos puntos) | **No** — pese a "sonar" genérica, hoy solo la usa un origen. Se mueve a `contenedor.py`. Si un origen futuro la necesita, se promueve entonces (FR-003 ya cubre ese caso: promocionar algo al mecanismo compartido no cuenta como tocar un origen existente). |
| `_docker_bin`, `BESZEL_HUB_VOLUME` | host_externo (`_consultar_beszel_hub`) y hub_beszel (`_consultar_beszel_hub_todos_sistemas`) — dos orígenes distintos | **Sí** |
| `_QUERY_SYSTEM_STATS` / `_QUERY_SYSTEM_STATS_TODOS` | una por origen (host_externo / hub_beszel respectivamente) — plantillas SQL distintas pese al nombre parecido | No — cada una a su origen |
| `inv_diff`, `inv_store`, `TIPOS_BRECHA` (paquete `inventory`) | solo inventario | No — se importan únicamente dentro de `inventario.py` |
| `_homelab_bridge` (`bridge.*`) | contenedor (`es_critico`) y ha (varias funciones) | Ya es un módulo compartido aparte, fuera de alcance de esta feature — cada submódulo que lo necesite lo importa igual que hoy |

**Rationale**: es la lectura literal de FR-006 (resuelto en `clarify`): el
mecanismo compartido es una pieza distinta de los diez orígenes, no un
origen más — y "distinta" se decide por uso real medido, no por intuición
sobre el nombre de la función.

**Alternativas consideradas**:
- *Meter todas las funciones con nombre genérico en `_compartido.py` sin
  comprobar uso real* (incluida `es_critico`). Rechazada: crearía
  acoplamiento falso — `disco.py` pasaría a depender de un módulo que en
  realidad solo necesita `contenedor.py`, justo el tipo de mezcla que este
  refactor busca eliminar (FR-001).

## 3. El riesgo real: `unittest.mock.patch.object` apunta al módulo equivocado tras la partición

**Hallazgo** (no una decisión de diseño, un riesgo concreto encontrado leyendo
`test_evidencia.py`): 41 líneas usan `evidencia._<algo_privado>(...)` o
`patch.object(evidencia, "_algo_privado", ...)` para invocar o sustituir
funciones internas — por ejemplo `patch.object(evidencia,
"_consultar_beszel_hub", return_value=...)` en los tests del origen hub
Beszel.

`unittest.mock.patch.object(modulo, "nombre", ...)` sustituye el atributo
`nombre` en el `__dict__` de `modulo`. Si `_consultar_beszel_hub` se define
en `hub_beszel.py` pero el test sigue hadiendo `patch.object(evidencia,
"_consultar_beszel_hub", ...)` sobre la fachada, el parche **no llega a la
función real** que se ejecuta dentro de `hub_beszel.py` — el test seguiría
en verde pero dejaría de probar lo que dice probar (llamaría a la función
real, no al doble). Es el mismo riesgo, silencioso, que motivó el
tratamiento de "sin lectura" en `ha_monitor.py` (ver `CLAUDE.md` general del
homelab, aviso de bateria_cerradura): un test que aparenta verificar y no
verifica.

**Decisión**: cada función privada y su `patch.object` correspondiente se
mueven juntos al mismo test de origen, apuntando al submódulo real
(`patch.object(evidencia_hub_beszel, "_consultar_beszel_hub", ...)`), nunca
a la fachada `evidencia`. Ya es una consecuencia directa de FR-007 (tests
reorganizados en paralelo al código): al partir `test_evidencia.py` por
origen, cada fichero nuevo importa su propio submódulo, no la fachada, así
que el parche cae naturalmente en el sitio correcto.

**Verificación exigida en tasks.md**: tras mover cada bloque de tests, correr
ese fichero de test con al menos un caso que dependa del `patch.object`
movido y confirmar que falla si se revierte el valor simulado — no basta con
verlo pasar en verde, hay que confirmar que sigue probando algo real.

## Resumen de decisiones

| # | Decisión | Afecta a |
|---|---|---|
| 1 | `evidencia/__init__.py` como fachada de compatibilidad; los 3 consumidores no cambian | data-model.md, tasks.md |
| 2 | `_compartido.py` solo con lo usado por >1 origen, verificado por grep, no por nombre | data-model.md, tasks.md |
| 3 | Cada `patch.object` viaja con su función al submódulo real, nunca queda apuntando a la fachada | tasks.md (paso de verificación explícito) |
