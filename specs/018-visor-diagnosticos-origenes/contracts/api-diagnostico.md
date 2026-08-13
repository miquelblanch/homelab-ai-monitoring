# Contrato — Campo `diagnostico` en `/api/data` (generalizado a 10 orígenes)

**Feature**: [../spec.md](../spec.md) · **Modelo**: [../data-model.md](../data-model.md)

Extiende `specs/008-visor-diagnosticos-correcciones/contracts/api-diagnostico.md`
— la forma del payload no cambia, `gasto_diagnostico` no cambia. Lo que
cambia es qué orígenes pueden traer `diagnostico` no nulo, y se
corrige el bug de contenedor (research.md §1).

## Productor

`get_diagnostico_para_origen(origen, identidad, down_since=None)` en
`homelab-dashboard/scripts/app.py` (research.md §3), sustituye a
`get_diagnostico_para_alarma()` (008). Llamada desde las 10 ramas de
`get_active_alarms()` (data-model.md), cada una con su propia
`identidad` real — no siempre la etiqueta visible de la alarma.

## Consumidor

Sin cambios — el JavaScript embebido de la pestaña `#alarmas`
(`renderAlarmas()`/`diagnosticoHtml()`) ya es agnóstico al origen
(research.md §2).

## Forma del payload

Sin cambios de forma respecto al contrato de 008 — ver ese fichero
para el ejemplo completo. Lo nuevo es que `diagnostico` puede venir
poblado también para `ha`, `discos`, `backup`, `relays`,
`hosts_externos`, `beszel_hub`, `agentes` (LaunchAgents) e
`inventario`, no solo `contenedores`:

```json
{
  "origen": "ha",
  "tipo": "ha_entidad_no_disponible",
  "componente": "sensor.ejemplo",
  "diagnostico": {
    "episodio_fecha": "2026-08-13T10:15:00+02:00",
    "diagnostico_fecha": "2026-08-13T08:16:02+00:00",
    "conclusion_tipo": "no_diagnosticable",
    "conclusion_texto": "...",
    "hipotesis": [ ]
  }
}
```

## Garantías (además de las ya vigentes en el contrato de 008)

7. **El emparejamiento de contenedor vuelve a funcionar** — la
   consulta filtra por `componente`+`origen`, nunca por la columna
   `contenedor` ya inexistente (research.md §1, spec.md FR-001/SC-001).
8. **La identidad usada para emparejar es siempre la real de
   `diagnostico.db` para ese origen**, no necesariamente la etiqueta
   que muestra la alarma (data-model.md: `cid` para HA, `job` para
   latido, `label` completo para agente, nombre canónico para host
   externo) — un emparejamiento por la etiqueta de pantalla habría
   fallado en falso para los cuatro.
9. **`backup` y `hub_beszel` muestran el episodio más reciente de su
   origen, sin comprobación de nombre** — su `componente` real es un
   momento ISO, no una identidad estable (spec.md FR-005).
10. **Ninguna alarma de Crons de Hermes lleva nunca `diagnostico`** —
    ningún origen de `diagnostico.py` los cubre (spec.md FR-006).
11. **`relay` solo empareja diagnósticos hechos en vivo por nombre
    concreto** — un episodio en diferido de ese origen nunca identifica
    cuál relay, así que nunca produce una coincidencia (limitación real
    del origen, spec.md Assumptions).
12. **Cada origen se resuelve en su propio bloque `try/except` dentro
    de `get_active_alarms()`** — un fallo de emparejamiento de un
    origen (por ejemplo, `diagnostico.db` bloqueado un instante) nunca
    deja sin alarmas a los demás (spec.md FR-009).
