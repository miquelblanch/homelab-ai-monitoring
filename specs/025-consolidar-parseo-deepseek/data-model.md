# Phase 1 — Data Model: Parseo de DeepSeek Compartido y Autocomprobación Sincera

No hay modelo de datos nuevo. Mapea las entidades de `spec.md`
(Extracción de respuesta DeepSeek, Pregunta a DeepSeek, Validación
posterior) a los cambios exactos por fichero.

## Extracción de respuesta DeepSeek → `diagnostico/deepseek.py`

| Elemento | Antes | Después |
|---|---|---|
| Extracción de `content`/`reasoning_content` + tokens | Duplicada en `parsear_respuesta` (deepseek.py) y `parsear_respuesta_remediacion` (deepseek_contenedores.py) | Única, en `_extraer_contenido_y_tokens()` (deepseek.py) |
| `parsear_respuesta` | Extrae inline | Llama a `_extraer_contenido_y_tokens()`, valida `conclusion_tipo`/`hipotesis` como antes |
| `parsear_respuesta_remediacion` | Extrae inline | Importa y llama a `diagnostico.deepseek._extraer_contenido_y_tokens()`, valida `accion_aplica` como antes |

## Pregunta a DeepSeek — sin cambios

| Elemento | Dónde sigue |
|---|---|
| `construir_prompt` (causa probable, pregunta abierta) | `diagnostico/deepseek.py`, sin tocar |
| `construir_prompt_remediacion` (acción aplicable, pregunta cerrada) | `remediacion/deepseek_contenedores.py`, sin tocar |

## Validación posterior — sin cambios

| Elemento | Dónde sigue |
|---|---|
| Validación de `conclusion_tipo`/`hipotesis`/`CONCLUSION_TIPOS`/`DESENLACES` | `parsear_respuesta`, dentro del mismo `try` que ahora empieza llamando a la extracción compartida |
| Validación de `accion_aplica`/`TIPOS_ACCION` (`_accion_valida`, `_validar_decision`) | `deepseek_contenedores.py`, sin tocar |

## Autocomprobación — `diagnostico/cli.py`, `inventory/cli.py`, `remediacion/cli.py`

| Fichero | Cambia |
|---|---|
| `diagnostico/cli.py` | Texto de `--help` de `--selftest`; docstring de `_run_selftest()` (quita la lista de 6 ficheros) |
| `inventory/cli.py` | Texto de `--help` de `--selftest`; docstring de `_run_selftest()` (quita la lista de 4 ficheros) |
| `remediacion/cli.py` | Texto de `--help` de `--selftest`; añade docstring a `_run_selftest()` (hoy no tiene ninguno) |

Ningún cambio de comportamiento en ninguno de los tres — `_run_selftest()` sigue llamando a `run_all()` exactamente igual.
