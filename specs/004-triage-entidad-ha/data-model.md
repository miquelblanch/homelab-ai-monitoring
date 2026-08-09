# Data Model — Triaje de Brechas `entidad_ha`

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Este feature no introduce ninguna base de datos ni fichero nuevo. Amplía
`ha_monitor.CHECKS`/`ha_monitor_state.json` (ya existen) y añade un
valor nuevo a un enum cerrado ya existente en `model.py`.

## `ha_monitor.CHECKS` — 50 entradas nuevas

**Automatizaciones (17)**, tipo `entity_state`, `ok_state: "on"`.
`entity_id` real confirmado contra el registro de HA el 2026-08-09 (no es
un slug naive del alias — HA los asigna a su manera, ver por ejemplo
"Botón Toldos Comedor" → `automation.nueva_automatizacion`):

| `id` (check) | `entity` | Alias en HA |
|---|---|---|
| `automation_proyector` | `automation.encender_apagar_proyector` | Encender/Apagar Proyector |
| `automation_boton_toldos_comedor` | `automation.nueva_automatizacion` | Botón Toldos Comedor |
| `automation_bajar_toldos_123` | `automation.bajar_toldo_al_azimut_de_120deg` | Bajar Toldos con Azimut a 123° |
| `automation_subir_toldos_282` | `automation.subir_toldos_en_acimut_280` | Subir Toldos con Azimut a 282° |
| `automation_vacaciones_on` | `automation.modo_vacaciones` | Modo Vacaciones ON |
| `automation_vacaciones_off` | `automation.modo_vacaciones_off` | Modo Vacaciones OFF |
| `automation_toldos_on` | `automation.automatizacion_toldos` | Automatización Toldos ON |
| `automation_toldos_off` | `automation.automatizacion_toldos_off` | Automatización Toldos OFF |
| `automation_boton_stores_comedor` | `automation.boton_stores_comedor` | Botón Stores Comedor |
| `automation_apagar_camaras` | `automation.apagar_camaras` | Apagar Grabaciones Cámaras |
| `automation_sirena_comedor` | `automation.sirena_comedor` | Activación Sirenas Presencia |
| `automation_cumples_icloud` | `automation.cumples_icloud` | Cumples iCloud |
| `automation_interruptor_luz_comedor` | `automation.styrbar_remote_control_for_lights` | Interruptor Luz Comedor |
| `automation_interruptor_luces_salon` | `automation.styrbar_remote_control_for_lights_2` | Interruptor Luces Salón |
| `automation_desbloqueo_cerradura` | `automation.desbloqueo_cerradura` | Desbloqueo Cerradura |
| `automation_bloqueo_cerradura` | `automation.bloqueo_cerradura` | Bloqueo Cerradura |
| `automation_modo_nocturno_cerradura` | `automation.modo_nocturno_control_cerradura` | Modo Nocturno - Control Cerradura |

Forma de cada entrada:

```python
{
    "id":       "automation_proyector",
    "label":    "Encender/Apagar Proyector",
    "type":     "entity_state",
    "entity":   "automation.encender_apagar_proyector",
    "ok_state": "on",
}
```

**Entidades de Frigate (33)**, tipo `entity_available` + campo nuevo
`requires_container: "frigate"`. Confirmadas contra el registro de HA
el 2026-08-09 (`platform: frigate`, `disabled_by: null`):

```text
binary_sensor.camara_cocina_all_occupancy      binary_sensor.camara_salon_all_occupancy
binary_sensor.camara_cocina_motion             binary_sensor.camara_salon_motion
binary_sensor.camara_cocina_person_occupancy   binary_sensor.camara_salon_person_occupancy
camera.camara_cocina                           camera.camara_salon
image.camara_cocina_person                     image.camara_salon_person
sensor.camara_cocina_all_active_count          sensor.camara_salon_all_active_count
sensor.camara_cocina_all_count                 sensor.camara_salon_all_count
sensor.camara_cocina_person_active_count       sensor.camara_salon_person_active_count
sensor.camara_cocina_person_count              sensor.camara_salon_person_count
sensor.camara_cocina_review_status             sensor.camara_salon_review_status
switch.camara_cocina_detect                    switch.camara_salon_detect
switch.camara_cocina_motion                    switch.camara_salon_motion
switch.camara_cocina_recordings                switch.camara_salon_recordings
switch.camara_cocina_review_alerts             switch.camara_salon_review_alerts
switch.camara_cocina_review_detections         switch.camara_salon_review_detections
switch.camara_cocina_snapshots                 switch.camara_salon_snapshots
update.frigate_server
```

(32 repartidas en pares cocina/salón + `update.frigate_server` = 33.)
Forma de cada entrada — `id` de check derivado del `entity_id`
(p. ej. `frigate_camara_cocina_motion` para
`binary_sensor.camara_cocina_motion`), `label` una descripción legible:

```python
{
    "id":                 "frigate_camara_cocina",
    "label":              "Cámara cocina",
    "type":               "entity_available",
    "entity":             "camera.camara_cocina",
    "requires_container": "frigate",
}
```

`requires_container` es el único campo nuevo del esquema de `CHECKS` —
opcional, ausente en los 15 checks existentes. `check_status()` lo
consulta antes de tocar la API de HA (`research.md` §2).

## `ha_monitor_state.json` — sin cambio de esquema

Cada una de las 50 claves nuevas usa el mismo formato que ya define
`heartbeat`/`ha_monitor.py` para las 15 actuales:

```json
{
  "automation_desbloqueo_cerradura": {
    "ok": true,
    "down_since": null,
    "label": "Desbloqueo Cerradura",
    "motivo": "",
    "detail": "state=on"
  },
  "frigate_camara_cocina": {
    "ok": true,
    "down_since": null,
    "label": "Cámara cocina",
    "motivo": "",
    "detail": "Frigate parado — no aplica"
  }
}
```

Cuando `requires_container` bloquea el check (contenedor parado),
`ok=true` y `motivo=""` — mismo criterio que "intencionado" en el resto
del inventario: no es una brecha, es una comprobación que no aplica
ahora mismo, no una comprobación que falló (`research.md` §2).

## Tipo de brecha nuevo — `model.py::TIPOS_BRECHA`

```python
TIPOS_BRECHA = (
    "sin_declaracion",
    "declaracion_caducada",
    "sin_vigilancia",
    "no_llega_a_dashboard",
    "riesgo_concentrado_telegram",
    "condicion_incumplida",   # nuevo
)
```

**Cuándo se produce**: `tiene_estado_declarado=True` (el componente está
en `ha_monitor.CHECKS`) pero `esta_vigilado=False` (el último resultado
real tiene `ok=false`) — `research.md` §4. Se distingue de
`sin_vigilancia`, que sigue significando "nadie lo comprueba en
absoluto".

**Mensaje** (`evaluate.py::gap_context()`): *"'{nombre}' ({categoria})
tiene un estado esperado declarado y vigilado, pero su último resultado
real no lo cumple: {detalle}."* — usa el `detail` que ya trae
`ha_monitor_state.json` para esa entidad, sin duplicar la lógica que
decide el mensaje.

## `is_intentional()` — exclusiones nuevas en `sources.py`

```python
# Excepciones de seguridad — fuera del alcance de este feature
# (spec.md, Assumptions). No se declaran ni se comprueban aquí.
ENTIDAD_HA_EXCEPCIONES_SEGURIDAD = {
    "binary_sensor.cerradura_amsterdam_9_battery_critical",
    "binary_sensor.cerradura_amsterdam_9_battery_charging",
    "binary_sensor.caseta_tapo_p115_caseta_sobrecargado",
    "binary_sensor.tapo_p115_datacenter_sobrecargado",
    "binary_sensor.tapo_p115_mac_mini_sobrecargado",
}

# Entidades de Frigate — se rigen por el check condicionado a
# requires_container, no por la regla genérica de entity_category.
#
# FALLBACK, no fuente de verdad: entidad_ha_frigate() (más abajo) usa
# esto solo si ha_monitor.CHECKS todavía no tiene las 33 entradas
# (antes de desplegar User Story 3) — research.md, nota de
# sincronización (hallazgo M1 de /speckit-analyze). Misma lista que las
# 33 entradas de ha_monitor.CHECKS de arriba, por eso puede quedar
# desactualizada sin que importe una vez la lista en vivo manda.
_ENTIDAD_HA_FRIGATE_FALLBACK = {
    "binary_sensor.camara_cocina_all_occupancy",
    "binary_sensor.camara_cocina_motion",
    "binary_sensor.camara_cocina_person_occupancy",
    "binary_sensor.camara_salon_all_occupancy",
    "binary_sensor.camara_salon_motion",
    "binary_sensor.camara_salon_person_occupancy",
    "camera.camara_cocina",
    "camera.camara_salon",
    "image.camara_cocina_person",
    "image.camara_salon_person",
    "sensor.camara_cocina_all_active_count",
    "sensor.camara_cocina_all_count",
    "sensor.camara_cocina_person_active_count",
    "sensor.camara_cocina_person_count",
    "sensor.camara_cocina_review_status",
    "sensor.camara_salon_all_active_count",
    "sensor.camara_salon_all_count",
    "sensor.camara_salon_person_active_count",
    "sensor.camara_salon_person_count",
    "sensor.camara_salon_review_status",
    "switch.camara_cocina_detect",
    "switch.camara_cocina_motion",
    "switch.camara_cocina_recordings",
    "switch.camara_cocina_review_alerts",
    "switch.camara_cocina_review_detections",
    "switch.camara_cocina_snapshots",
    "switch.camara_salon_detect",
    "switch.camara_salon_motion",
    "switch.camara_salon_recordings",
    "switch.camara_salon_review_alerts",
    "switch.camara_salon_review_detections",
    "switch.camara_salon_snapshots",
    "update.frigate_server",
}


def entidad_ha_frigate() -> set[str]:
    """Entidades de Frigate para is_intentional() — prioriza la lista
    en vivo de ha_monitor.CHECKS (una vez desplegado User Story 3);
    cae al fallback fijo mientras esa lista esté vacía (antes de
    desplegar US3), para no acoplar US1 a US3 (research.md, nota de
    sincronización)."""
    return bridge.ha_monitor_conditional_entities() or _ENTIDAD_HA_FRIGATE_FALLBACK
```

`is_intentional()` (`evaluate.py`) consulta
`ENTIDAD_HA_EXCEPCIONES_SEGURIDAD` y `entidad_ha_frigate()` junto con
`entity_category` para decidir si una entidad `config`/`diagnostic`
cuenta como intencionada (`research.md` §3).

## `_homelab_bridge.py` — función nueva

```python
def ha_monitor_conditional_entities() -> set[str]:
    """entity_id de los checks de ha_monitor.py con requires_container
    — mismo patrón que ha_monitor_checked_entities(), filtrado a los
    condicionados a que un contenedor esté corriendo. Vacío si
    ha_monitor.py no está disponible o todavía no tiene esos checks
    (antes de desplegar User Story 3) — nunca lanza."""
    if _ha_monitor is None:
        return set()
    try:
        return {
            c["entity"] for c in getattr(_ha_monitor, "CHECKS", [])
            if c.get("requires_container")
        }
    except Exception:
        return set()
```
