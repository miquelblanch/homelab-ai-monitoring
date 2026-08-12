# Contrato — CLI del diagnóstico de episodios (generalizado a los hosts externos)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/013-diagnostico-inventario/contracts/cli.md` — `diagnosticar`,
`mostrar` y `--selftest` no cambian. Solo `congelar` gana dos opciones
nuevas.

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
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --host-externo-vivo NOMBRE` | Busca `NOMBRE` (entrecomillar si tiene espacios, p. ej. `"Host de Uptime Kuma"`) en `HOSTS_EXTERNOS`; lee su estado ya calculado (`beszel_hosts.json` + latido, misma política de frescura de 900s que el dashboard); crea un `episodio` con `origen='host_externo'`, `en_vivo=1`, `componente=NOMBRE`. | FR-001, FR-002, FR-003 |
| `congelar --host-externo-historico "NOMBRE@MOMENTO_ISO"` | Convierte `MOMENTO_ISO` (hora local de Madrid) a UTC, consulta `system_stats` del hub de Beszel en `[momento-24h, momento+24h]`, resume la densidad; crea el episodio con `en_vivo=0`, `componente=NOMBRE` (nunca `NOMBRE@MOMENTO_ISO` — research.md §2). | FR-001, FR-002, FR-003 |

`MOMENTO_ISO` sigue la misma convención que discos/HA/backups/relays:
hora local sin marca de zona.

### Evidencia reunida (FR-003)

| Modo | Clave | Contenido |
|---|---|---|
| Vivo | `host_externo_actual` | `{nombre, beszel_name, status, raw_status, data_age_s, hb_age_s}` — `status` ∈ `{"arriba", "caido", "sin_evidencia"}`. |
| Diferido | `host_externo_stats` | `{beszel_name, total_muestras, primera, ultima, por_tipo}` — nunca un booleano "caído" (FR-006a). |

**`NOMBRE` fuera de los 2 hosts vigilados, o consulta fallida
(`beszel_hosts.json` ausente, `docker run` sin éxito)**: no es un
error — el episodio se congela igual, con la evidencia correspondiente
en `null`. El diagnóstico resultante concluye `no_diagnosticable` por
falta de evidencia, mismo criterio que un `check_id`/`label`/nombre de
relay/componente de inventario inexistente en orígenes anteriores.

**`total_muestras: 0` en diferido**: no es un error ni "host
caído confirmado" — es evidencia real de ausencia, que el prompt
generalizado le prohíbe presentar como prueba concluyente (FR-006a,
research.md §5/§8).

## Garantías (además de las ya vigentes en `specs/013-.../contracts/cli.md`)

26. **Un episodio de host externo nunca lleva `es_critico=true`**
    (research.md §8).
27. **El gasto de un diagnóstico de host externo cuenta contra el
    mismo acumulado diario** que el resto de orígenes (spec.md FR-007).
28. **Este feature nunca ejecuta ninguna acción sobre un host externo
    ni sobre Beszel** (spec.md FR-008) — solo lectura.
29. **Este feature nunca diagnostica el propio hub de Beszel** (spec.md
    FR-010) — ese es el origen #8, con su propia investigación
    pendiente.
30. **La consulta al hub de Beszel usa siempre parámetros SQL, nunca
    interpolación de texto** (research.md §7) — mismo nivel de
    disciplina que cualquier consulta contra `homelab.db`.

## Configuración (variables de entorno)

Además de las ya definidas en `specs/007-.../contracts/cli.md`, este
feature añade:

| Variable | Por defecto | Uso |
|---|---|---|
| `BESZEL_HOSTS_JSON` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/beszel_hosts.json` | Evidencia en vivo (data-model.md). |
| `BESZEL_HOSTS_HEARTBEAT` | `/Volumes/FastData/homelab/data/heartbeats/beszel-hosts.json` | Segunda mitad de la política de frescura en vivo (research.md §3). |

No usa `HOMELAB_SCRIPTS_DIR`, `HOMELAB_DB_PATH`, `SOCAT_RELAYS_JSON`,
`DASHBOARD_SOCAT_LOG` ni `INVENTORY_DB_PATH` — este feature no lee
`homelab.db`, ningún fichero de relay ni `inventario.db` (research.md
§3/§7). El volumen del hub de Beszel (`beszel_hub_data`) no es
configurable vía variable de entorno — es el mismo volumen fijo que ya
usa `scripts/beszel_hosts_monitor.py` en producción.
