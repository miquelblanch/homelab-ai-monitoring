# Quickstart — Generalizar el Diagnóstico a Discos

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada (ya lo
  está desde la validación real de 007).
- `homelab.db` accesible en la ruta por defecto, con la tabla
  `disk_metrics` real (ya la tiene — 13.992 filas al escribir este
  documento).

## Escenario 1 — Migración de esquema no rompe los episodios ya existentes

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 1
# → debe seguir imprimiendo el episodio 1 (beszel, histórico) exactamente
#   igual que antes de este feature — la migración no debe alterar
#   ninguna fila ya escrita por 007
```

**Resultado esperado**: los 14 episodios ya persistidos por 007 se
siguen leyendo con normalidad, ahora con `origen='contenedor'` asignado
automáticamente por la migración (research.md §1).

## Escenario 2 — Diagnosticar un disco sano en vivo (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --disco-vivo FastData
# → "episodio N congelado (FastData, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (los tres discos reales están hoy
#   muy por debajo de cualquier umbral de aviso)
```

**Resultado esperado**: el motor reúne evidencia real de uso de disco
(no de ningún contenedor) y concluye honestamente que no hay nada que
diagnosticar — sin inventar una causa. Repetir con `Storage` y
`Sistema` para los tres discos reales (SC-004).

## Escenario 3 — Reproducibilidad en diferido (US2, SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --disco-historico "FastData@$(date -u -v-1H +%Y-%m-%dT%H:%M:%S)"
# → episodio M congelado, ventana de ±30 min alrededor de ese momento

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: los dos `diagnosticar` de arriba concuerdan en
`conclusion_tipo` (mismo criterio que SC-001 de 007/008).

## Escenario 4 — El gasto de disco cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado" — el límite
#   ya consumido por diagnósticos de contenedor (si los hubo hoy)
#   también bloquea uno de disco
```

**Resultado esperado**: ninguna llamada nueva a DeepSeek — el
cortacircuitos no distingue el origen del episodio.

## Autocomprobaciones (sin tocar DeepSeek/Docker/homelab.db reales)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007: la migración de esquema
idempotente (`test_store.py`), `congelar_disco_vivo`/
`congelar_disco_historico` contra una base `homelab.db` de prueba
(`test_evidencia.py`), y que el prompt generalizado sigue incluyendo
correctamente la cláusula de "sin acción" cuando corresponde
(`test_deepseek.py`).
