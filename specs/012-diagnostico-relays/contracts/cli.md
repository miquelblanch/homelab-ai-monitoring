# Contrato — CLI del diagnóstico de episodios (generalizado a relays)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/011-diagnostico-backups/contracts/cli.md` — `diagnosticar`,
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
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --relay-vivo NOMBRE` | Busca `NOMBRE` en `socat_relays.json` (entrecomillar si tiene espacios, p. ej. `"Beszel AdGuard"`); crea un `episodio` con `origen='relay'`, `en_vivo=1`, `componente=NOMBRE`. Imprime el `episodio_id`. | FR-001, FR-002, FR-003 |
| `congelar --relay-historico MOMENTO_ISO` | Reúne el recuento agregado de `dashboard-socat.log` en `[MOMENTO_ISO - 180min, MOMENTO_ISO + 180min]`; crea el episodio con `en_vivo=0`, `componente=MOMENTO_ISO` — **sin nombre de relay**, research.md §2. | FR-001, FR-002, FR-003 |

`MOMENTO_ISO` sigue la misma convención que discos/HA/backups: hora
local sin marca de zona.

### Evidencia reunida (FR-003), asimétrica por diseño

| Modo | Evidencia | Detalle por relay |
|---|---|---|
| Vivo | `relay_estado_actual` (`name`, `desc` — incluye IPs de la LAN, research.md §4 —, `ok`) | **Sí** |
| Diferido | `relay_agregado` (lista de `{momento, ok, total}` en la ventana) | **No** — nunca dice cuál relay, esa información no se archivó (spec.md FR-006) |

**`NOMBRE` inexistente en `socat_relays.json`**: no es un error — el
episodio se congela igual, con `relay_estado_actual` en `null`. El
diagnóstico resultante concluye `no_diagnosticable` por falta de
evidencia, mismo criterio que un `check_id`/`label` inexistente en
orígenes anteriores.

**Ningún dato dentro de la ventana en `--relay-historico`**: `relay_agregado`
queda `[]`, no `null` — el fichero se leyó, simplemente no había
ninguna línea en ese rango.

## Garantías (además de las ya vigentes en `specs/011-.../contracts/cli.md`)

17. **Un episodio de relay nunca lleva `es_critico=true`** (research.md §7).
18. **El gasto de un diagnóstico de relay cuenta contra el mismo
    acumulado diario** que contenedor/disco/HA/backup (spec.md FR-007).
19. **Este feature nunca ejecuta ninguna acción sobre un relay ni su
    LaunchAgent** (spec.md FR-008) — solo lectura.
20. **Este feature nunca amplía la vigilancia a un relay que
    `dump_socat_status.py` no compruebe hoy** (spec.md FR-010,
    research.md de `BRIEFING.md` "Feature 012") — es diagnóstico sobre
    lo ya vigilado, no cobertura nueva.
21. **Un diagnóstico en diferido nunca nombra un relay concreto como
    causa** — el prompt lo prohíbe explícitamente cuando la evidencia
    es agregada (research.md §7).

## Configuración (variables de entorno)

Además de las ya definidas en `specs/007-.../contracts/cli.md`, este
feature añade:

| Variable | Por defecto | Uso |
|---|---|---|
| `SOCAT_RELAYS_JSON` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json` | Evidencia en vivo (data-model.md). |
| `DASHBOARD_SOCAT_LOG` | `~/Library/Logs/dashboard-socat.log` | Evidencia en diferido — primera fuente fuera de `/Volumes/FastData/homelab/` (research.md §5). |

No usa `HOMELAB_SCRIPTS_DIR` ni `HOMELAB_DB_PATH` — este feature no lee
`homelab.db` ni ningún script externo (research.md §6).
