# Quickstart — Validar la regla de móvil y el backup de HA

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/ficheros.md](./contracts/ficheros.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `ha_monitor.py` desplegado con la entrada nueva en `CHECKS`.
- Al menos un ciclo de `ha_monitor.py` completado tras el despliegue.

## 1 — La regla de `mobile_app` cierra 53 brechas (User Story 1)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep -c "^❌ \[entidad_ha\]"
```

**Esperado**: el recuento baja en al menos 53 respecto a la referencia
de 150 (2026-08-09). Comprobar también que ninguna entidad ajena a la
app móvil cambia de clasificación:

```bash
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard \
  | grep -c "iphone_\|macbook_air"
```

**Esperado**: 0.

## 2 — El backup de HA cuenta como brecha real si está viejo (User Story 2)

```bash
curl -s "$HA_URL/api/states/sensor.backup_ultima_copia_de_seguridad_automatica_realizada_correctamente" \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -m json.tool
```

(`HA_URL`/`HA_TOKEN` ya existen como variables de entorno para `ha_monitor.py` — no se hardcodea la IP real, mismo criterio de "Repositorio público" que el resto del proyecto)

**Esperado, con la copia reciente (caso normal)**: el inventario no
marca `ha_backup_reciente` como brecha.

Para el caso de brecha real, no hay forma segura de forzar que Home
Assistant deje de hacer copias. Validar por inspección de código +
dato sintético: con una copia temporal de `ha_monitor_state.json`,
comprobar que si `ha_backup_reciente.ok` es `false`, el inventario lo
clasifica como `condicion_incumplida` (mismo mecanismo ya validado en
`quickstart.md` de feature 004 para las automatizaciones).

## 3 — El resto del inventario sigue funcionando (regresión)

```bash
PYTHONPATH=src python3 -m inventory.cli --selftest
```

**Esperado**: todo en verde — la condición nueva de `is_intentional()`
y el tipo de check nuevo no deben romper ninguna aserción ya escrita
para otras categorías ni para las reglas de feature 004.
