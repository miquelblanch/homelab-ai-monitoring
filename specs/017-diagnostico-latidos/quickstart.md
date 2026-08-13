# Quickstart — Generalizar el Diagnóstico a los Latidos de Monitores

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- Al menos un `<job>.json` real en
  `/Volumes/FastData/homelab/data/heartbeats/`, escrito por
  `heartbeat.py` desde los distintos monitores.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo un latido sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --latido-vivo docker-monitor
# → "episodio N congelado (docker-monitor, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → latido_actual.ok = true (si el monitor real ha latido dentro de su
#   umbral)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el latido está a tiempo)
```

Repetir con al menos otro job real (`ha-monitor`, `verify-backups`...)
para cubrir el caso sano de verdad.

## Escenario 3 — Job inexistente entre los 8, evidencia vacía (Edge Cases)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --latido-vivo "job-que-no-existe"
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto — sin lanzar ningún error
```

## Escenario 4 — Reproducibilidad (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos —
el snapshot ya congelado nunca vuelve a leer `<job>.json`.

## Escenario 5 — El gasto de latido cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 6 — Sin `--latido-historico` (FR-011)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --help | grep latido
# → solo aparece --latido-vivo, ningún --latido-historico
```

## Autocomprobaciones (sin tocar los ficheros reales ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007-016: `_latido_actual()` contra
ficheros `<job>.json` de prueba (latido reciente y sano, latido rancio,
fichero ausente, `job` inexistente entre los 8, `ok` calculado solo por
edad incluso con `status: "error"` — research.md §3), y que el prompt
generalizado incluye correctamente la mención al décimo y último
origen.
