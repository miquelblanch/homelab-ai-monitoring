# Quickstart — Validar el triaje de brechas `entidad_ha`

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/ficheros.md](./contracts/ficheros.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `ha_monitor.py` desplegado con las 50 entradas nuevas en `CHECKS`.
- Al menos un ciclo de `ha_monitor.py` completado tras el despliegue
  (hasta 15 min, o ejecutarlo a mano una vez).

## 1 — La regla de `entity_category` cierra ~115 brechas (User Story 1)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep -c "^❌ \[entidad_ha\]"
```

**Esperado**: el recuento baja en al menos 115 respecto a las 309
brechas de referencia (2026-08-09) — comparar antes/después. Las 5
excepciones de seguridad (`sensor.cerradura_amsterdam_9_battery_*`,
`*_sobrecargado`) siguen apareciendo:

```bash
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep "sobrecargado\|battery_critical\|battery_charging"
```

## 2 — Una automatización doméstica desactivada cuenta como brecha real (User Story 2)

```bash
# Desactivar una automatización no crítica a mano en HA (UI o API),
# esperar al siguiente ciclo de ha_monitor.py, y comprobar:
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep "automation\."
```

**Esperado**: la automatización desactivada aparece con tipo
`condicion_incumplida`, no `sin_declaracion` — la distinción que pide el
escenario 2 de `User Story 2`. Volver a activarla y comprobar que deja
de aparecer en el siguiente ciclo.

## 3 — Frigate parado no genera brechas (User Story 3, escenario 1)

```bash
docker ps --format "{{.Names}}\t{{.Status}}" | grep frigate   # confirmar que está parado
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep -c "camara_\|frigate"
```

**Esperado**: 0 (salvo que aparezca por otra vía ajena a este feature).

## 4 — Frigate corriendo con datos reales no genera brechas (escenario 2)

```bash
docker start frigate   # o el mecanismo que Miquel use para encenderlo
# esperar al siguiente ciclo de ha_monitor.py (hasta 15 min)
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep -c "camara_\|frigate"
```

**Esperado**: 0, con las cámaras dando datos reales (mismo estado
verificado en vivo el 2026-08-09: 14 fps en las dos).

## 5 — Frigate corriendo con una entidad rota sí genera brecha (escenario 3, SC-004)

No hay forma segura de forzar esto contra el sistema real sin romper
algo a propósito. Validar por inspección: parar uno de los relays
`amsterdam9.frigate.relay-cocina`/`-salon` (`launchctl bootout`) con
Frigate corriendo, esperar un ciclo, y comprobar que las entidades de
esa cámara concreta (`camera.camara_cocina`, sus `binary_sensor`, etc.)
aparecen como `condicion_incumplida`. Restaurar el relay
(`launchctl bootstrap`) al terminar.

## 6 — El resto del inventario sigue funcionando (regresión)

```bash
PYTHONPATH=src python3 -m inventory.cli --selftest
```

**Esperado**: todo en verde, incluidos los checks ya existentes de
`test_evaluate.py` — el cambio de contrato de `esta_vigilado`
(`research.md` §4) no debe romper ninguna aserción ya escrita para las
otras categorías (`contenedor`, `host_externo`, `infra_monitorizacion`,
etc.), que no tocan `entidad_ha`.
