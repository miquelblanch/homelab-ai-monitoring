# Contrato — Extensión del CLI de remediación (`remediacion.cli`)

**Feature**: [../spec.md](../spec.md)

Extiende `specs/019-remediacion-automatica/contracts/cli.md` (mismo
CLI, `remediacion.cli` — no un binario nuevo). Los comandos ya
existentes (`comprobar`, `pendientes`, `tipos`, `aprobar`, `rechazar`,
`deshacer`, `modo`, `historial`, `--selftest`) no cambian de
comportamiento para `rotar_log`. Esta feature añade soporte para
contenedores dentro de los mismos comandos donde tiene sentido, y dos
comandos nuevos donde no.

## Invocación (comandos afectados o nuevos)

```
python3 -m remediacion.cli comprobar-contenedores
python3 -m remediacion.cli pendientes                       # ya lista también intentos_reinicio
python3 -m remediacion.cli aprobar INTENTO_ID                # ya funciona sobre cualquier tabla de intentos
python3 -m remediacion.cli rechazar INTENTO_ID
python3 -m remediacion.cli modo-contenedor CONTENEDOR (--automatico | --manual)
python3 -m remediacion.cli contenedores
```

| Comando | Efecto |
|---|---|
| `comprobar-contenedores` | Recorre los contenedores no `running and healthy`, excluidos críticos/`NEVER_RESTART` (FR-006). Para cada uno sin ya un intento `pendiente`/`sin_evaluar` reciente: reúne evidencia, pregunta a DeepSeek, crea un `intento_reinicio` en el estado que corresponda (`pendiente`, `ejecutado`, `fallido`, `sin_accion`, `sin_evaluar`). Separado de `comprobar` (que sigue siendo solo `rotar_log`) — mismo criterio que separar `TIPOS_ACCION` de la lista de contenedores: dominios distintos, comandos distintos. |
| `pendientes` | Sin cambio de firma — ahora también puede devolver intentos de `intentos_reinicio`, distinguibles por sus campos propios (`contenedor` en vez de `componente`/`ruta`). |
| `aprobar INTENTO_ID` | Sin cambio de firma — resuelve sobre la tabla que corresponda según dónde exista ese `id`. Para un intento de reinicio, ejecuta vía `_homelab_bridge.restart_container()`, con la misma verificación real post-reinicio. |
| `rechazar INTENTO_ID` | Igual — pasa el intento de reinicio a `"rechazado"`, sin tocar el contenedor. |
| `modo-contenedor CONTENEDOR --automatico\|--manual` | Nuevo — cambia `configuracion_contenedor.modo` para un contenedor concreto. Rechaza explícitamente, sin escribir nada, si `CONTENEDOR` está en la lista crítica o es `frigate` (FR-006). |
| `contenedores` | Nuevo — lista los 26 contenedores no críticos con su modo actual, mismo espíritu de solo-lectura que `tipos` (research.md de la sesión anterior: "¿cómo sé los tipos que existen?" aplicado ahora a contenedores). |

## Garantías (además de las 9 ya declaradas en el contrato de 019)

10. **DeepSeek nunca elige fuera de la lista cerrada de acciones** —
    `parsear_respuesta_remediacion()` valida `accion_aplica` contra
    `acciones.TIPOS_ACCION` antes de aceptar cualquier recomendación
    (FR-003).
11. **Ningún contenedor crítico ni `frigate` recibe una evaluación,
    una propuesta, ni un cambio de modo** — `comprobar-contenedores`
    los excluye antes de reunir evidencia; `modo-contenedor` los
    rechaza explícitamente si se intenta (FR-006).
12. **Un fallo de la llamada a DeepSeek nunca se registra como
    "ninguna acción aplica"** — estado `sin_evaluar`, distinto de
    `sin_accion` (FR-015, data-model.md).
13. **Sin llamada a DeepSeek sin presupuesto disponible** —
    `comprobar-contenedores` comprueba `diagnostico.gasto.hay_presupuesto()`
    antes de cada llamada, mismo límite compartido que `diagnostico.cli`
    (FR-013/FR-014).
14. **Ningún reinicio se ejecuta sin verificación real de `running`
    tras el intento** — vía `_homelab_bridge.restart_container()`,
    reutilizando la corrección ya aplicada en `docker_monitor.py`
    (FR-010).
15. **Sin operación de deshacer para un intento de reinicio** —
    `deshacer INTENTO_ID` sigue existiendo para `rotar_log`, pero
    rechaza explícitamente cualquier `id` que pertenezca a
    `intentos_reinicio` (FR-016).

## Configuración (variables de entorno nuevas)

| Variable | Por defecto | Uso |
|---|---|---|
| `REMEDIACION_CB_MAX_INTENTOS` | `3` | Mismo valor que `docker_monitor.CB_MAX_ATTEMPTS` — configurable para poder probar el cortacircuito por CLI sin esperar 6 horas reales. |
| `REMEDIACION_CB_VENTANA_HORAS` | `6` | Mismo valor que `docker_monitor.CB_WINDOW_HOURS`. |

Sin variable nueva para el presupuesto diario — reutiliza
`DIAGNOSTICO_LIMITE_EUR_DIA`, ya existente (research.md §8).
