# Contrato — Clave `alarms` en `/api/data`

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Sin CLI ni endpoint nuevo (mismo patrón que features 002/003): el
contrato es una clave más dentro del JSON que `/api/data` ya devuelve
en cada petición del dashboard.

## Productor

`get_active_alarms()` en `homelab-dashboard/scripts/app.py`, llamada
desde el mismo punto de `collect()` donde ya se llaman
`get_containers()`, `get_ha_monitor()`, `get_inventory()`, etc.

## Consumidor

El JavaScript embebido en la plantilla HTML del dashboard, en la
pestaña nueva `#alarmas` — mismo patrón de lectura que ya usa
`render(d)` para `d.inventory`, `d.containers`, etc.

## Forma del payload

```json
{
  "alarms": {
    "total": 2,
    "items": [
      {
        "origen": "discos",
        "tipo": "disco_aviso",
        "nivel": "aviso",
        "componente": "FastData",
        "mensaje": "78%",
        "explicacion": "Un disco ha superado el 75% de uso.",
        "remediacion": "Revisar qué está creciendo...",
        "antiguedad_s": null,
        "agrupada": false,
        "cantidad": 1
      },
      {
        "origen": "ha",
        "tipo": "ha_entidad_no_disponible",
        "nivel": "aviso",
        "componente": "23 entidades de Home Assistant",
        "mensaje": "23 checks en unavailable/unknown",
        "explicacion": "Una entidad de Home Assistant está unavailable...",
        "remediacion": "Comprobar el dispositivo físico...",
        "antiguedad_s": 340,
        "agrupada": true,
        "cantidad": 23
      }
    ]
  }
}
```

## Garantías

1. **`items` nunca omite una condición de fallo real** (Principio XII,
   FR-008/FR-010): un tipo sin entrada en `ALARM_TYPES` aparece
   igualmente, con `explicacion`/`remediacion` fijas a los textos de
   aviso de "no documentado todavía" — nunca se descarta el elemento.
2. **`total` cuenta entradas de la lista, no alarmas individuales**:
   con una entrada agrupada, `total` suma 1 por esa entrada, y
   `cantidad` dentro de ella lleva el recuento real (FR-013, SC-005).
3. **`items` viene pre-ordenado** por `nivel` (crítico → aviso →
   informativo) y, dentro del mismo nivel, por `antiguedad_s`
   descendente cuando existe (FR-004) — el consumidor no tiene que
   reordenar nada.
4. **Ausencia total de alarmas** se representa con `items: []` y
   `total: 0`, nunca con la clave `alarms` ausente — el consumidor
   siempre puede confiar en que la clave existe (FR-010).
5. **Ningún campo de `items` permite ejecutar nada** (FR-009): son
   todos de solo lectura; no hay ningún id de acción ni endpoint de
   escritura asociado.
6. **Si uno de los 10 orígenes falla al leer su propio dato**,
   `get_active_alarms()` añade una alarma `origen_sin_datos` para ese
   origen en vez de propagar la excepción — mismo principio "a prueba
   de fallos" que ya usa el resto de `app.py` (por ejemplo,
   `get_docker_monitor_state()` devuelve `{}` en vez de lanzar).

## Fuera de este contrato

- El esquema interno de cada origen (`docker_monitor_state.json`,
  `ha_monitor_state.json`, etc.) — ya está descrito en los contratos de
  features 001-003; este feature solo los lee, no los cambia.
- Cualquier acción sobre el homelab — no existe ningún endpoint de
  escritura en este feature (FR-009).
