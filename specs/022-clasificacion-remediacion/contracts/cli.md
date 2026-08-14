# Contrato — Extensión del CLI de remediación (`remediacion.cli`) y del snapshot JSON

**Feature**: [../spec.md](../spec.md)

Extiende `specs/021-remediacion-contenedores/contracts/cli.md` (mismo
CLI). Ningún comando cambia de firma; dos cambian de comportamiento, y
el snapshot JSON que ya escribe `escribir_snapshot()` gana una clave
nueva.

## Comandos existentes, comportamiento ampliado

| Comando | Antes de 022 | Desde 022 |
|---|---|---|
| `comprobar-contenedores` | Excluye críticos y `NEVER_RESTART` (021, FR-006) | Excluye solo `NEVER_RESTART`. Los críticos se evalúan con `modo_forzado="manual"` (research.md §1) — nunca se ejecuta nada sobre ellos sin pasar por `aprobar` explícitamente. |
| `modo-contenedor CONTENEDOR --automatico\|--manual` | Rechaza cualquier crítico (021, FR-006) | Sin cambio de comportamiento observable para `--automatico` (sigue rechazado) — pero ahora el rechazo vive en `store.set_modo_contenedor()` (research.md §2), no solo en la capa de CLI, así que también protege a cualquier otro punto del código que llegue a llamarla directamente. `--manual` sobre un crítico ya no tiene efecto real (el modo de un crítico nunca se lee, research.md §1) pero se sigue aceptando sin error — no hay ninguna razón para que falle un comando que no cambia nada peligroso. |
| `pendientes` | Lista intentos de `rotar_log` y `reiniciar_contenedor` (no críticos) | Sin cambio de firma — ahora también puede incluir intentos `pendiente` de contenedores críticos, indistinguibles en forma de los de no críticos (misma tabla, mismos campos). |
| `aprobar INTENTO_ID` / `rechazar INTENTO_ID` | Ya genéricos por `id` | Sin cambio — funcionan igual sobre un intento de un contenedor crítico que sobre uno no crítico; es, deliberadamente, el mismo camino de aprobación (FR-008: la única vía de ejecución sobre un crítico es esta, nunca automática). |

## Comando nuevo

```
python3 -m remediacion.cli contenedores --incluir-criticos
```

| Comando | Efecto |
|---|---|
| `contenedores --incluir-criticos` | Igual que `contenedores` (021), pero añade los 12 críticos a la lista, marcados explícitamente (`critico: true`) y con `modo: null` (no aplica) en vez de `manual`/`automatico`. Sin este flag, `contenedores` sigue devolviendo solo los 26 no críticos — comportamiento de 021 sin cambios, para no romper ningún consumidor existente del comando sin el flag. |

## Snapshot JSON (`remediacion_estado.json`) — clave nueva

`escribir_snapshot()` (020) sigue escribiendo `modo_rotar_log`,
`logs[]`, `total_activos_bytes`, `total_con_rotaciones_bytes` sin
ningún cambio. Gana una clave nueva, `contenedores`:

```json
{
  "generado_en": "2026-08-14T12:00:00+00:00",
  "modo_rotar_log": "automatico",
  "logs": [ "... sin cambios ..." ],
  "total_activos_bytes": 12345,
  "total_con_rotaciones_bytes": 54321,
  "contenedores": [
    {
      "nombre": "beszel",
      "critico": false,
      "never_restart": false,
      "clasificacion": "ia",
      "modo": "automatico",
      "intento_vigente": {
        "estado": "ejecutado",
        "detalle": "reiniciado y verificado",
        "creado_en": "2026-08-14T10:03:00+00:00"
      }
    },
    {
      "nombre": "homeassistant",
      "critico": true,
      "never_restart": false,
      "clasificacion": "manual",
      "modo": null,
      "intento_vigente": null
    },
    {
      "nombre": "frigate",
      "critico": false,
      "never_restart": true,
      "clasificacion": "manual",
      "modo": null,
      "intento_vigente": null
    }
  ]
}
```

`contenedores` incluye los 39 contenedores conocidos por
`docker_monitor.py` (`_homelab_bridge.listar_contenedores()`), no solo
los evaluables — el dashboard privado necesita la lista completa para
unirla con `get_inventory()` sin dejar ninguno sin clasificar (FR-001,
SC-002). `intento_vigente` usa `store.intento_reinicio_vigente()`
(data-model.md) — `null` cuando no hay ninguno relevante ahora mismo.

## Garantías (además de las 17 ya declaradas en el contrato de 021)

18. **Ningún contenedor crítico admite modo `"automatico"`, en ningún
    punto de entrada** — `store.set_modo_contenedor()` lo rechaza
    antes de escribir (research.md §2), independientemente de si la
    llamada viene del CLI, de un test, o de cualquier código futuro
    que use esa función directamente.
19. **Una evaluación sobre un contenedor crítico nunca lee su modo de
    `configuracion_contenedor`** — `evaluar_contenedor(...,
    modo_forzado="manual")` lo impone en el punto de llamada
    (research.md §1); aunque la tabla tuviera, por algún fallo previo,
    una fila con `modo="automatico"` para un crítico, esa fila nunca
    se consulta ni se respeta.
20. **`escribir_snapshot()` nunca lanza** — igual que su versión de
    020; un fallo al calcular la clasificación o el intento vigente de
    un contenedor concreto lo omite del array en vez de abortar la
    escritura completa (mismo principio "a prueba de fallos" de todo
    el paquete).
21. **La clasificación del snapshot es siempre una de tres cadenas
    exactas** — `"manual"` / `"automatica"` / `"ia"` — nunca un valor
    derivado en el dashboard a partir de heurísticas propias; el
    dashboard privado solo aplica el "Manual" por defecto para
    componentes ausentes del snapshot (categorías sin acción real),
    nunca reinterpreta un valor presente.
22. **Si el propio snapshot no se puede leer** (fichero ausente,
    JSON corrupto, `remediacion.db` inaccesible al generarlo), el
    dashboard DEBE mostrar "sin datos de remediación" — explícito,
    nunca "Manual" por defecto ni la columna en blanco, que se
    confundiría con una clasificación real (spec.md, Edge Cases;
    Principio II — salud por resultado, no por ausencia silenciosa;
    añadida tras `/speckit-analyze`, hallazgo E2).

## Configuración

Reutiliza íntegramente las variables ya declaradas en el contrato de
021 (`REMEDIACION_CB_*`, `REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS`,
`REMEDIACION_DEEPSEEK_MOCK`, `REMEDIACION_TEST_FORZAR_FALLO`,
`REMEDIACION_DEEPSEEK_MODEL`, `REMEDIACION_SNAPSHOT_PATH`). El
presupuesto diario compartido (`DIAGNOSTICO_LIMITE_EUR_DIA`) ahora
también cubre las llamadas sobre críticos — sin límite propio
(FR-015). Una variable nueva, exclusiva de pruebas:

| Variable | Por defecto | Uso |
|---|---|---|
| `REMEDIACION_TEST_FORZAR_CRITICO` | *(sin valor)* | Lista de nombres separados por comas que se añaden al conjunto de `docker_critical()` sin tocar `docker_monitor.CRITICAL` real (research.md §1b) — permite validar el camino de críticos con un contenedor de prueba desechable, sin arriesgar uno de los 12 reales. Nunca activa en producción. |
| `REMEDIACION_INTENTO_VIGENTE_MINUTOS` | `5` | Ventana en minutos dentro de la cual un intento ya resuelto (`ejecutado`/`fallido`/`rechazado`) sigue considerándose "vigente" para `intento_reinicio_vigente()` (data-model.md) — mismo criterio de constante nombrada y configurable que el resto de umbrales del paquete (corregido tras `/speckit-analyze`, hallazgo C1: antes era un literal "5 minutos" sin nombrar). |
