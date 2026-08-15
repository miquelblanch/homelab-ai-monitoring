# Phase 0 — Research: Parseo de DeepSeek Compartido y Autocomprobación Sincera

## 1. Dónde vive la función compartida, y por qué no hace falta un módulo nuevo

**Decisión**: `_extraer_contenido_y_tokens()` vive en
`diagnostico/deepseek.py`. `remediacion/deepseek_contenedores.py` la
importa directamente.

**Evidencia real**: `remediacion/acciones.py:20` ya hace
`from diagnostico.deepseek import llamar_deepseek as
diagnostico_llamar_deepseek` — autorizado y documentado en
`specs/021-remediacion-contenedores/research.md` §2. Añadir
`_extraer_contenido_y_tokens` al mismo import no crea una dependencia
nueva, solo usa una que ya existe y ya está justificada. A diferencia
de 023 (evidencia.py, 10 orígenes sin relación previa) y 024 (tres
paquetes sin relación previa entre sí para el bridge), aquí no hace
falta decidir dónde poner un módulo neutral — el precedente ya resolvió
esa pregunta en 021.

**Alternativas consideradas**:
- *Un módulo compartido nuevo* (patrón 023/024). Rechazada: sería
  aplicar una solución más pesada de lo que el problema pide — solo
  hay dos consumidores, y uno de los dos ya depende directamente del
  otro para algo del mismo dominio (la llamada HTTP).

## 2. Ningún test necesita reescribirse — verificado

Comprobado con grep sobre `test_deepseek.py` y
`test_remediacion_deepseek_contenedores.py`: ningún test hace
`patch.object` sobre el bloque de extracción ni sobre ninguna función
interna de `parsear_respuesta`/`parsear_respuesta_remediacion` — los
dos se llaman siempre como caja negra, con un `respuesta` dict
completo, comprobando la salida. Extraer el bloque compartido a una
función nueva no tiene el riesgo de `patch.object` que sí tuvo 023.

## 3. Forma exacta de la función compartida

```python
def _extraer_contenido_y_tokens(respuesta: dict) -> tuple[dict, int, int]:
    """Extrae el contenido ya parseado como JSON y los tokens de
    entrada/salida de una respuesta cruda de la API de DeepSeek.
    Respaldo `content`/`reasoning_content` (hallazgo real de
    validación en vivo, 2026-08-12): el modelo de razonamiento a veces
    escribe la respuesta completa en `reasoning_content` y nunca la
    vuelve a escribir en `content`. Compartida entre el diagnóstico de
    episodios y la remediación de contenedores — la misma corrección
    debe aplicarse a los dos (specs/025-consolidar-parseo-deepseek/).
    Lanza KeyError/ValueError/TypeError/IndexError si la respuesta no
    tiene la forma esperada; el llamador decide qué hacer (los dos
    llamadores actuales lo tratan como "sin diagnóstico", nunca
    reintentan)."""
    mensaje = respuesta["choices"][0]["message"]
    contenido = mensaje.get("content") or mensaje.get("reasoning_content") or ""
    usage = respuesta.get("usage", {})
    tokens_entrada = int(usage.get("prompt_tokens", 0))
    tokens_salida = int(usage.get("completion_tokens", 0))
    return json.loads(contenido), tokens_entrada, tokens_salida
```

`parsear_respuesta` y `parsear_respuesta_remediacion` mantienen su
propio `try/except (KeyError, ValueError, TypeError, IndexError):
return None` alrededor de la llamada — el contrato de "nunca lanza"
sigue siendo responsabilidad del llamador, no de la función compartida
(mismo patrón que las funciones de `evidencia/` en 023, que devuelven
`None`/vacío en su propio nivel, no dentro de un helper interno).

## 4. Texto de `--selftest` — qué decir en su lugar

**Decisión**: sustituir la lista de ficheros (siempre desactualizada
en cuanto se añade un test nuevo) por una frase que describa el
mecanismo real, no una instantánea de su contenido.

Ejemplo para las tres CLIs:
- `--help`: *"Autocomprobación — ejecuta la suite completa compartida
  de los tres paquetes (diagnóstico, inventario, remediación), no solo
  la de este paquete."*
- Docstring de `_run_selftest()`: *"Ejecuta `tests.selftest.run_all()`,
  que descubre y corre todos los `test_*.py` del directorio —
  compartido por los tres paquetes, no acotado a este. Mismo mecanismo
  en `diagnostico.cli`/`inventory.cli`/`remediacion.cli`."*

**Rationale**: una lista de ficheros desactualizada es exactamente el
problema que motivó este hallazgo — nombrar el mecanismo (`run_all()`
descubre todo `test_*.py`) en vez de enumerar su contenido actual
evita que el texto vuelva a quedar desactualizado la próxima vez que
se añada un test.

## Resumen de decisiones

| # | Decisión | Afecta a |
|---|---|---|
| 1 | `_extraer_contenido_y_tokens` vive en `diagnostico/deepseek.py`, sin módulo nuevo | data-model.md, tasks.md |
| 2 | Ningún test se reescribe | tasks.md |
| 3 | La función compartida lanza; el `try/except` de "nunca lanza" sigue en cada llamador | data-model.md |
| 4 | El texto de `--selftest` describe el mecanismo (`run_all()` descubre todo), no una lista de ficheros | tasks.md |
