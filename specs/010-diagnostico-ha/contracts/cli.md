# Contrato — CLI del diagnóstico de episodios (generalizado a Home Assistant)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/009-diagnostico-discos/contracts/cli.md` — `diagnosticar`,
`mostrar` y `--selftest` no cambian (ya son agnósticos al origen del
episodio). Solo `congelar` gana dos opciones nuevas.

## Invocación

```
python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
python3 -m diagnostico.cli congelar --vivo CONTENEDOR
python3 -m diagnostico.cli congelar --disco-historico "LABEL@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --disco-vivo LABEL
python3 -m diagnostico.cli congelar --ha-historico "CHECK_ID@MOMENTO_ISO"
python3 -m diagnostico.cli congelar --ha-vivo CHECK_ID
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --ha-vivo CHECK_ID` | Resuelve `CHECK_ID` contra `ha_monitor.CHECKS` en vivo, reúne su evidencia según el tipo de check (tabla abajo), crea un `episodio` con `origen='ha'`, `en_vivo=1` y congela el snapshot. Imprime el `episodio_id`. | FR-001, FR-002, FR-003 |
| `congelar --ha-historico "CHECK_ID@MOMENTO_ISO"` | Igual, pero con la evidencia centrada en `MOMENTO_ISO` en vez de en el instante actual (con el límite del research.md §6 para `ha_recorder_corrupto`/`ha_api`). Crea el episodio con `en_vivo=0`. | FR-001, FR-002, FR-003 |

`CHECK_ID` es el identificador de un check tal cual aparece en
`ha_monitor.CHECKS` (por ejemplo `"bateria_interruptor_salon"`,
`"z2m_bridge"`, `"ha_recorder_corrupto"`, `"ha_api"`) — no un
`entity_id` de Home Assistant (research.md §2). `MOMENTO_ISO` sigue la
misma convención que `LABEL@MOMENTO_ISO` de discos: hora local sin
marca de zona, sin conversión (research.md §9).

### Evidencia reunida según el tipo de check (FR-003)

| `ha_monitor.CHECKS[...]["type"]` | Evidencia | Ventana |
|---|---|---|
| `entity_state`, `entity_available`, `entity_value_below`, `entity_age_below` | Historial de la entidad (`/api/history/period/` de la API REST de HA) | ± `VENTANA_HA_ENTIDAD_HORAS` (12h) alrededor del momento, o hacia atrás desde ahora en modo vivo |
| `recorder_corrupto` | Ficheros `*.corrupt.*` presentes + últimas 200 líneas de `docker logs homeassistant` | Estado actual siempre — sin equivalente histórico (research.md §6) |
| `api_ping` (`ha_api`) | Últimas 200 líneas de `docker logs homeassistant` | Estado actual siempre — sin equivalente histórico (research.md §6) |

**`CHECK_ID` inexistente en `ha_monitor.CHECKS`**: no es un error — el
episodio se congela igual, con toda la evidencia de HA en `null`
(research.md §3). El diagnóstico resultante concluye
`no_diagnosticable` por falta de evidencia, mismo criterio que un
contenedor o disco inexistente.

**`CHECK_ID` de la cerradura**: `congelar --ha-vivo`/`--ha-historico`
**rechaza** con error y código de salida distinto de 0 cualquiera de
los tres checks `cerradura_up`, `bateria_cerradura`,
`bateria_critica_cerradura` — no crea ningún episodio (FR-010,
research.md §7). Esto es distinto del caso anterior: aquí el rechazo es
explícito, no una evidencia vacía.

## Garantías (además de las ya vigentes en `specs/009-.../contracts/cli.md`)

9. **Un episodio de HA nunca lleva `es_critico=true`** (research.md
   §8) — el concepto no existe para HA en este feature.
10. **El gasto de un diagnóstico de HA cuenta contra el mismo acumulado
    diario que ya protege a los de contenedor y disco** (spec.md
    FR-007) — `diagnosticar` no distingue el origen del episodio al
    aplicar el cortacircuitos de gasto.
11. **Este feature nunca ejecuta ninguna acción sobre HA ni sobre
    ningún dispositivo físico** (spec.md FR-008) — solo lectura vía la
    API REST de HA y `docker logs`/`docker exec` de solo lectura.
12. **Los tres checks de la cerradura quedan fuera de alcance con un
    rechazo explícito, no un diagnóstico honesto de "sin evidencia"**
    (spec.md FR-010, research.md §7).

## Configuración (variables de entorno)

Sin variables nuevas propias de este feature — reutiliza
`DIAGNOSTICO_DB_PATH`, `DIAGNOSTICO_LIMITE_EUR_DIA`,
`DIAGNOSTICO_DEEPSEEK_MODEL`, `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`,
`HOMELAB_SCRIPTS_DIR`, `HOMELAB_DB_PATH` ya definidas en
`specs/007-.../contracts/cli.md`, más las credenciales de HA
(`HA_URL`/`HA_TOKEN` en `.secrets/ha.env`), que este feature nunca lee
directamente — las resuelve `ha_monitor.py` al importarse, vía
`_homelab_bridge` (research.md §3).
