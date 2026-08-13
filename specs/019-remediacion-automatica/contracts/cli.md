# Contrato — CLI de remediación (`remediacion.cli`)

**Feature**: [../spec.md](../spec.md)

Primer contrato de `src/remediacion/` — paquete nuevo, sin relación
con `specs/007-.../contracts/cli.md` de `diagnostico.cli`.

## Invocación

```
python3 -m remediacion.cli comprobar
python3 -m remediacion.cli pendientes
python3 -m remediacion.cli tipos
python3 -m remediacion.cli aprobar INTENTO_ID
python3 -m remediacion.cli rechazar INTENTO_ID
python3 -m remediacion.cli deshacer INTENTO_ID
python3 -m remediacion.cli modo TIPO_ACCION (--automatico | --manual)
python3 -m remediacion.cli historial TIPO_ACCION
python3 -m remediacion.cli --selftest
```

| Comando | Efecto |
|---|---|
| `comprobar` | Evalúa `LOGS_VIGILADOS` (data-model.md). Por log por encima de su umbral sin ya un intento `pendiente`: en modo manual crea `pendiente`; en modo automático ejecuta directo (`ejecutado`/`fallido`). Imprime un resumen. |
| `pendientes` | Lista los intentos en estado `pendiente`, con su detalle. |
| `tipos` | Lista cada tipo de acción registrado en código (`acciones.TIPOS_ACCION`) con su modo actual. Solo lectura — a diferencia de `modo`, nunca crea fila en `configuracion_accion` (research.md §10). |
| `aprobar INTENTO_ID` | Solo sobre un intento `pendiente`. Ejecuta la rotación real; pasa a `ejecutado` o `fallido` según el resultado. |
| `rechazar INTENTO_ID` | Solo sobre un intento `pendiente`. Pasa a `rechazado`, estado final — el fichero no se toca. |
| `deshacer INTENTO_ID` | Solo sobre un intento `ejecutado`. Aplica el procedimiento de rollback (research.md §4). Pasa a `deshecho`. |
| `modo TIPO_ACCION --automatico\|--manual` | Cambia `configuracion_accion.modo` — sin ninguna condición previa (FR-003). Imprime el historial de ese tipo de acción antes de aplicar el cambio. |
| `historial TIPO_ACCION` | Recuento de intentos por estado para ese tipo de acción — informativo (FR-004). |

## Garantías

1. **Todo tipo de acción empieza en modo `manual`** — no existe forma
   de crear una fila de `configuracion_accion` ya en `automatico`
   (FR-002).
2. **`comprobar` nunca actúa sobre un fichero fuera de
   `LOGS_VIGILADOS`** (FR-005).
3. **`comprobar` nunca crea una segunda `pendiente` para el mismo log**
   mientras ya exista una sin resolver (FR-008).
4. **Ninguna rotación trunca ni borra contenido** — siempre renombra
   (FR-009, research.md §4).
5. **`deshacer` nunca sobreescribe lo escrito después de la rotación**
   — lo renombra aparte si existe (FR-010, research.md §4).
6. **`aprobar`/`rechazar`/`deshacer` sobre un intento en el estado
   equivocado se rechazan explícitamente**, sin ejecutar nada (Edge
   Cases de spec.md).
7. **Ninguna acción sobre un componente de la lista de críticos** —
   `LOGS_VIGILADOS` en v1 no contiene ninguno (FR-012, spec.md
   Assumptions).
8. **Sin ninguna llamada de red ni a DeepSeek** — la condición se
   evalúa enteramente local (FR-013).
9. **Sin ninguna notificación ni escritura fuera de `remediacion.db`
   y los propios ficheros de log vigilados** — ni Telegram, ni
   dashboard (FR-014).

## Configuración (variables de entorno)

| Variable | Por defecto | Uso |
|---|---|---|
| `REMEDIACION_DB_PATH` | Junto a `diagnostico.db` (`.../homelab-orchestrator/data/remediacion.db`) | Base de este paquete — independiente de `diagnostico.db` (research.md §2). |
| `REMEDIACION_UMBRAL_ROTACION_BYTES` | `10485760` (10 MB) | Umbral de la condición determinista (research.md §3). |
| `REMEDIACION_LOGS_DIR` | `~/Library/Logs` | Directorio donde viven los logs vigilados — configurable para validar por CLI contra ficheros de prueba sin tocar los reales (`quickstart.md`, research.md §3). |

Los **nombres de fichero** de `LOGS_VIGILADOS` (`health-docker.log`,
`health-ha.log`) son una constante en código, no configurables — mismo
criterio que `MONITOR_JOBS` en 017: un universo cerrado y conocido, no
un dato externo. Solo el directorio que los contiene es configurable.
