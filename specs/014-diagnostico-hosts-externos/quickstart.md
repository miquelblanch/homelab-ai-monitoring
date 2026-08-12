# Quickstart — Generalizar el Diagnóstico a los Hosts Externos

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- `beszel_hosts.json` real, escrito por `beszel_hosts_monitor.py` cada
  5 min, y su latido en `data/heartbeats/beszel-hosts.json`.
- Docker disponible localmente, con acceso de lectura al volumen
  `beszel_hub_data` (mismo acceso que ya usa
  `scripts/beszel_hosts_monitor.py` en producción).

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo un host sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --host-externo-vivo "Host de Uptime Kuma"
# → "episodio N congelado (Host de Uptime Kuma, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → host_externo_actual.status = "arriba" (si Beszel lo reporta sano ahora)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el host responde con normalidad)
```

Repetir con "Host de AdGuard Home (DNS primario)" para cubrir el
segundo host real.

## Escenario 3 — Host inexistente, evidencia vacía (Edge Cases)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --host-externo-vivo "Host que no existe"
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto — sin lanzar ningún error
```

## Escenario 4 — Diagnosticar en diferido contra la avería real conocida (US2, SC-005)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --host-externo-historico "Host de Uptime Kuma@2026-08-02T12:00:00"
# → episodio M congelado — cae dentro del hueco real de 8 días
#   (2026-07-30 a 2026-08-07) causado por el routing de contenedores
#   roto, ya documentado en el CLAUDE.md general

PYTHONPATH=src python3 -m diagnostico.cli mostrar M
# → host_externo_stats.total_muestras = 0

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
# → conclusión esperada: causa_probable o no_diagnosticable, pero
#   NUNCA presentando la ausencia de muestras como "host caído
#   confirmado" sin más (FR-006a) — confirmar leyendo la
#   conclusion_texto a mano
```

Repetir con "Host de AdGuard Home (DNS primario)" para el segundo host
real dentro de la misma avería.

## Escenario 5 — Reproducibilidad en diferido (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos —
el snapshot ya congelado nunca vuelve a consultar el hub de Beszel.

## Escenario 6 — El gasto de host externo cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 7 — Momento sin ningún dato en la ventana, fuera de cualquier avería conocida

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --host-externo-historico "Host de Uptime Kuma@2020-01-01T00:00:00"
# → episodio congelado igual, host_externo_stats.total_muestras=0,
#   componente = "Host de Uptime Kuma" (nunca incluye el momento —
#   research.md §2)
```

## Autocomprobaciones (sin tocar Docker real ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007-013: `_host_externo_actual()`
contra un `beszel_hosts.json`/latido de prueba (fresco, caducado,
nombre inexistente), `_a_utc_madrid()` con casos de invierno y verano
(CET/CEST), `_resumen_system_stats()` contra filas simuladas, y que el
prompt generalizado incluye correctamente la cláusula de "nunca
presentes la ausencia de muestras como caída confirmada" cuando la
evidencia es de diferido.
