# Contrato — CLI del diagnóstico de episodios (generalizado a discos)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de `specs/007-diagnostico-episodios/contracts/cli.md`
— `diagnosticar`, `mostrar` y `--selftest` no cambian (ya son agnósticos
al origen del episodio). Solo `congelar` gana dos opciones nuevas.

## Invocación

```
python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
python3 -m diagnostico.cli congelar --vivo CONTENEDOR
python3 -m diagnostico.cli congelar --disco-historico "LABEL@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --disco-vivo LABEL
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --disco-historico "LABEL@MOMENTO_ISO"` | Lee `disk_metrics` en la ventana ±30 min alrededor de `MOMENTO_ISO` para el disco `LABEL`, crea un `episodio` con `origen='disco'`, `en_vivo=0` y congela el snapshot. Imprime el `episodio_id` asignado. | FR-001, FR-002 |
| `congelar --disco-vivo LABEL` | Reúne las últimas muestras disponibles de `disk_metrics` para `LABEL`, crea un `episodio` con `origen='disco'`, `en_vivo=1` y congela el snapshot. Imprime el `episodio_id`. | FR-001, FR-002 |

`LABEL` es uno de `"FastData"`, `"Storage"`, `"Sistema"` (research.md
§2) — mismos nombres que ya usa el dashboard. `MOMENTO_ISO` es una
fecha/hora ISO 8601; no existe un identificador de fila como
`RESTART_HISTORY_ID` para discos (spec.md, Assumptions) — el momento
mismo es el identificador del episodio histórico. **Se interpreta como
hora local sin marca de zona** (research.md §3) — misma convención que
`disk_metrics.timestamp`; nunca se convierte a UTC ni se le añade
ningún offset antes de comparar.

## Garantías (además de las ya vigentes en `specs/007-.../contracts/cli.md`)

6. **Un episodio de disco nunca lleva `es_critico=true`** (research.md
   §4) — el concepto no existe para discos en este feature.
7. **El gasto de un diagnóstico de disco cuenta contra el mismo
   acumulado diario que ya protege a los de contenedor** (spec.md
   FR-007) — `diagnosticar` no distingue el origen del episodio al
   aplicar el cortacircuitos de gasto.
8. **Si el disco diagnosticado es el mismo que aloja `diagnostico.db`
   y no queda espacio para escribir, el intento se pierde sin ningún
   mecanismo de respaldo** (spec.md, Clarifications) — riesgo aceptado
   explícitamente, no un comportamiento a corregir.

## Configuración (variables de entorno)

Sin variables nuevas — reutiliza exactamente `DIAGNOSTICO_DB_PATH`,
`DIAGNOSTICO_LIMITE_EUR_DIA`, `DIAGNOSTICO_DEEPSEEK_MODEL`,
`DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`, `HOMELAB_SCRIPTS_DIR`,
`HOMELAB_DB_PATH` ya definidas en `specs/007-.../contracts/cli.md`.
