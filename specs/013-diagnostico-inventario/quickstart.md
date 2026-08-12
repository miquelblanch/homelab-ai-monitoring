# Quickstart — Generalizar el Diagnóstico al Inventario de Cobertura

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- `inventario.db` real, con al menos las ejecuciones que ya existen en
  producción (81 al momento de escribir este documento).

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo el inventario sin ninguna brecha activa de los 5 tipos en alcance (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-vivo "Agente Hermes/Bautista"
# → "episodio N congelado (Agente Hermes/Bautista, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → inventario_hallazgo.es_brecha = false (hoy sano), inventario_brecha = null

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (no hay ninguna brecha que explicar)
```

Comprobar antes con `python3 -m inventory.cli --gaps` que, en efecto,
no hay ninguna brecha activa de los 5 tipos en alcance (solo
`condicion_incumplida` de `entidad_ha`, fuera de alcance) — si la
apareciera una brecha real entre tanto, repetir con un componente sano
distinto.

## Escenario 3 — Componente inexistente, evidencia vacía (Edge Cases)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-vivo "Componente que no existe"
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto — sin lanzar ningún error
```

## Escenario 4 — Diagnosticar en diferido contra una brecha real conocida (US2, SC-005)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-historico "Agente Hermes/Bautista@19"
# → episodio M congelado, componente=Agente Hermes/Bautista

PYTHONPATH=src python3 -m diagnostico.cli mostrar M
# → inventario_brecha.tipo = no_llega_a_dashboard, primera_ejecucion_id = 3
# → inventario_comparacion.ejecucion_previa_id = 2 (research.md §10) —
#   NO 18, aunque la ejecución pedida sea la #19

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
# → conclusión esperada: causa_probable o no_diagnosticable honesto
```

Repetir con al menos otra de las tres brechas reales conocidas:

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-historico "Host de Uptime Kuma@28"
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-historico "Recordatorios de Nextcloud (Tareas/Calendario)@31"
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-historico "Beszel (hub)@52"
```

**Resultado esperado**: igual que en 012, es la validación en diferido
contra episodios reales ya resueltos (Principio IX, SC-005), no solo
contra el estado sano actual como en 009/010/011.

## Escenario 5 — Reproducibilidad en diferido (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos —
el snapshot ya congelado nunca vuelve a consultar `inventario.db`.

## Escenario 6 — El gasto de inventario cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 7 — Brecha de tipo `condicion_incumplida`, rechazada antes de congelar (FR-010)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-vivo "$(python3 -m inventory.cli --gaps | grep condicion_incumplida | head -1 | sed -E "s/.*\] //; s/ —.*//")"
# → código de salida 1, mensaje en stderr: brecha fuera de alcance
#   (FR-010) — ningún episodio se crea
```

## Escenario 8 — Ejecución inexistente

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --inventario-historico "Agente Hermes/Bautista@999999"
# → episodio congelado igual, inventario_hallazgo/brecha/comparacion en
#   null — componente = el NOMBRE pedido, no un error
```

## Autocomprobaciones (sin tocar `inventario.db` real ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007/009/010/011/012:
`congelar_inventario_vivo`/`congelar_inventario_historico` contra una
`inventario.db` de prueba en un fichero temporal (nunca la real, mismo
patrón que `test_evidencia.py` ya usa para `homelab.db`), el rechazo en
código de `condicion_incumplida`, el límite defensivo de
`INVENTARIO_COMPARACION_MAX_ENTRADAS`, y que el prompt generalizado
incluye correctamente la mención al sexto origen.
