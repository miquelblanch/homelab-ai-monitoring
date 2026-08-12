# Quickstart — Generalizar el Diagnóstico al Hub de Beszel

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- `beszel_hosts.json` real, con `hub_systems` escrito por
  `beszel_hosts_monitor.py` cada 5 min.
- Docker disponible localmente, con acceso de lectura al volumen
  `beszel_hub_data`.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
```

## Escenario 2 — Diagnosticar en vivo el hub sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --hub-beszel-vivo
# → "episodio N congelado (<momento ISO>, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → hub_beszel_actual.sano = true (si al menos un sistema reporta fresco)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el hub sigue vigilando algo)
```

## Escenario 3 — Diagnosticar en diferido un momento sin ninguna avería conocida (US2, SC-005)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --hub-beszel-historico "2026-08-02T12:00:00"
# → episodio M congelado — dentro de la avería real de 014, pero
#   Mac Mini Server siguió reportando durante toda esa ventana
#   (research.md §6), así que NO se espera todos_sin_muestras=true

PYTHONPATH=src python3 -m diagnostico.cli mostrar M
# → hub_beszel_stats.todos_sin_muestras = false (al menos Mac Mini
#   Server tiene muestras), aunque AdGuardHome/UptimeKuma puedan
#   tener total_muestras=0 — ausencia PARCIAL, no total

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
# → conclusión esperada: no_diagnosticable honesto (SC-005) — sin
#   presentar la ausencia parcial como si el hub entero estuviera
#   caído (FR-006a)
```

**Resultado esperado**: a diferencia de 012/013/014, este feature
arranca sin ningún episodio real conocido de "hub caído" — la
validación se apoya en que el mecanismo distingue correctamente
ausencia parcial de ausencia total, no en reproducir una avería real
(research.md §6).

## Escenario 4 — Reproducibilidad en diferido (SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: mismo `conclusion_tipo` en los dos intentos.

## Escenario 5 — El gasto del hub cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado"
```

## Escenario 6 — Momento sin ningún dato en la ventana, fuera de cualquier retención real

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --hub-beszel-historico "2020-01-01T00:00:00"
# → episodio congelado igual, hub_beszel_stats.todos_sin_muestras=true
#   (ningún sistema tiene datos tan antiguos) — componente = el
#   momento pedido (research.md §2)
```

## Autocomprobaciones (sin tocar Docker real ni DeepSeek)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007-014: `_hub_beszel_actual()`
contra un `beszel_hosts.json` de prueba con varias combinaciones de
antigüedad (todos frescos, uno caducado, todos caducados, sin
sistemas), `_resumen_por_sistema()` contra filas simuladas (incluido
el caso `LEFT JOIN` con sistemas sin ninguna muestra), y que el prompt
generalizado incluye correctamente la cláusula FR-006a propia de este
origen.
