# Quickstart — Diagnóstico de Episodios

**Feature**: [spec.md](./spec.md) · Contrato: [contracts/cli.md](./contracts/cli.md) ·
Modelo de datos: [data-model.md](./data-model.md)

## Prerrequisitos

- Python 3.11, sin dependencias adicionales que instalar (research.md §1/§3).
- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` en el homelab real (fuera
  de este repo) — sin él, `diagnosticar` concluye siempre
  `no_diagnosticable` con motivo "sin credencial DEEPSEEK_API_KEY
  configurada" (mismo principio "a prueba de fallos" que
  `_homelab_bridge.py` ya sigue para Telegram). **Estado al implementar
  (2026-08-10): ese fichero todavía no existe** — verificado contra
  `/Volumes/FastData/homelab/.secrets/` — así que los Escenarios 1, 2 y 4
  de más abajo no se han podido ejecutar contra DeepSeek real todavía.
- `homelab.db` accesible en la ruta por defecto (o `HOMELAB_SCRIPTS_DIR`/
  rutas equivalentes si se ejecuta fuera del Mac Mini) para el caso
  `congelar --historico`.

## Escenario 1 — Reproducibilidad en diferido (US1, SC-001)

Validar que diagnosticar dos veces el mismo episodio histórico produce la
misma conclusión.

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
python3 -m diagnostico.cli congelar --historico 16   # un reinicio real de beszel
# → "episodio 1 congelado (beszel, histórico, restart_history #16)"

python3 -m diagnostico.cli diagnosticar 1
# → conclusión #1: causa_probable | no_diagnosticable, N hipótesis consideradas

python3 -m diagnostico.cli diagnosticar 1
# → conclusión #2: debe coincidir con la #1 en conclusion_tipo (no
#   necesariamente en el número o el texto de las hipótesis — ver
#   research.md §2, aclarado el 2026-08-11 tras evidencia real de que
#   el número de hipótesis puede variar entre llamadas)

python3 -m diagnostico.cli mostrar 1
# → episodio + ambos intentos de diagnóstico, con sus hipótesis, legible
#   sin volver a ejecutar nada (Principio VIII)
```

**Resultado esperado**: los dos `diagnosticar` de arriba concuerdan en
`conclusion_tipo` (SC-001) — no se exige que coincida el número ni el
texto de las hipótesis intermedias.

## Escenario 2 — Validación contra la línea base de `beszel` (FR-011, SC-002)

Línea base fijada el 2026-08-11 (hallazgo U2 de `/speckit-analyze`): de
los 6 episodios de referencia, 3 (`restart_history_id` 16, 17, 25) no
tienen evidencia de métricas — el agente debe llegar a
`no_diagnosticable` en esos 3, no inventar una causa.

```bash
for id in 16 17 25; do
  episodio=$(python3 -m diagnostico.cli congelar --historico "$id" | grep -o 'episodio [0-9]*' | cut -d' ' -f2)
  python3 -m diagnostico.cli diagnosticar "$episodio"
done
```

**Resultado esperado**: los tres intentos concluyen `no_diagnosticable`
— ninguno presenta una causa sin evidencia real que la respalde (FR-007).
Ya confirmado en `tasks.md` T030 con una llamada real a DeepSeek (6/6
episodios de referencia, incluidos estos 3, concluyeron
`no_diagnosticable`); este escenario reproduce esa validación.

## Escenario 3 — Cortacircuitos de gasto diario (US3, SC-004)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 python3 -m diagnostico.cli diagnosticar 1
# → "no_diagnosticable: límite de gasto diario alcanzado (0.00€ / 0.00€)"
# → NO debe haber ninguna llamada HTTP saliente a DeepSeek (comprobable
#   sin credencial configurada: el resultado es idéntico a "sin credencial")
```

**Resultado esperado**: ninguna llamada a la API, coste registrado
`0.0`, conclusión explícita de que no se pudo diagnosticar sin superar el
límite — nunca fuerza la llamada (FR-010).

## Escenario 4 — Contenedor crítico, solo diagnóstico (US1 escenario 4, FR-013/013a)

```bash
python3 -m diagnostico.cli congelar --vivo homeassistant
# → "episodio 2 congelado (homeassistant, en vivo, crítico=sí)"
python3 -m diagnostico.cli diagnosticar 2
python3 -m diagnostico.cli mostrar 2
```

**Resultado esperado**: el registro tiene el mismo rigor (varias
hipótesis, contraste, conclusión) que cualquier episodio no crítico — y
en ningún punto de `conclusion_texto` ni de `hipotesis.descripcion`
aparece una acción propuesta o ejecutada sobre `homeassistant`. Revisar
esto es manual en esta fase (no hay un check automático de "el texto no
sugiere una acción" en v1) — parte del propio prompt a DeepSeek instruye
explícitamente no proponer acciones para episodios `es_critico=1`
(research.md §7), y la revisión humana del texto generado es la
verificación de que esa instrucción se cumplió.

## Autocomprobaciones (sin tocar DeepSeek/Docker/homelab.db reales)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre (test_evidencia, test_deepseek, test_gasto, test_store,
test_reproducibilidad, test_baseline_beszel, data-model.md): parseo de
una respuesta DeepSeek simulada, cálculo de coste a partir de tokens
fijos, cortacircuitos de presupuesto en los tres casos (por debajo / al
límite / por encima), el invariante FR-007 (`causa_probable` exige
**exactamente una** hipótesis `confirmada` — ni cero ni dos o más,
corregido el 2026-08-11; `no_diagnosticable` exige que ninguna lo esté),
la parte determinista de la reproducibilidad (SC-001) y la línea base
fija de `beszel` (SC-002) contra una respuesta DeepSeek simulada.
