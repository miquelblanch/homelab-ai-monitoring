# Contrato — Extensión del CLI de remediación (`remediacion.cli`)

**Feature**: [../spec.md](../spec.md)

Extiende `specs/021-remediacion-contenedores/contracts/cli.md` (mismo
CLI, `remediacion.cli` — no un binario nuevo). Los comandos ya
existentes no cambian de comportamiento para `rotar_log` ni
`reiniciar_contenedor`. Esta feature añade soporte para agentes dentro
de los comandos genéricos, y dos comandos nuevos donde no lo es.

## Invocación (comandos afectados o nuevos)

```
python3 -m remediacion.cli comprobar-agentes
python3 -m remediacion.cli pendientes                # ya lista también intentos_agente
python3 -m remediacion.cli aprobar INTENTO_ID          # ya funciona sobre cualquier tabla de intentos
python3 -m remediacion.cli rechazar INTENTO_ID
python3 -m remediacion.cli agentes
```

| Comando | Efecto |
|---|---|
| `comprobar-agentes` | Recorre los 43 candidatos (`amsterdam9.*` + `com.homeassistant.*`) sin proceso activo, salta los que ya tienen un intento `pendiente`/`sin_evaluar` reciente, evalúa el resto: reúne evidencia (`congelar_agente_vivo`), pregunta a DeepSeek, crea un `intento_agente` en el estado que corresponda. Separado de `comprobar`/`comprobar-contenedores` — mismo criterio de dominios distintos, comandos distintos. |
| `pendientes` | Sin cambio de firma — ahora también puede devolver intentos de `intentos_agente`, distinguibles por `label` en vez de `componente`/`contenedor`. |
| `aprobar INTENTO_ID` | Sin cambio de firma — `localizar_intento()` ahora prueba tres tablas (research.md §1). Para un intento de agente, ejecuta vía `_homelab_bridge`/`acciones.ejecutar_reiniciar_agente()`, con verificación real post-reinicio. |
| `rechazar INTENTO_ID` | Igual — pasa el intento de agente a `"rechazado"`, sin tocar el proceso. |
| `agentes` | Nuevo — lista los 43 candidatos con su estado actual (`running`/no), clasificación, y si es `com.homeassistant.*`, si el `sudoers` está instalado — mismo espíritu de solo lectura que `contenedores`/`tipos`. Sin `modo-agente`: `reiniciar_agente` usa `configuracion_accion` (mismo `modo` para todos), no una configuración por-instancia — cambia con `modo reiniciar_agente --automatico\|--manual`, comando ya existente desde 019. |

## Garantías (además de las 20 ya declaradas en 019/021/022)

21. **DeepSeek nunca elige fuera de la lista cerrada de acciones para
    un agente** — `parsear_respuesta_agente()` valida `accion_aplica`
    contra `acciones.TIPOS_ACCION` antes de aceptar cualquier
    recomendación (mismo criterio que la garantía 10 de 021).
22. **Ningún `com.homeassistant.*` se reinicia sin que `sudo -n`
    confirme el permiso exacto en el momento de ejecutar** — un
    permiso no instalado o insuficiente produce `estado="fallido"`
    con el motivo real, nunca un intento silenciosamente ignorado
    (data-model.md, transición nueva).
23. **La comprobación de `sudoers` para el snapshot nunca ejecuta el
    reinicio** — `sudoers_permitido()` usa `sudo -n -l`, que consulta
    el permiso sin dispararlo (research.md §3, FR-023).
24. **Un fallo de la llamada a DeepSeek nunca se registra como
    "ninguna acción aplica"** — estado `sin_evaluar`, mismo criterio
    que contenedores (garantía 12 de 021).
25. **Sin llamada a DeepSeek sin presupuesto disponible** — mismo
    límite compartido que diagnóstico y contenedores (FR-010/FR-011).
26. **El cortacircuito de agentes cuenta solo sobre `intentos_agente`**
    — un agente en racha de fallos no consume ni comparte contador con
    ningún contenedor, aunque el umbral (3/6h) sea el mismo valor
    (Clarifications, sesión 2026-08-16).
27. **`amsterdam9.health` (o el mecanismo de vigilancia de agentes
    equivalente) no cambia de comportamiento** — sigue vigilando y
    avisando de cualquier agente caído, con o sin esta feature activa
    (FR-013, Principio VII).
28. **Ningún job de Hermes (`cron: *`), `host_externo`, ni entidad de
    Home Assistant individual recibe evaluación ni acción** — fuera de
    alcance de este contrato (FR-016, spec.md Assumptions).

## Nota — no confundir con "Correcciones"

`agentes`/`pendientes`/`historial` siguen siendo el mecanismo de
`remediacion.cli` (intentos reales, con o sin resolver) — distinto de
la pestaña "Correcciones" del dashboard (008/021), que hoy es un
historial de **alarmas ya resueltas**. FR-020/FR-021 amplían
Correcciones para que también lea el `intento_vigente` de este mismo
CLI (vía el snapshot, `contracts/snapshot-json.md`) mientras la alarma
sigue activa — sin que eso convierta a Correcciones en un duplicado de
`remediacion.cli pendientes`: uno vive en el dashboard (solo lectura,
todo tipo de componente junto), el otro es la única vía real de
actuar (CLI, por tipo de acción).
