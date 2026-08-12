# Contrato — CLI del diagnóstico de episodios (generalizado al inventario)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/012-diagnostico-relays/contracts/cli.md` — `diagnosticar`,
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
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --inventario-vivo NOMBRE` | Busca `NOMBRE` (entrecomillar si tiene espacios, p. ej. `"Agente Hermes/Bautista"`) entre los hallazgos de la ejecución más reciente de `inventario.db`; crea un `episodio` con `origen='inventario'`, `en_vivo=1`, `componente=NOMBRE`. Imprime el `episodio_id`. | FR-001, FR-002, FR-003 |
| `congelar --inventario-historico "NOMBRE@EJECUCION_ID"` | Busca `NOMBRE` entre los hallazgos de la ejecución `EJECUCION_ID`; crea el episodio con `en_vivo=0`, `componente=NOMBRE` (la ejecución pedida queda en el snapshot, no en `componente` — research.md §3). | FR-001, FR-002, FR-003 |

`EJECUCION_ID` es un entero — el `id` de una fila de
`inventario.db.ejecuciones` (consultable con `python3 -m inventory.cli
--gaps` o revisando el histórico). A diferencia de `MOMENTO_ISO` en los
demás orígenes, no es un instante continuo: las ejecuciones del
inventario no tienen cadencia fija (research.md §8).

### Evidencia reunida (FR-003)

| Clave | Presente cuando |
|---|---|
| `inventario_ejecucion_id` | Siempre. |
| `inventario_hallazgo` | `NOMBRE` existe entre los hallazgos de esa ejecución. |
| `inventario_brecha` | El hallazgo es una brecha de uno de los 5 tipos en alcance (`sin_declaracion`, `declaracion_caducada`, `sin_vigilancia`, `no_llega_a_dashboard`, `riesgo_concentrado_telegram`). |
| `inventario_comparacion` | Hay brecha y existe una ejecución anterior a `primera_ejecucion_id` — diff de `inventory.diff.compare_runs()` contra `primera_ejecucion_id - 1`, nunca contra `EJECUCION_ID - 1` (research.md §4). Cada lista acotada a 30 entradas con su total real (research.md §11) — el caso real más grande observado llega a 319. |

**`NOMBRE` inexistente en esa ejecución, o `EJECUCION_ID` inexistente**:
no es un error — el episodio se congela igual, con
`inventario_hallazgo`/`inventario_brecha`/`inventario_comparacion` en
`null`. El diagnóstico resultante concluye `no_diagnosticable` por
falta de evidencia, mismo criterio que un `check_id`/`label`/nombre de
relay inexistente en orígenes anteriores.

**Brecha de tipo `condicion_incumplida`**: **rechazada explícitamente**
antes de congelar — `congelar` termina con código de salida 1 y un
mensaje en stderr, mismo tratamiento que un `check_id` de la cerradura
en `--ha-vivo`/`--ha-historico` (FR-010).

## Garantías (además de las ya vigentes en `specs/012-.../contracts/cli.md`)

22. **Un episodio de inventario nunca lleva `es_critico=true`**
    (research.md §7).
23. **El gasto de un diagnóstico de inventario cuenta contra el mismo
    acumulado diario** que contenedor/disco/HA/backup/relay (spec.md
    FR-007).
24. **Este feature nunca declara un estado esperado, añade vigilancia
    ni corrige qué llega al dashboard** (spec.md FR-008) — solo
    lectura de `inventario.db` a través de `inventory.store`/
    `inventory.diff`.
25. **Este feature nunca diagnostica una brecha de tipo
    `condicion_incumplida`** (spec.md FR-010) — rechazada en código
    antes de congelar, no solo pedido en el prompt.

## Configuración (variables de entorno)

Este feature **no** añade ninguna variable de entorno nueva — reutiliza
`INVENTORY_DB_PATH`, ya definida por `inventory.store.db_path()`
(`inventory/contracts/cli.md` de feature 001), sin duplicarla en
`diagnostico`. No usa `HOMELAB_SCRIPTS_DIR`, `HOMELAB_DB_PATH`,
`SOCAT_RELAYS_JSON` ni `DASHBOARD_SOCAT_LOG` — este feature no lee
`homelab.db` ni ningún fichero de relay (research.md §2).
