# Quickstart — validar el refactor de `evidencia`

Guía de validación end-to-end. No sustituye a `tasks.md` (que detalla cada
paso de implementación) — esto es lo que se ejecuta para comprobar que el
resultado cumple `spec.md`, apoyándose en `data-model.md` y
`contracts/fachada-evidencia.md`.

## Prerrequisitos

- Repo en `023-evidencia-por-origen`, cambios de esta feature aplicados.
- `homelab.db` accesible en la ruta por defecto (mismo requisito que hoy
  para correr el `--selftest` completo — sin esto, algunos casos de
  `test_evidencia_*.py` que ya dependían de datos reales seguirán
  necesitándolo igual que antes; el refactor no cambia esa dependencia).

## 1. Línea base — capturar el resultado ANTES del cambio

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli --selftest 2>&1 | tail -5
PYTHONPATH=src python3 -m remediacion.cli --selftest 2>&1 | tail -5
```

Anotar el recuento exacto de aserciones y fallos (hoy: 595 aserciones, 0
fallos, en los tres paquetes — ver `REFACTOR-evidencia.md`).

## 2. Tras aplicar el refactor — mismo resultado exacto

```bash
PYTHONPATH=src python3 -m diagnostico.cli --selftest 2>&1 | tail -5
PYTHONPATH=src python3 -m inventory.cli --selftest 2>&1 | tail -5
PYTHONPATH=src python3 -m remediacion.cli --selftest 2>&1 | tail -5
```

**Criterio de éxito (SC-002)**: mismo recuento de aserciones que en el paso
1, cero fallos nuevos. Si el recuento cambia, algo se perdió o se duplicó al
mover los tests — no es aceptable "menos aserciones pero todo en verde".

## 3. Confirmar que un origen se puede revisar sin abrir los otros nueve (SC-003)

```bash
wc -l src/diagnostico/evidencia/*.py
```

Cada módulo de origen debe poder leerse solo (por ejemplo `disco.py`) sin
necesidad de abrir `ha.py`, `backup.py`, etc. — verificación manual, no
automatizable: abrir `disco.py` y confirmar que no faltan símbolos sin
importar explícitamente desde `_compartido.py` o desde su propio test.

## 4. Confirmar que la fachada no rompió a los tres consumidores reales (FR-002, SC-004)

```bash
PYTHONPATH=src python3 - <<'EOF'
from diagnostico import evidencia
import inspect

# Los 18 nombres que usa diagnostico/cli.py, más los 2 que usa deepseek.py
esperados = [
    "congelar_historico", "congelar_vivo",
    "congelar_disco_vivo", "congelar_disco_historico",
    "congelar_ha_vivo", "congelar_ha_historico",
    "congelar_backup_vivo", "congelar_backup_historico",
    "congelar_relay_vivo", "congelar_relay_historico",
    "listar_nombres_relay", "nombres_relay_evidenciados",
    "congelar_inventario_vivo", "congelar_inventario_historico",
    "congelar_host_externo_vivo", "congelar_host_externo_historico",
    "congelar_hub_beszel_vivo", "congelar_hub_beszel_historico",
    "congelar_agente_vivo", "congelar_latido_vivo",
]
faltan = [n for n in esperados if not hasattr(evidencia, n)]
assert not faltan, f"la fachada perdió: {faltan}"
print(f"OK — {len(esperados)} nombres de la fachada presentes")
EOF
```

## 5. Confirmar que un origen nuevo no toca a los existentes (SC-001, prueba de humo)

No forma parte de esta feature crear un origen real — la verificación es
estructural: `git diff --stat` del PR de esta feature no debe tocar, dentro
de `src/diagnostico/evidencia/`, más de un módulo de origen a la vez salvo
`_compartido.py` y `__init__.py` (que sí cambian una vez, al crear la
fachada). Si una tarea posterior añade un origen 011 y el diff toca
`disco.py` o `ha.py` sin motivo, es una señal de que el aislamiento no se
sostuvo.
