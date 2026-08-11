# Contrato — Campos `diagnostico` y `gasto_diagnostico` en `/api/data`

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Sin CLI ni endpoint nuevo (mismo patrón que features 002/003/006): el
contrato es un campo nuevo dentro de `alarms.items[]` (ya existente,
feature 006) más una clave nueva de nivel superior en el JSON que
`/api/data` ya devuelve en cada petición del dashboard.

## Productor

`get_diagnostico_para_alarma()` y `get_gasto_diagnostico_hoy()` en
`homelab-dashboard/scripts/app.py` (research.md §5), llamadas desde
`get_active_alarms()` (para el campo por alarma, en la rama
`origen == "contenedores"`) y desde el mismo punto de `collect()` donde
ya se calcula `alarms` (para el campo de nivel superior).

## Consumidor

El JavaScript embebido de la pestaña `#alarmas` ya existente
(`renderAlarmas()`), ampliado para pintar el bloque de diagnóstico
cuando `a.diagnostico` no es `null` (research.md §6).

## Forma del payload

```json
{
  "alarms": {
    "total": 2,
    "items": [
      {
        "origen": "contenedores",
        "tipo": "contenedor_caido",
        "nivel": "aviso",
        "componente": "beszel",
        "mensaje": "Exited (1) 3 minutes ago",
        "explicacion": "Este contenedor no está corriendo...",
        "remediacion": "Revisar docker logs --tail 50...",
        "antiguedad_s": 180,
        "agrupada": false,
        "cantidad": 1,
        "diagnostico": {
          "episodio_fecha": "2026-08-11T18:55:00+02:00",
          "diagnostico_fecha": "2026-08-11T16:56:12+00:00",
          "conclusion_tipo": "no_diagnosticable",
          "conclusion_texto": "La evidencia disponible es insuficiente para determinar una causa probable del reinicio del contenedor 'beszel'...",
          "hipotesis": [
            {
              "descripcion": "Presión de memoria en el momento del reinicio",
              "comprobacion": "container_metrics de la ventana no muestra ninguna muestra con memory_percent elevado",
              "desenlace": "descartada"
            }
          ]
        }
      },
      {
        "origen": "contenedores",
        "tipo": "contenedor_caido_critico",
        "nivel": "critico",
        "componente": "homeassistant",
        "mensaje": "Restarting (1) 2 minutes ago",
        "explicacion": "Este contenedor está en la lista de críticos...",
        "remediacion": "No reiniciar ni modificar sin aprobación humana previa...",
        "antiguedad_s": 120,
        "agrupada": false,
        "cantidad": 1,
        "diagnostico": null
      },
      {
        "origen": "ha",
        "tipo": "ha_entidad_no_disponible",
        "nivel": "aviso",
        "componente": "sensor.ejemplo",
        "mensaje": "unavailable",
        "explicacion": "Una entidad de Home Assistant está unavailable...",
        "remediacion": "Comprobar el dispositivo físico...",
        "antiguedad_s": 340,
        "agrupada": false,
        "cantidad": 1,
        "diagnostico": null
      }
    ]
  },
  "gasto_diagnostico": {
    "coste_eur_acumulado": 0.0021,
    "limite_eur": 5.0
  }
}
```

## Garantías

1. **`diagnostico` siempre está presente en toda alarma** (mismo
   `add()` que construye las de los 10 orígenes en
   `get_active_alarms()`) y es `null` en cualquier caso donde este
   feature no aplica: alarmas de otro origen (`ha`, `backup`,
   `relays`...), alarmas agrupadas (`agrupada == true`, spec.md
   FR-012), o alarmas de contenedor sin ningún episodio que
   corresponda a la caída actual — incluido el caso de que el único
   episodio disponible sea de una caída anterior ya resuelta (spec.md
   FR-004/FR-007, Clarifications Q2, research.md §2-§3). Nunca un
   objeto vacío ni un error serializado en su lugar. **Corregido el
   2026-08-11** (hallazgo I1 de `/speckit-analyze`): la versión
   anterior de esta garantía decía que la clave no aparecía en
   absoluto para orígenes ajenos o alarmas agrupadas, contradiciendo
   `data-model.md` y `tasks.md` (T005), que ya asumían la clave
   siempre presente — más simple de implementar (un solo camino de
   código en `add()`, sin añadir la clave condicionalmente por
   origen).
3. **Todas las fechas de `diagnostico` llevan offset explícito** —
   `episodio_fecha` normalizada a `Europe/Madrid`, `diagnostico_fecha`
   en UTC (ya lo era en origen) — el consumidor JS nunca necesita saber
   de dónde venía cada una originalmente (research.md §4).
4. **`gasto_diagnostico` siempre está presente**, incluso sin ningún
   diagnóstico hecho hoy (`coste_eur_acumulado: 0.0` — spec.md User
   Story 3, escenario 2).
5. **Nunca se escribe nada en `diagnostico.db`** desde este productor
   — solo `SELECT` (spec.md FR-010).
6. **Si `diagnostico.db` no está disponible o no se puede leer**, el
   productor devuelve `diagnostico: null` para todas las alarmas y
   `gasto_diagnostico` con ceros — nunca lanza una excepción que rompa
   `/api/data` entero (spec.md FR-008).
