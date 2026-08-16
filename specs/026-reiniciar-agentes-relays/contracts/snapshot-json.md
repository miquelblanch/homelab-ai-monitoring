# Contrato — `remediacion_estado.json`, bloque `agentes[]`

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Extiende `specs/020-visor-remediacion/contracts/snapshot-json.md`
(mismo fichero, mismo productor/consumidor) y
`specs/022-clasificacion-remediacion/` (que ya añadió el bloque
`contenedores[]`). Esta feature añade un tercer bloque, `agentes[]`, y
**una corrección sobre `logs[]`**: gana un campo `intento_vigente` que
nunca había tenido (verificando T028 se descubrió que la premisa de
que ya lo tenía "desde 020" era falsa — corregido aquí, no solo en
research.md). `contenedores[]` no cambia de forma.

## Productor

`escribir_snapshot(conn)` en `src/remediacion/acciones.py` — mismo
punto de escritura, ahora también recorre `bridge.listar_agentes_conocidos()`.

## Consumidor

`homelab-dashboard/scripts/app.py` (fuera de este repo) — la pestaña
"Remediaciones" (User Story 4) y la ampliación de "Correcciones" (User
Story 5) leen este bloque; el cableado de "Beszel (hub)" (User Story
3) sigue leyendo solo `contenedores[]`, sin cambios.

## Forma del payload (bloque nuevo)

```json
{
  "agentes": [
    {
      "label": "amsterdam9.health.docker",
      "tipo": "amsterdam9",
      "running": true,
      "clasificacion": "ia",
      "sudoers_instalado": null,
      "intento_vigente": null
    },
    {
      "label": "com.homeassistant.esphome-sal-relay",
      "tipo": "com.homeassistant",
      "running": false,
      "clasificacion": "ia",
      "sudoers_instalado": false,
      "intento_vigente": {
        "estado": "sin_evaluar",
        "detalle": "sin presupuesto diario disponible para preguntar a DeepSeek",
        "creado_en": "2026-08-16T09:05:00+00:00"
      }
    }
  ]
}
```

| Campo | Notas |
|---|---|
| `label` | Label real de `launchd`. |
| `tipo` | `"amsterdam9"` o `"com.homeassistant"` — para que el dashboard sepa si `sudoers_instalado` aplica sin tener que parsear el prefijo del label. |
| `running` | Estado real en el momento de escribir el snapshot (`LAUNCHAGENTS_RAW`). |
| `clasificacion` | `"ia"` — mismo valor para los 43, `clasificar_agente()` no distingue automática/IA para agentes (no hay condición determinista equivalente a `rotar_log`, siempre decide DeepSeek). |
| `sudoers_instalado` | `null` para `amsterdam9.*` (la pregunta no aplica). `true`/`false` para `com.homeassistant.*` — resultado de `sudoers_permitido()` (research.md §3), nunca ejecuta el reinicio para comprobarlo. |
| `intento_vigente` | Mismo shape que `contenedores[].intento_vigente` (020/022) — `null` si no hay ninguno reciente. |

## Garantías (además de las 6 ya declaradas en 020)

7. **`agentes` siempre tiene una entrada por cada label reconocido en
   el momento de escribir el snapshot** (43 hoy) — un agente que
   desaparece de `launchctl list` entre un ciclo y otro deja de
   aparecer (a diferencia de `logs[]`, que es una lista cerrada fija);
   no es una brecha, es coherente con FR-012 del spec (solo se evalúa
   lo reconocido).
8. **`sudoers_instalado` nunca se calcula ejecutando el reinicio** —
   siempre vía `sudo -n -l`, de solo lectura (FR-023, research.md §3).
9. **Un fallo al comprobar el permiso de un agente concreto no aborta
   el resto del bloque** — mismo criterio que la garantía 20 de 022
   para `contenedores[]` (`_snapshot_agentes()` atrapa la excepción
   por agente, no por el bloque entero).
10. **`clasificacion` de un agente nunca es `"manual"` dentro de este
    bloque** — si apareciera como `"manual"`, sería un candidato mal
    filtrado (bug), no un valor esperado: `agentes[]` solo contiene lo
    que ya se decidió evaluar, la clasificación real "manual" para
    todo lo demás del inventario vive fuera de este bloque.
11. **`logs[].intento_vigente` existe desde esta feature** (corrección
    de un supuesto falso, arriba) — mismo shape y mismo criterio que
    `contenedores[]`/`agentes[]`, vía `store.intento_vigente()`.
    Necesario para que Correcciones (FR-020) pueda leer el estado real
    de un intento de `rotar_log`, no solo de contenedores/agentes.
