# Refactor — parseo de DeepSeek duplicado + `--selftest` engañoso

> **Resuelto el 2026-08-15 por `specs/025-consolidar-parseo-deepseek/`.**
> `_extraer_contenido_y_tokens()` (contenido + tokens, con el respaldo
> `content`/`reasoning_content`) vive ahora una sola vez, en
> `diagnostico/deepseek.py`; `remediacion/deepseek_contenedores.py` la
> importa directamente — mismo patrón ya autorizado en 021. El texto
> de `--help` y el docstring de `_run_selftest()` en las tres CLIs
> describen ahora con precisión que ejecutan la suite completa
> compartida, no una acotada a cada paquete. Ningún test se reescribió;
> 595/595/595 aserciones, idéntico a la línea base. Ver
> `specs/025-consolidar-parseo-deepseek/{spec,plan,research,data-model}.md`.
> Este documento queda como material histórico de la auditoría que
> motivó la feature.

> Material y criterios preparados por Claude antes de `speckit-specify`,
> mismo patrón que `REFACTOR-evidencia.md` (023) y
> `REFACTOR-homelab-bridge.md` (024). Dos hallazgos menores de la
> auditoría original, combinados en un único refactor a petición
> explícita — no comparten causa, pero ambos son correcciones
> pequeñas y de bajo riesgo.

## Hallazgo A — parseo de la respuesta de DeepSeek duplicado

**Evidencia (comprobada 2026-08-15):** `diagnostico/deepseek.py::parsear_respuesta`
(líneas 262-321) y `remediacion/deepseek_contenedores.py::parsear_respuesta_remediacion`
(líneas 83-99) repiten, literal, el mismo bloque de extracción:

```python
mensaje = respuesta["choices"][0]["message"]
contenido = mensaje.get("content") or mensaje.get("reasoning_content") or ""
usage = respuesta.get("usage", {})
tokens_entrada = int(usage.get("prompt_tokens", 0))
tokens_salida = int(usage.get("completion_tokens", 0))
parsed = json.loads(contenido)
```

Incluye el respaldo `content`/`reasoning_content` (hallazgo real de
validación en vivo, 2026-08-12, documentado en el docstring de
`parsear_respuesta`) — si se corrige en un sitio y no en el otro, el
mismo síntoma real (modelo de razonamiento que deja `content` vacío)
vuelve a aparecer en remediación sin que nadie lo note.

**Lo que NO se toca:** `construir_prompt`/`construir_prompt_remediacion`
preguntan cosas deliberadamente distintas — una pregunta abierta
("¿cuál es la causa?") frente a una cerrada ("¿aplica esta acción de
la lista?"), documentado explícitamente como decisión consciente en
el docstring de `deepseek_contenedores.py` y en
`specs/021-remediacion-contenedores/research.md` §3. Tampoco se toca
la validación posterior (`CONCLUSION_TIPOS`/`DESENLACES` en
diagnostico vs. `TIPOS_ACCION` en remediacion) — vocabularios
distintos, sin solapamiento real.

**Consumidores de cada función (comprobado):** ningún test parchea el
bloque de extracción directamente — todos llaman a
`parsear_respuesta`/`parsear_respuesta_remediacion` como caja negra
con un `respuesta` dict completo y comprueban la salida. Extraer el
bloque compartido no tiene el riesgo de `patch.object` que sí tuvieron
023 y 024.

**Precedente ya sentado:** `remediacion` ya importa directamente de
`diagnostico.deepseek` (`llamar_deepseek`, autorizado y documentado en
specs/021/research.md §2) — extraer el bloque compartido a una función
en `diagnostico/deepseek.py` e importarla desde
`remediacion/deepseek_contenedores.py` sigue exactamente ese patrón ya
existente, sin abrir ninguna dependencia nueva.

## Hallazgo B — `--selftest` sugiere un alcance que no tiene

**Evidencia:** las tres CLIs (`diagnostico`, `inventory`, `remediacion`)
tienen un flag `--selftest` cuyo texto de ayuda y docstring interno
sugieren una autocomprobación acotada a ese paquete:

| CLI | Texto de `--help` | Docstring de `_run_selftest()` |
|---|---|---|
| diagnostico | *"Autocomprobación de lógica pura, sin tocar DeepSeek/Docker/homelab.db reales."* | *"orquesta test_evidencia/test_deepseek/test_gasto/test_store/test_reproducibilidad/test_baseline_beszel"* |
| inventory | *"Autocomprobación de lógica pura, sin tocar Docker/HA/Telegram reales."* | *"orquesta test_evaluate/test_identity/test_diff/test_no_mutation"* |
| remediacion | *"Autocomprobación de lógica pura, contra logs de prueba en un directorio temporal."* | (sin docstring) |

En realidad, los tres llaman a `tests.selftest.run_all()`
(`tests/selftest/__init__.py`), que descubre y ejecuta **todos** los
`test_*.py` del directorio — hoy 24 ficheros, no los 4-6 que cada
docstring enumera. Los tres flags ejecutan exactamente la misma suite
completa (comprobado: 595 aserciones idénticas en los tres, ver
`specs/023-evidencia-por-origen/baseline-selftest.txt`).

**Lo que NO se toca:** partir la suite para que cada CLI ejecute solo
sus propios tests sería un cambio de comportamiento real (y de alcance
mucho mayor — los 24 ficheros no tienen un prefijo de paquete limpio
hoy: `test_deepseek.py`, `test_store.py`, `test_gasto.py`,
`test_baseline_beszel.py`, `test_reproducibilidad.py` no llevan
prefijo `remediacion_`/`evidencia_` aunque pertenezcan a diagnostico).
No es lo que motivó el hallazgo — el problema es que el texto engaña,
no que el comportamiento esté mal.

## Criterios de éxito candidatos

1. `parsear_respuesta` y `parsear_respuesta_remediacion` comparten una
   única función de extracción (contenido + tokens, con el respaldo
   `content`/`reasoning_content`) — un fallo o una corrección futura
   en ese respaldo se aplica en un solo lugar.
2. Cero cambio de comportamiento observable: los 595 aserciones de
   cada `--selftest` siguen pasando, incluidas las de
   `test_deepseek.py` y `test_remediacion_deepseek_contenedores.py`.
3. El texto de `--help` y el docstring de `_run_selftest()` en las
   tres CLIs describen con precisión lo que de verdad hace el flag:
   ejecuta la suite completa compartida de los tres paquetes, no una
   acotada a cada uno.
4. `construir_prompt`/`construir_prompt_remediacion` y la validación
   posterior de cada uno no se tocan — son alcance distinto, no
   duplicación real.
