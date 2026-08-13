# Contrato — CLI del diagnóstico de episodios (generalizado a los latidos de monitores)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/016-diagnostico-agentes/contracts/cli.md` — `diagnosticar`,
`mostrar` y `--selftest` no cambian. Solo `congelar` gana **una**
opción nueva — segundo origen de los 10 con un solo flag, sin par
`--latido-historico` (FR-011, research.md §2/§5).

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
python3 -m diagnostico.cli congelar --latido-vivo JOB
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --latido-vivo JOB` | Busca `JOB` entre los 8 de `MONITOR_JOBS`; lee su `<job>.json`; crea un `episodio` con `origen='latido'`, `en_vivo=1` (siempre), `componente=JOB`. | FR-001, FR-002, FR-003 |

### Evidencia reunida (FR-003)

| Clave | Contenido |
|---|---|
| `latido_actual` | `{job, label, detail, status, ok, age_s, max_age_s}` — `ok` calculado solo por edad, nunca por `status` (research.md §3). |

**`JOB` fuera de los 8 vigilados**: no es un error — el episodio se
congela igual, con `latido_actual` en `null`. El diagnóstico resultante
concluye `no_diagnosticable` por falta de evidencia.

**`JOB` válido pero sin `<job>.json` todavía, o lectura fallida**:
tampoco es un error — `latido_actual` se congela con `ok: false`,
`age_s: null`, `status: null`, `detail: "sin latido"` (mismo texto
exacto que usa `app.py::get_monitor_heartbeats()` para cualquier
excepción de lectura — research.md §3).

## Garantías (además de las ya vigentes en `specs/016-.../contracts/cli.md`)

41. **Un episodio de latido nunca lleva `es_critico=true`** (research.md §4).
42. **El gasto de un diagnóstico de latido cuenta contra el mismo
    acumulado diario** que el resto de orígenes (spec.md FR-007).
43. **Este feature nunca ejecuta ninguna acción sobre ningún monitor**
    (spec.md FR-008) — solo lectura.
44. **Este feature nunca corrige la inconsistencia real entre
    `MONITOR_JOBS` y `DEFAULT_MANIFEST`** (spec.md FR-010) — defecto
    del homelab, fuera de alcance.
45. **`congelar` no expone `--latido-historico`** — no existe ninguna
    evidencia histórica real que ofrecer (spec.md FR-011, research.md
    §2).

## Configuración (variables de entorno)

| Variable | Por defecto | Uso |
|---|---|---|
| `MONITOR_HEARTBEATS_DIR` | `/Volumes/FastData/homelab/data/heartbeats` | Directorio con un `<job>.json` por job (data-model.md). |

No usa ninguna de las variables de entorno de orígenes anteriores
(`HOMELAB_DB_PATH`, `SOCAT_RELAYS_JSON`, `INVENTORY_DB_PATH`,
`BESZEL_HOSTS_JSON`, `LAUNCHAGENTS_RAW`, etc.) — este feature lee un
directorio de ficheros JSON nuevo, sin ninguna dependencia de las
fuentes ya usadas por los otros 9 orígenes. `MONITOR_JOBS` (la lista de
8 jobs) es una constante en código, no configurable por variable de
entorno — mismo criterio que `HOSTS_EXTERNOS` en 014 (un universo
cerrado y conocido, no un dato externo).
