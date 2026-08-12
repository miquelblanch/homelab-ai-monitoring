# Contrato — CLI del diagnóstico de episodios (generalizado al hub de Beszel)

**Feature**: [../spec.md](../spec.md)

Extiende el contrato de
`specs/014-diagnostico-hosts-externos/contracts/cli.md` — `diagnosticar`,
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
python3 -m diagnostico.cli congelar --hub-beszel-historico MOMENTO_ISO
python3 -m diagnostico.cli congelar --hub-beszel-vivo
python3 -m diagnostico.cli diagnosticar EPISODIO_ID
python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
python3 -m diagnostico.cli --selftest
```

| Comando | Efecto | Requisito de origen |
|---|---|---|
| `congelar --hub-beszel-vivo` | Lee la antigüedad de todos los sistemas registrados en el hub (`beszel_hosts.json`), calcula `sano` con el mismo criterio que el dashboard; crea un `episodio` con `origen='hub_beszel'`, `en_vivo=1`, `componente=<momento ISO>`. Sin argumento — solo hay un hub, mismo patrón que `--backup-vivo`. | FR-001, FR-002, FR-003 |
| `congelar --hub-beszel-historico MOMENTO_ISO` | Convierte `MOMENTO_ISO` (hora local de Madrid) a UTC, consulta `system_stats` de **todos** los sistemas del hub en `[momento-24h, momento+24h]`, resume la densidad por sistema; crea el episodio con `en_vivo=0`, `componente=<momento ISO>`. | FR-001, FR-002, FR-003 |

### Evidencia reunida (FR-003)

| Modo | Clave | Contenido |
|---|---|---|
| Vivo | `hub_beszel_actual` | `{systems: [{name, age_s, stale}], sano}`. |
| Diferido | `hub_beszel_stats` | `{por_sistema: {nombre: {total_muestras, primera, ultima, por_tipo}}, todos_sin_muestras}` — nunca un booleano "caído" sin más (FR-006a). |

**Consulta al hub fallida (`docker run` sin éxito, Docker no
disponible)**: no es un error — el episodio se congela igual, con
`hub_beszel_stats` en `null`. El diagnóstico resultante concluye
`no_diagnosticable` por falta de evidencia.

**`todos_sin_muestras: true` en diferido**: no es un error ni "hub
caído confirmado" — es evidencia real de ausencia total, que el
prompt generalizado le prohíbe presentar como prueba concluyente
(FR-006a, research.md §5/§8).

## Garantías (además de las ya vigentes en `specs/014-.../contracts/cli.md`)

31. **Un episodio del hub nunca lleva `es_critico=true`** (research.md §8).
32. **El gasto de un diagnóstico del hub cuenta contra el mismo
    acumulado diario** que el resto de orígenes (spec.md FR-007).
33. **Este feature nunca ejecuta ninguna acción sobre Beszel** (spec.md
    FR-008) — solo lectura.
34. **Este feature nunca diagnostica un host externo concreto**
    (spec.md FR-010) — ese es el origen #7 (014), ya cerrado.
35. **La consulta al hub usa siempre parámetros SQL, nunca
    interpolación de texto** — mismo nivel de disciplina que 014.

## Configuración (variables de entorno)

Reutiliza tal cual las de 014: `BESZEL_HOSTS_JSON`. No añade ninguna
variable nueva — `BESZEL_HUB_VOLUME` sigue fijo, sin variable de
entorno, mismo criterio que 014.
