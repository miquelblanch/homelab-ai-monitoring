# Contrato — Ficheros y latidos de este feature

**Feature**: [../spec.md](../spec.md)

Sin CLI ni API HTTP nueva (mismo patrón que feature 002): el contrato
externo son los latidos que ya lee `app.py` y una ampliación de un
fichero que ya existe.

## Latido `bautista-calendar` (nuevo)

**Productor**: `bautista-calendar.sh`, al final de cada ejecución diaria
(10:00).

**Consumidor**: `get_monitor_heartbeats()` en `app.py`, vía la entrada
nueva en `MONITOR_JOBS` — mismo contrato que ya usan los otros 6
monitores (docker-monitor, ha-monitor, dns-pi-monitor, verify-backups,
telegram-monitor, beszel-hosts).

**Garantías**:

1. Se escribe tanto si el cron manda recordatorios reales, como si calla
   porque no hay eventos, como si detecta y reporta un error real de los
   calendarios — las tres son "el cron completó su ciclo" (FR-001).
2. El `detail` es siempre una de tres etiquetas fijas elegidas por el
   propio script — nunca contenido derivado de los eventos del
   calendario (`research.md` §1, riesgo de inyección de comandos).
3. Si el script falla **antes** de calcular su resultado (por ejemplo,
   sin credenciales de Telegram), el latido de ese día no se escribe —
   es la señal correcta, no un caso a tratar aparte (Edge Cases,
   `spec.md`).

## `beszel_hosts.json` — clave `hub_systems` (ampliación)

**Productor**: el mismo `scripts/beszel_hosts_monitor.py` de feature 002,
sin script nuevo.

**Consumidor**: una función nueva en `app.py` que decide sano/no-sano
para el mecanismo de vigilancia de Beszel.

**Esquema**: ver `data-model.md`.

**Garantías** (adicionales a las 3 que ya establece
`specs/002-alarmas-al-dashboard/contracts/ficheros.md` para este mismo
fichero — siguen vigentes sin cambios):

4. `hub_systems` incluye **todos** los sistemas que Beszel tiene
   registrados, no solo los 2 hosts canónicos de `hosts` — hoy son 3
   (Mac Mini, Uptime Kuma, AdGuard Home); si Beszel llegara a vigilar
   alguno más, aparecería aquí sin cambio de código.
5. Los valores de `hub_systems` son el dato de `updated` tal cual lo
   reporta Beszel, sin traducir ni redondear — la decisión de "¿es
   viejo?" es responsabilidad exclusiva del consumidor (`app.py`), nunca
   del productor (mismo principio que la garantía 2 de feature 002 para
   `status`).

## "Estado de vigilancia de Beszel (hub)" en el panel "Estado de los monitores"

**Productor**: función nueva en `app.py`, calculada en cada carga —no
persistida.

**Consumidor**: la fila añadida a mano al render de "Estado de los
monitores", mismo patrón que ya usan las filas "heartbeat.py" y "Backup
diario" (`research.md` §4) — no pasa por `MONITOR_JOBS`.

**Garantía**: `sano` es `false` únicamente cuando los 3 sistemas de
`hub_systems` superan 900 s (15 min) de antigüedad **a la vez** (FR-004,
Clarifications) — un solo sistema viejo, con los otros frescos, no
cambia este valor.

## Fuera de este contrato

- El propio latido `beszel-hosts` (ya existe, feature 002) sigue
  respondiendo solo a "¿sigue vivo `beszel_hosts_monitor.py`?" — este
  feature no lo modifica, y lo reutiliza tal cual para cumplir FR-008 sin
  crear un segundo latido para el mismo proceso (Edge Cases, `spec.md`).
- El esquema interno de la tabla `systems` de Beszel más allá de `name`,
  `status` y `updated` — dependencia de implementación ya aceptada por
  feature 002 (`research.md` §3 de esa feature).
