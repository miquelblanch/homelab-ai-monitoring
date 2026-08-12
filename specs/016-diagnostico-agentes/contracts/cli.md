# Contrato — CLI del diagnóstico de episodios (generalizado a los agentes)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/015-diagnostico-hub-beszel/contracts/cli.md` — `diagnosticar`,
`mostrar` y `--selftest` no cambian. Solo `congelar` gana **una**
opción nueva — el único origen de los 9 con un solo flag, sin par
`--agente-historico` (FR-011, research.md §2/§5).

## Invocación

```
python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
python3 -m diagnostico.cli congelar --vivo CONTENEDOR
python3 -m diagnostico.cli congelar --disco-historico "LABEL@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --disco-vivo LABEL
python3 -m diagnostico.cli congelar --ha-historico "CHECK_ID@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --ha-vivo CHECK_ID
python3 -m diagnostico.cli congelar --backup-historico MOMENTO_ISO
python3 -m diagnostico.cli congelar --backup-vivo
python3 -m diagnostico.cli congelar --relay-historico MOMENTO_ISO
python3 -m diagnostico.cli congelar --relay-vivo NOMBRE
python3 -m diagnostico.cli congelar --inventario-historico "NOMBRE@EJECUCION_ID"
python3 -m diagnostico.cli congelar --inventario-vivo NOMBRE
python3 -m diagnostico.cli congelar --host-externo-historico "NOMBRE@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --host-externo-vivo NOMBRE
python3 -m diagnostico.cli congelar --hub-beszel-historico MOMENTO_ISO
python3 -m diagnostico.cli congelar --hub-beszel-vivo
python3 -m diagnostico.cli congelar --agente-vivo LABEL
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --agente-vivo LABEL` | Busca `LABEL` en `launchagents_raw.txt`; crea un `episodio` con `origen='agente'`, `en_vivo=1` (siempre), `componente=LABEL`. | FR-001, FR-002, FR-003 |

### Evidencia reunida (FR-003)

| Clave | Contenido |
|---|---|
| `agente_actual` | `{label, pid, exit_code, running, status}` — `status` ∈ `{"running", "idle", "error"}`. |

**`LABEL` inexistente en `launchagents_raw.txt`**: no es un error — el
episodio se congela igual, con `agente_actual` en `null`. El
diagnóstico resultante concluye `no_diagnosticable` por falta de
evidencia.

## Garantías (además de las ya vigentes en `specs/015-.../contracts/cli.md`)

36. **Un episodio de agente nunca lleva `es_critico=true`** (research.md §4).
37. **El gasto de un diagnóstico de agente cuenta contra el mismo
    acumulado diario** que el resto de orígenes (spec.md FR-007).
38. **Este feature nunca ejecuta ninguna acción sobre ningún agente**
    (spec.md FR-008) — solo lectura.
39. **Este feature nunca diagnostica el mecanismo de latidos de
    monitores** (spec.md FR-010) — mecanismo distinto, fuera de
    alcance.
40. **`congelar` no expone `--agente-historico`** — no existe ninguna
    evidencia histórica real que ofrecer (spec.md FR-011, research.md
    §2).

## Configuración (variables de entorno)

| Variable | Por defecto | Uso |
|---|---|---|
| `LAUNCHAGENTS_RAW` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/launchagents_raw.txt` | Única fuente de evidencia (data-model.md). |

No usa ninguna de las variables de entorno de orígenes anteriores
(`HOMELAB_DB_PATH`, `SOCAT_RELAYS_JSON`, `INVENTORY_DB_PATH`,
`BESZEL_HOSTS_JSON`, etc.) — este feature lee un único fichero de
texto plano nuevo, sin ninguna dependencia de las fuentes ya usadas
por los otros 8 orígenes.
