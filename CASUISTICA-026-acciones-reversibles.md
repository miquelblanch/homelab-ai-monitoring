# Casuística — feature 026, ampliar acciones sobre el inventario

> Material de trabajo, no spec. Recoge, componente a componente, si hay o no una
> acción de remediación real, con qué mecanismo, y por qué sí o por qué no. Nace de
> la conversación del 2026-08-15/16 en la que Miquel respondió, uno por uno, a los
> "fuera de alcance" del primer borrador de `BRIEFING.md` (sección Feature 026).

## Antes de la tabla: dos ofrecimientos que no se aceptan tal cual

Miquel ofreció la contraseña de `sudo` (para `com.homeassistant.*`) y la contraseña
SSH de los hosts externos (para `host_externo`) directamente en la conversación. No
se usan así:

- **Regla 1 del `CLAUDE.md` general**: ninguna credencial se hardcodea ni se pasa en
  claro — va en `.secrets/*.env`, y una contraseña pegada en un chat es exactamente
  el tipo de exposición que esa regla quiere evitar (queda en el historial de la
  sesión, no solo en un fichero con permisos 600).
- Además, para estos dos casos concretos, la contraseña ni siquiera es la
  herramienta correcta:
  - **`com.homeassistant.*`**: en vez de una contraseña de `sudo` de uso general,
    lo que hace falta es una regla `NOPASSWD` en `/etc/sudoers.d/` acotada al
    comando exacto (`launchctl kickstart -k system/com.homeassistant.<label>`, uno
    por uno o por patrón) — así el proceso de remediación nunca tiene sudo de
    verdad, solo permiso para ese comando concreto. Auditable y revocable con una
    línea.
  - **`host_externo`**: ya existe una clave SSH en `~/.ssh/` (`id_ed25519`) y el
    propio hub de Beszel ya usa una clave propia para llegar a estos mismos hosts
    (nota de Beszel en el `CLAUDE.md` general: "se comprobó llamándolos desde el Mac
    con la propia clave SSH del hub"). Antes de generar nada nuevo, comprobar si esa
    clave (o una prestada del hub) ya tiene acceso — y si no, generar una clave
    dedicada de solo-ese-uso, nunca una contraseña compartida por chat.

Esto no bloquea la feature — al contrario, ambos casos pasan a "sí, automatizable",
solo que con el mecanismo correcto en vez del ofrecido.

## Tabla completa

| # | Componente | N | ¿Automatizable? | Acción / mecanismo real | Motivo / condición |
|---|---|---:|---|---|---|
| 1 | `contenedor` no crítico | 39 | **Sí — ya dentro** | `reiniciar_contenedor` (021) | Ya en producción, sin cambios en esta feature |
| 2 | `contenedor` crítico | 12 | **No, fase 2** | — | Confirmado por Miquel: se aparca a propósito. Sigue protegido por la regla 3 del `CLAUDE.md` general y el Principio VII — solo DeepSeek *propone*, nunca ejecuta (022) |
| 3 | `amsterdam9.*` (LaunchAgents usuario) | 32 | **Sí** | `reiniciar_agente`: `launchctl kickstart -k gui/$(id -u)/<label>` | Sin privilegios especiales, sin precedente de automatización previa (hoy solo se sugiere por texto) |
| 3a | ...de los cuales, monitores/remediación que se vigilan a sí mismos (`amsterdam9.health.*`, `amsterdam9.verify-backups`, `amsterdam9.bautista.heartbeat`, `amsterdam9.remediacion.comprobar`, `amsterdam9.dashboard.launchagents`) | 7 | **Sí — decidido** | Misma acción que 3, sin excepción | Decisión de Miquel (2026-08-16): entran con el mismo patrón de bajo riesgo que el resto — un reinicio no destruye nada, igual que `reiniciar_contenedor` no distingue "vigilante" de otro contenedor no crítico |
| 4 | `com.homeassistant.*` (LaunchDaemons root) | 11 | **Sí, con sudoers acotado** | `launchctl kickstart -k system/<label>` vía regla `NOPASSWD` limitada al comando exacto | Ver nota de arriba — no se acepta una contraseña de sudo genérica, sí un permiso de comando único |
| 5 | `Relay: *` (vista de `socat_relays.json`) | 10 | **Sí, indirectamente** | Ninguna acción propia — se resuelve el hallazgo reiniciando el LaunchAgent/LaunchDaemon subyacente (grupos 3 o 4) | Primero hay que emparejar cada `Relay: X` con su proceso real (hoy son dos componentes de inventario distintos para la misma cosa física) — una vez emparejados, **no hace falta una acción nueva**, la que ya cubre al proceso cubre también al relay |
| 6 | "Backup diario" / "Recordatorios Nextcloud" (vistas funcionales) | 2 | **Sí — ya cubiertos** | Ninguna acción propia — son la misma cosa que `amsterdam9.backups` y `amsterdam9.bautista.calendar`, ya contados en el grupo 3 | Confirmado: mismo problema de identidad duplicada que el grupo 5, no dos componentes reales |
| 7 | `cron: *` (jobs de Hermes: `dreaming` 03:00 diario, `noticias-ia` mar/jue 07:30, `homelab-optimizer-weekly` domingo 03:00, `gbrain-weekly-purge` sábado 03:00) | 4 | **Sí, en los 4 — decidido** | `hermes cron run <id>` — comando ya soportado por la CLI de Hermes ("Run a job on the next scheduler tick") | No hace falta cambiar la regla 4 del `CLAUDE.md` general: `hermes cron run` es la vía oficial de Hermes, no una modificación directa del LaunchAgent. Riesgo real evaluado por job: `gbrain-weekly-purge` es el más seguro (purga por antigüedad, re-ejecutar no duplica nada); `noticias-ia` y `homelab-optimizer-weekly` son de bajo riesgo (solo reenvían un resultado a Telegram); `dreaming` es el más delicado (procesa una ventana de 24h, un re-disparo podría solapar). Decisión de Miquel (2026-08-16): empezar con auto-retry en los 4 igual, revisar si `dreaming` da problemas en la práctica |
| 8 | `infra_monitorizacion` → `Beszel (hub)` | 1 | **Sí — ya dentro** | Cablear al `reiniciar_contenedor` ya existente sobre el contenedor `beszel` | Es el mismo software visto desde otro ángulo, no un sistema nuevo |
| 9 | `infra_monitorizacion` → resto (`docker_monitor.py`, `ha_monitor.py`, `dns_pi_monitor.py`, `heartbeat.py`, `verify_backups.py`) | 5 | **Ya contados** | Son los mismos procesos que el grupo 3a (`amsterdam9.health.*`, etc.) | No es un grupo aparte — mismo componente visto por dos categorías de inventario |
| 10 | `entidad_ha`, atacado por **dispositivo** en vez de por entidad — desglose real (`core.entity_registry`, 696 entidades, 650 con `device_id`) | **65 dispositivos** (62 con alguna entidad activa) | Depende de la plataforma — ver 10a-10f | Comprobado en vivo: 696 entidades registradas ≠ 340 con estado ahora mismo (muchas deshabilitadas a propósito) ni ≠ los 65 dispositivos físicos/lógicos que las agrupan |
| 10a | ...MQTT/Zigbee (vía Z2M) | 16 | **No, mayoría** | — | La mayoría son sensores de batería "sleepy" sin concepto de reinicio — el fallo típico es la pila, no el software. El candidato real de acción está en el **coordinador Zigbee** (SLZB-06U), no en cada sensor — y ese coordinador **ni siquiera está en el inventario de relays hoy** (no aparece en `socat_relays.json`). Gap real, pero aparte de esta feature |
| 10b | ...ESPHome, Broadlink, Shelly, Android TV, Marantz (denonavr/heos) | 6 | **Sí, pero ya cubierto** | Restart de su relay correspondiente (grupo 4, `com.homeassistant.*`) | Es la misma acción que el grupo 4 — no hace falta una acción "por dispositivo" nueva, restablecer el relay ya arregla el dispositivo que hay detrás |
| 10c | ...HACS — plugins de dashboard y wrappers de integraciones instaladas vía HACS, no hardware: `Weather Card`, `Met.no next 6 hours forecast`, `Scheduler Card`, `Tapo: Cameras Control`, `Better Thermostat UI`, `Advanced Camera Card`, `Frigate` (integración), `Tapo Controller`, `Flex Table`, `ZHA Toolkit`, `HACS`, `Battery State Card`, `mini-graph-card`, `Scheduler component`, `WebRTC Camera` | 15 | **No — ni acción ni vigilancia, y ya es así hoy** | — | Decisión de Miquel: no se borra nada de HA, pero tampoco tiene sentido vigilarlos ni intentar repararlos. **Comprobado que ya es el comportamiento actual**: las 30 entidades que cuelgan de estos 15 dispositivos son todas `switch.*_pre_release` (activar actualizaciones beta) o `update.*_update` (aviso de actualización), `entity_category` `diagnostic`/`config` en los dos casos — y la regla general de `evaluate.py:181` (desde la feature 006) ya excluye esas categorías de contar como brecha. Nada que cambiar |
| 10d | ...Jellyfin (clientes reproductor): `Amterdam 9 Music`, 2× `iPhone` (Finamp), `Iphone Miquel` (Jellyfin iOS) | 4 | **No — resuelto en origen** | Quitar la integración Jellyfin de HA (fuera de este repo) | Confirmado con Miquel: Jellyfin se gestiona fuera de HA. Al quitar la integración, el inventario deja de verlos solo, sin tocar código |
| 10e | ...mobile_app: `Iphone Miquel` (iPhone18,1), `iPhone de CECILE` (iPhone14,5), `MacBook Air de Miquel` (Mac14,2) | 3 (2 móviles + 1 portátil) | **No** | — | No son dispositivos del homelab — son clientes que se conectan a él. Corrección: el tercero no es un móvil, es el MacBook Air (la app de HA también corre en macOS) |
| 10f | ...MELCloud (aire acondicionado, vía nube del fabricante) | 3 | **No** | — | Mediado 100% por la nube de Mitsubishi — no hay ninguna vía local de reinicio |
| 10g | ...cámaras reales: `tapo_control` (`Cámara Cocina TP-Link`, `Cámara Salón TP-Link`, modelo C210) + `frigate` (las mismas 2 vistas por Frigate + el NVR `Frigate`) | 2+3 | **No** | — | `frigate` es `NEVER_RESTART` (regla 2 del `CLAUDE.md` general); las cámaras están físicamente desconectadas |
| 10h | ...**no son cámaras — enchufes inteligentes de consumo** (`tplink`): `Tapo P115 Mini PC`, `Tapo P115 Datacenter`, **`Tapo P115 Mac Mini`** | 3 | **No — exclusión permanente, no solo ausencia** | — | Corrección sobre el borrador anterior, que los agrupaba mal con las cámaras. `switch.tapo_p115_mac_mini` controla la alimentación de **este mismo Mac Mini** — la máquina que corre todo el homelab, incluida la propia remediación. `switch.tapo_p115_datacenter` probablemente controla el rack/equipo de red. Cualquier feature futura que trate "dispositivos con entidad `switch`" como candidatos genéricos DEBE excluir estos 3 por nombre, no por categoría — el riesgo es real: un fallo del agente podría apagar el servidor que lo ejecuta |
| 11 | `host_externo` (AdGuard Pi, Uptime Kuma) | 2 | **Sí, con clave SSH** | A definir (reinicio de servicio vía SSH) — condicionado a qué comando exacto tiene sentido en cada host | Ya monitorizados hoy vía Beszel (confirmado: `mecanismo_vigilancia = "Beszel (vía relay socat)"` en ambos) — lo que faltaba era la acción, no la vigilancia. Usar clave SSH existente o dedicada, nunca contraseña compartida |
| 12 | `telegram` (canal de aviso) | 1 | **No es remediable — es otra feature** | Canal secundario (correo) como *fallback* de aviso | Buena idea de Miquel, pero es resiliencia del aviso (Principio I), no una acción de remediación sobre el componente — encajaría mejor como feature propia, no dentro de la 026 |
| 13 | `hermes` (el propio agente) | 1 | **No** | — | Es el agente que decide — reiniciarlo a sí mismo desde su propia capa de decisión es el mismo problema de circularidad que el grupo 3a, aún más agudo |

## Recuento — cuánto entra de verdad si se resuelve todo lo de arriba

| Bloque | N |
|---|---:|
| Ya dentro hoy (contenedores no críticos) | 39 |
| Nuevo, sin condiciones (`amsterdam9.*` no-monitor, Beszel hub cableado, "vigilantes" incluidos) | 33 |
| Nuevo, condicionado a sudoers acotado (`com.homeassistant.*`) | 11 |
| Nuevo, decidido — auto-retry en los 4 (`hermes cron run`) | 4 |
| Nuevo, condicionado a clave SSH + comando por host — Kuma confirmado Docker, Pi pendiente | 2 |
| **Total potencial** | **89 de 792** |
| Cubiertos indirectamente sin acción propia (`Relay:*`, vistas duplicadas, dispositivos-ya-cubiertos-por-su-relay) | 18 |
| Fuera, sin vía real (hardware, nube, clientes, off-limits) | ~665 |
| Fuera, fase 2 explícita (críticos) | 12 |
| Fuera, es otra feature (canal de aviso secundario) | 1 |

**89 de 792 (11%)** es el techo real si se aprueban todos los "sí" de esta tabla —
frente a los ~72 del borrador anterior. La diferencia la ponen sobre todo el
`sudo` acotado (11) y `hermes cron run` (4), no una reinterpretación de la
reversibilidad: casi todo lo de esta tabla sigue siendo una acción de bajo riesgo
sin operación de deshacer explícita, exactamente como `reiniciar_contenedor` desde
021 — el Principio VI no fue nunca el obstáculo real, como ya se vio en la vuelta
anterior de esta conversación.

## Decisiones ya cerradas (2026-08-16)

1. **Grupo 4 (`com.homeassistant.*`)**: sudoers acotado, comando exacto, sin
   comodín — texto propuesto arriba, sección "1", listo para `/speckit-plan`.
2. **Grupo 11 (`host_externo`)**: Uptime Kuma corre en Docker (confirmado por
   Miquel) → `docker restart <contenedor>` vía SSH. **AdGuard/Pi sigue sin
   confirmar** — intenté comprobarlo yo mismo (hay una entrada en
   `~/.ssh/known_hosts` que prueba una conexión SSH previa desde este Mac, pero la
   clave `id_ed25519` actual no está autorizada ni como `pi` ni como
   `miquelblanch`). No se sigue probando usuarios a ciegas — pendiente de que
   Miquel confirme el usuario correcto o genere una clave nueva.
3. **Grupo 7 (`cron: *` de Hermes)**: auto-retry en los 4 jobs desde el principio
   (decisión de Miquel), con el riesgo de `dreaming` anotado para revisar si da
   problemas en la práctica.
4. **Grupo 3a/9 ("quién vigila al vigilante")**: entran en `reiniciar_agente` sin
   excepción, mismo patrón de bajo riesgo que el resto.
5. **Canal de aviso secundario**: se abre como **feature 027**, aparte de la 026 —
   material de partida añadido a `BRIEFING.md`.
6. El coordinador Zigbee sin cobertura de relay (10a) — gap real encontrado de
   pasada, no pedido por nadie: anotado para un barrido futuro, no se resuelve aquí.
7. **No negociable, no solo pendiente**: los 3 enchufes Tapo P115 (10h) —
   especialmente `Tapo P115 Mac Mini`, que controla la alimentación de la máquina
   que corre todo esto — deben quedar excluidos por nombre de cualquier acción
   presente o futura sobre entidades `switch`, no solo ausentes de esta feature por
   no haberlos incluido. Vale la pena escribirlo como excepción explícita en
   `/speckit-specify`, con el mismo peso que `NEVER_RESTART` para contenedores.
