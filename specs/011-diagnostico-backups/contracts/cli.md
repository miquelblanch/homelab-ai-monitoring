# Contrato — CLI del diagnóstico de episodios (generalizado a backups)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/010-diagnostico-ha/contracts/cli.md` — `diagnosticar`, `mostrar`
y `--selftest` no cambian (ya son agnósticos al origen del episodio).
Solo `congelar` gana dos opciones nuevas.

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
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --backup-vivo` | Localiza el log de backup más reciente (`backup_*.log`, orden lexicográfico), extrae su evidencia acotada (research.md §3), crea un `episodio` con `origen='backup'`, `en_vivo=1` y congela el snapshot. Imprime el `episodio_id`. **No lleva argumento** — solo existe una serie (research.md §2). | FR-001, FR-002, FR-003 |
| `congelar --backup-historico MOMENTO_ISO` | Localiza el log más cercano a `MOMENTO_ISO` dentro de `VENTANA_BACKUP_HORAS` (±12h), extrae su evidencia acotada, crea el episodio con `en_vivo=0`. | FR-001, FR-002, FR-003 |

`MOMENTO_ISO` sigue la misma convención que en discos/HA: hora local
sin marca de zona, comparada directamente contra el timestamp embebido
en el nombre del fichero de log (research.md §8 de 011).

### Evidencia reunida (FR-003)

Nunca el log completo — solo piezas acotadas (research.md §3 de 011):
estado de cada dump de base de datos, el bloque fijo de estadísticas
de rsync, la línea `RESUMEN FINAL` con el código ya interpretado, y
hasta 30 líneas de anomalía real (`rsync:`, `IO error`, `Permission
denied`, `⚠️`, `❌`) encontradas en cualquier punto del log.

**Sin log dentro de la ventana** (`--backup-historico` sin ningún
fichero a ±12h del momento pedido, o directorio de logs vacío en
`--backup-vivo`): no es un error — el episodio se congela igual, con
toda la evidencia de backup en `null`/`[]` según corresponda
(`backup_log_path` en `null`). El diagnóstico resultante concluye
`no_diagnosticable` por falta de evidencia, mismo criterio que un
`check_id`/`restart_history_id` inexistente en orígenes anteriores.

## Garantías (además de las ya vigentes en `specs/010-.../contracts/cli.md`)

13. **Un episodio de backup nunca lleva `es_critico=true`**
    (research.md §7 de 011) — el concepto no existe para backups en
    este feature.
14. **El gasto de un diagnóstico de backup cuenta contra el mismo
    acumulado diario que ya protege a contenedor, disco y HA** (spec.md
    FR-007).
15. **Este feature nunca ejecuta ninguna acción sobre el backup ni
    sobre `/Volumes/Storage/backup/`** (spec.md FR-008) — solo lectura
    de ficheros de log ya escritos.
16. **El log completo de una noche nunca se envía a DeepSeek** — solo
    la evidencia acotada de la tabla de arriba, verificado contra el
    log real más grande retenido (955 KB, 9.878 líneas) antes de
    diseñar este mecanismo (research.md §3/§4 de 011).

## Configuración (variables de entorno)

Además de `DIAGNOSTICO_DB_PATH`, `DIAGNOSTICO_LIMITE_EUR_DIA`,
`DIAGNOSTICO_DEEPSEEK_MODEL`, `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` ya
definidas en `specs/007-.../contracts/cli.md`, este feature añade:

| Variable | Por defecto | Uso |
|---|---|---|
| `BACKUP_LOG_DIR` | `/Volumes/FastData/homelab/logs` | Directorio donde buscar `backup_*.log` (data-model.md de 011). |

No usa `HOMELAB_SCRIPTS_DIR` ni `HOMELAB_DB_PATH` — este feature no lee
`homelab.db` ni ningún script externo (research.md §6 de 011).
