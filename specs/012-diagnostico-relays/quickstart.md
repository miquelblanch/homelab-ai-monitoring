# Quickstart — Generalizar el Diagnóstico a los Relays

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- `socat_relays.json` real, escrito por `dump_socat_status.py` cada 5 min.
- `~/Library/Logs/dashboard-socat.log` accesible — histórico real
  desde el 2026-04-29.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo un relay sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --relay-vivo "Beszel AdGuard"
# → "episodio N congelado (Beszel AdGuard, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → relay_estado_actual.ok = true, con su desc real (incluye IPs)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el relay responde con normalidad)
```

Repetir con al menos otro de los 10 relays reales (`"Traefik LAN"`,
`"HA Shelly"`, `"Kuma UI"`...) para cubrir el caso sano de verdad.

## Escenario 3 — Relay inexistente, evidencia vacía (Edge Cases)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --relay-vivo "Relay que no existe"
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto — sin lanzar ningún error
```

## Escenario 4 — Diagnosticar en diferido contra un episodio real conocido (US2, SC-005)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --relay-historico "2026-05-24T08:00:00"
# → episodio M congelado, ventana ±180 min alrededor de ese momento —
#   cae dentro de la caída real de ~10h identificada en la investigación
#   previa (research.md §5)

PYTHONPATH=src python3 -m diagnostico.cli mostrar M
# → relay_agregado tiene varias entradas con ok < total, sin nombrar
#   ningún relay concreto

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
# → conclusión esperada: causa_probable o no_diagnosticable, pero NUNCA
#   nombrando un relay concreto como la causa (FR-006) — confirmar
#   leyendo la conclusion_texto a mano
```

**Resultado esperado**: es la primera vez en el proyecto que un
diagnóstico en diferido se contrasta contra un episodio real ya
identificado (Principio IX, SC-005), no solo contra el estado sano
actual como en 009/010/011.

## Escenario 5 — Reproducibilidad en diferido (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos —
el snapshot ya congelado nunca vuelve a tocar `dashboard-socat.log`.

## Escenario 6 — El gasto de relay cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 7 — Momento sin ningún dato en la ventana

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --relay-historico "2020-01-01T00:00:00"
# → episodio congelado igual, relay_agregado=[], componente = el
#   momento PEDIDO (2020-01-01), no la hora a la que se ejecutó
#   congelar — lección de 011 (research.md §9 de 011) aplicada aquí
#   desde el diseño, no como sorpresa (research.md §2 de 012)
```

## Autocomprobaciones (sin tocar ficheros reales ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007/009/010/011: `_relay_actual()`
contra un `socat_relays.json` de prueba, `_agregado_relays_ventana()`
contra un `dashboard-socat.log` simulado (incluido un caso con más de
`RELAY_AGREGADO_MAX_LINEAS` para comprobar el límite defensivo), y que
el prompt generalizado incluye correctamente la cláusula de "nunca
nombres un relay concreto" cuando la evidencia es agregada.
