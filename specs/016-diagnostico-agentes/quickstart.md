# Quickstart — Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- `launchagents_raw.txt` real, escrito por `dump_launchagents.sh` cada
  5 min.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo un agente sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --agente-vivo "amsterdam9.morning-report"
# → "episodio N congelado (amsterdam9.morning-report, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → agente_actual.status = "idle" o "running" (nunca "error" para un
#   agente sano)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el agente está sano)
```

Repetir con al menos otro agente real (`amsterdam9.docker-monitor`,
`ai.hermes.gateway-bautista`...) para cubrir el caso sano de verdad.

## Escenario 3 — Agente inexistente, evidencia vacía (Edge Cases)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --agente-vivo "agente.que.no.existe"
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto — sin lanzar ningún error
```

## Escenario 4 — Reproducibilidad (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos —
el snapshot ya congelado nunca vuelve a leer `launchagents_raw.txt`.

## Escenario 5 — El gasto de agente cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 6 — Sin `--agente-historico` (FR-011)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --help | grep agente
# → solo aparece --agente-vivo, ningún --agente-historico
```

## Autocomprobaciones (sin tocar el fichero real ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007-015: `_agente_actual()` contra
un `launchagents_raw.txt` de prueba (agente en ejecución, agente
inactivo con código de salida normal, agente inactivo con código de
salida anómalo, `label` inexistente), y que el prompt generalizado
incluye correctamente la mención al noveno y último origen.
