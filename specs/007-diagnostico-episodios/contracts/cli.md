# Contrato — CLI del diagnóstico de episodios

**Feature**: [../spec.md](../spec.md)

No hay API HTTP ni pestaña de dashboard en este feature (Assumptions:
"la superficie visible... queda fuera de este feature"). El contrato
externo es la línea de comandos.

## Invocación

```
python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
python3 -m diagnostico.cli congelar --vivo CONTENEDOR
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --historico ID` | Lee la fila `ID` de `homelab.db.restart_history` más su ventana de métricas, crea un `episodio` nuevo y congela el snapshot (FR-002). Imprime el `episodio_id` asignado. | FR-001, FR-002 |
| `congelar --vivo CONTENEDOR` | Reúne el estado actual de `CONTENEDOR` (última ventana de métricas + `docker inspect`/`docker logs`), crea un `episodio` nuevo con `en_vivo=1` y congela el snapshot. Imprime el `episodio_id`. | FR-001, FR-002 |
| `diagnosticar EPISODIO_ID` | Lee el snapshot ya congelado de `EPISODIO_ID` (nunca vuelve a consultar `homelab.db` ni Docker), comprueba el presupuesto diario (FR-010), llama a DeepSeek si hay margen, persiste un `diagnostico` nuevo con sus `hipotesis`. Puede invocarse varias veces sobre el mismo episodio — cada vez crea un `diagnostico` nuevo (para poder comprobar SC-001 comparando intentos). | FR-003 a FR-011 |
| `mostrar EPISODIO_ID` | Imprime en texto plano el episodio, todos sus intentos de diagnóstico y las hipótesis de cada uno — reconstruible sin volver a ejecutar nada (Principio VIII, US2 escenario 3). Con `--diagnostico`, filtra a un intento concreto. | FR-006 |
| `--selftest` | Autocomprobaciones de lógica pura (parseo de respuesta DeepSeek simulada, cálculo de coste, cortacircuitos de presupuesto, esquema SQLite) — nunca llama a DeepSeek ni a Docker de verdad. | Higiene operativa, mismo patrón que `inventory --selftest` |

## Garantías (independientemente del comando)

1. **Nunca ejecuta ni propone una acción correctiva sobre el homelab.**
   Ningún comando de este CLI llama a `docker restart` ni equivalente —
   no forma parte de la superficie de este feature (FR-012). Esto no es
   una opción desactivable.
2. **Nunca actúa sobre un contenedor crítico de ninguna forma**, ni
   siquiera leyendo más allá de lo que cualquier episodio no crítico
   también expondría — la única diferencia es el campo `es_critico` en el
   snapshot, que cambia el prompt (para que DeepSeek nunca redacte en
   clave de "acción a tomar"), no el mecanismo de lectura (FR-013a).
3. **`diagnosticar` nunca hace una llamada a DeepSeek que se sepa de
   antemano que supera el límite diario** — en ese caso concluye
   `no_diagnosticable` sin llamar (FR-010).
4. **Ningún comando se dispara solo.** No existe un modo "vigilar y
   lanzar automáticamente" en este CLI — cada invocación la decide
   Miquel explícitamente (FR-015).
5. **`diagnosticar` nunca vuelve a consultar el estado en vivo del
   homelab** — toda su entrada es el `snapshot_evidencia` ya persistido
   en el momento de `congelar` (FR-002, Principio XI).

## Salida por stdout

Texto plano legible, mismo estilo que `inventory.cli`: `congelar` imprime
una línea con el `episodio_id` asignado y un resumen de qué se congeló;
`diagnosticar` imprime la conclusión final y el conteo de hipótesis
consideradas; `mostrar` imprime el episodio completo en un formato
legible pegable en un mensaje sin reformatear. No hay otro programa que
consuma esta salida — no es un contrato formal de formato, solo de
comportamiento.

## Configuración (variables de entorno)

| Variable | Por defecto | Efecto |
|---|---|---|
| `DIAGNOSTICO_DB_PATH` | `.../homelab-orchestrator/data/diagnostico.db` | Ruta de la base propia de este feature (research.md §4). |
| `DIAGNOSTICO_LIMITE_EUR_DIA` | `5.0` | Límite de gasto diario (FR-010, Assumptions). |
| `DIAGNOSTICO_DEEPSEEK_MODEL` | `deepseek-v4-flash` | Identificador de modelo DeepSeek a usar (research.md §3; elegido por Miquel el 2026-08-10 tras validar el feature con él). |
| `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` | `2000` | Límite duro de tokens de salida enviado como `max_tokens` a la API — también es el número exacto que usa el cortacircuitos de gasto para estimar el coste antes de llamar (research.md §6, hallazgo B1 de `/speckit-analyze`). |
| `HOMELAB_SCRIPTS_DIR` | `/Volumes/FastData/homelab/scripts` | Mismo mecanismo que `inventory` para localizar `homelab_secrets.py`/`docker_monitor.py` (research.md §7). |
| `HOMELAB_DB_PATH` | `.../homelab-orchestrator/data/homelab.db` | Ruta de la base de solo lectura de `restart_history`/`container_metrics`/`disk_metrics` (research.md §4/§5) — sobreescribible para que los selftests (T013) usen un fichero temporal en vez de la base real. |
