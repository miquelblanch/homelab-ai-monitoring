# Quickstart — Generalizar el Diagnóstico a Home Assistant

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada (ya lo
  está desde la validación real de 007).
- `.secrets/ha.env` con `HA_URL`/`HA_TOKEN` ya configuradas (ya lo está
  — es la misma credencial que usa `ha_monitor.py` en producción).
- `homelab.db` accesible en la ruta por defecto (sin cambios respecto a
  007/009 — este feature no añade lecturas nuevas de `homelab.db`).
- Home Assistant accesible (`http://192.168.4.87:8123` por defecto) y
  el contenedor `homeassistant` corriendo.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 1
# → debe seguir imprimiendo el episodio 1 exactamente igual que antes
#   de este feature — a diferencia de 009, este feature no toca el
#   esquema de diagnostico.db (research.md §1), así que no hay nada
#   que verificar sobre datos ya persistidos más allá de que sigan ahí.
```

## Escenario 2 — Diagnosticar en vivo un check de entidad sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --ha-vivo z2m_bridge
# → "episodio N congelado (z2m_bridge, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el bridge de Zigbee2MQTT está
#   conectado hoy — nada que explicar)
```

**Resultado esperado**: el motor reúne evidencia real del historial de
la entidad (no de ningún contenedor ni disco) y concluye honestamente
que no hay nada que diagnosticar. Repetir con otro check de entidad
sano (por ejemplo `sal_nivel` o cualquier `bateria_interruptor_*`) para
cubrir los cuatro subtipos de `entity_*` (SC-004).

## Escenario 3 — Diagnosticar en vivo el check `ha_api` (evidencia sin entidad)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --ha-vivo ha_api
PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → el episodio no tiene "ha_history" (null) — su evidencia es
#   "docker_logs_tail" del contenedor homeassistant (Clarifications
#   2026-08-12, FR-003)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (la API responde con normalidad hoy)
```

**Resultado esperado**: confirma que el gap encontrado en
`/speckit-clarify` (el check `ha_api` no encajaba en ninguna de las dos
categorías de evidencia originales) queda cerrado — el motor lo
diagnostica con la misma honestidad que cualquier otro check.

## Escenario 4 — Diagnosticar en vivo el check del recorder corrupto (US2)

Simular una corrupción (mismo mecanismo ya usado para probar el check
de `ha_monitor.py`, ver spec.md Independent Test de User Story 2):

```bash
docker exec homeassistant sh -c 'touch /recorder/home-assistant_v2.db.corrupt.20260812'

PYTHONPATH=src python3 -m diagnostico.cli congelar --ha-vivo ha_recorder_corrupto
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: causa_probable, con al menos una hipótesis que cita el
#   fichero de corrupción encontrado

docker exec homeassistant sh -c 'rm /recorder/home-assistant_v2.db.corrupt.20260812'
```

**Resultado esperado**: la evidencia congelada (`mostrar N`) incluye
`ha_recorder_corrupt_files` con el nombre del fichero simulado y
`docker_logs_tail` con los logs recientes del contenedor.

## Escenario 5 — Reproducibilidad en diferido, check de entidad (US3, SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --ha-historico "z2m_bridge@$(date -v-2H +%Y-%m-%dT%H:%M:%S)"
# → episodio M congelado, ventana ±12h alrededor de ese momento

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: los dos `diagnosticar` de arriba concuerdan en
`conclusion_tipo` (mismo criterio que SC-001 de 007/009) — el snapshot
ya congelado nunca vuelve a tocar la API de HA (FR-002).

## Escenario 6 — El gasto de HA cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado" — el límite
#   ya consumido por diagnósticos de contenedor/disco (si los hubo hoy)
#   también bloquea uno de HA
```

## Escenario 7 — La cerradura queda fuera de alcance (FR-010)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --ha-vivo bateria_cerradura
# → error explícito, código de salida distinto de 0, ningún episodio creado
```

**Resultado esperado**: a diferencia de un `CHECK_ID` simplemente
inexistente (que sí crea un episodio con evidencia vacía), los tres
checks de la cerradura (`cerradura_up`, `bateria_cerradura`,
`bateria_critica_cerradura`) se rechazan antes de congelar nada
(research.md §7).

## Autocomprobaciones (sin tocar DeepSeek/HA/Docker/homelab.db reales)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007/009: resolución de `check_id`
contra un `ha_monitor.CHECKS` de prueba para los tres tipos de
evidencia (`test_evidencia.py`), el bloqueo de los tres checks de
cerradura, y que el prompt generalizado sigue incluyendo correctamente
la evidencia de HA en el JSON enviado (`test_deepseek.py`) — sin
ninguna llamada real a la API de HA ni a DeepSeek.
