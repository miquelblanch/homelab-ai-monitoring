# Quickstart — validar el parseo compartido y el texto corregido

## 1. Línea base

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m inventory.cli --selftest 2>&1 | tail -3
PYTHONPATH=src python3 -m remediacion.cli --selftest 2>&1 | tail -3
```

## 2. Tras el cambio — mismo resultado exacto

Repetir los tres comandos — mismo recuento (SC-002), sin haber tocado
ningún fichero de test.

## 3. Confirmar que la extracción compartida se usa de verdad

```bash
PYTHONPATH=src python3 -c "
from diagnostico import deepseek
from remediacion import deepseek_contenedores
import inspect
src_rem = inspect.getsource(deepseek_contenedores.parsear_respuesta_remediacion)
assert '_extraer_contenido_y_tokens' in src_rem, 'remediacion no usa la función compartida'
print('OK — remediacion llama a la extracción compartida de diagnostico')
"
```

## 4. Confirmar el respaldo `reasoning_content` en los dos consumidores

```bash
PYTHONPATH=src python3 -c "
from diagnostico.deepseek import _extraer_contenido_y_tokens
respuesta = {
    'choices': [{'message': {'content': '', 'reasoning_content': '{\"x\": 1}'}}],
    'usage': {'prompt_tokens': 10, 'completion_tokens': 5},
}
parsed, ti, ts = _extraer_contenido_y_tokens(respuesta)
assert parsed == {'x': 1} and ti == 10 and ts == 5
print('OK — respaldo reasoning_content funciona en la función compartida')
"
```

## 5. Confirmar el texto de `--selftest`

```bash
PYTHONPATH=src python3 -m diagnostico.cli --help | grep -A1 "\-\-selftest"
PYTHONPATH=src python3 -m inventory.cli --help | grep -A1 "\-\-selftest"
PYTHONPATH=src python3 -m remediacion.cli --help | grep -A1 "\-\-selftest"
```

Los tres deben mencionar la suite completa compartida de los tres
paquetes — ninguno debe sugerir un alcance acotado a sí mismo.
