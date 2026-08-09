# Data Model — Central de Alarmas del Homelab

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Sin base de datos ni fichero nuevo. Dos estructuras, las dos calculadas
en memoria en cada petición a `/api/data` — nada se persiste.

## Alarma activa

Producida por `get_active_alarms()`. Instancia individual, o una
entrada agrupada cuando aplica FR-013.

| Campo | Tipo | Obligatorio | Significado |
|---|---|---|---|
| `origen` | string | Sí | Uno de los 10 orígenes (`contenedores`, `ha`, `backup`, `monitores`, `relays`, `hosts_externos`, `beszel_hub`, `agentes`, `discos`, `inventario`) |
| `tipo` | string | Sí | Id de una entrada de `ALARM_TYPES` (tabla de abajo) |
| `nivel` | string | Sí | `critico` / `aviso` / `informativo` — copiado de `ALARM_TYPES[tipo]`, nunca decidido por instancia |
| `componente` | string | Sí | Nombre del contenedor/entidad/host afectado; si `agrupada` es `true`, una descripción del grupo (p. ej. "113 checks de Home Assistant") |
| `mensaje` | string | Sí | El dato en bruto que el origen ya calculó (p. ej. `state=unavailable`, `Exited (1)`, `92%`) |
| `explicacion` | string | Sí | Copiado de `ALARM_TYPES[tipo].explicacion`, o el aviso fijo de "sin explicación documentada todavía" (FR-008) si `tipo` no está en el catálogo |
| `remediacion` | string | Sí | Copiado de `ALARM_TYPES[tipo].remediacion` (o la variante crítica, FR-007), o el aviso fijo de "sin remediación documentada todavía" (FR-008) |
| `antiguedad_s` | number \| `null` | No | Segundos desde que la condición está activa — `null` cuando el origen no lo calcula (discos; FR-014). En una entrada agrupada (`agrupada=true`), es el valor más alto entre las alarmas que agrupa (la más antigua del grupo) |
| `agrupada` | boolean | Sí | `true` si esta entrada resume ≥ `ALARM_GROUP_THRESHOLD` alarmas del mismo `(origen, tipo)` (FR-013) |
| `cantidad` | number | Sí | `1` si no está agrupada; el número real de alarmas que resume si lo está |

## Tipo de alarma — catálogo `ALARM_TYPES`

19 tipos iniciales, uno por cada condición de fallo distinta que los 10
orígenes ya distinguen hoy (`research.md` §2). `nivel` es la respuesta
completa a la Assumption de `spec.md` ("la asignación exacta... se
completa en el plan"). El texto de `explicacion`/`remediacion` es el
contenido real que se despliega — no un placeholder — y puede pulirse
en `/speckit-implement` sin que cambie ni el id ni el nivel.

| id | Origen | Nivel | Explicación | Remediación |
|---|---|---|---|---|
| `contenedor_caido` | contenedores | Aviso | Este contenedor no está corriendo y no es uno de los marcados para estar parado a propósito. | Revisar `docker logs --tail 50 <nombre>`. Si la causa es clara y no es un contenedor crítico, `docker restart <nombre>`. |
| `contenedor_caido_critico` | contenedores | Crítico | Este contenedor está en la lista de críticos (Home Assistant, Vaultwarden, Nextcloud, Immich, Pangolin, Gerbil, Traefik) y no está corriendo. | **No reiniciar ni modificar sin aprobación humana previa.** Revisar `docker logs --tail 50 <nombre>` para entender la causa antes de decidir nada. |
| `ha_api_caida` | ha | Crítico | La API de Home Assistant no responde — mientras dure, ningún otro check de HA es fiable (puede ser la causa de una cascada de alarmas HA). | Comprobar que el contenedor `homeassistant` está corriendo y que responde en su URL interna. |
| `ha_entidad_no_disponible` | ha | Aviso | Una entidad de Home Assistant está `unavailable` o `unknown` — el dispositivo o la integración detrás de ella no está reportando datos. | Comprobar el dispositivo físico y, si aplica, el relay `socat` correspondiente (ver pestaña Networking). |
| `ha_entidad_estado_inesperado` | ha | Aviso | Una entidad de Home Assistant está en un estado distinto del esperado (por ejemplo, un enchufe marcado como sobrecargado, o el modo de emparejamiento Zigbee dejado abierto). | Revisar el dispositivo en Home Assistant y devolverlo al estado esperado si procede. |
| `ha_valor_bajo_umbral` | ha | Aviso | Un valor numérico de Home Assistant (por ejemplo, el nivel de sal del descalcificador) ha cruzado el umbral configurado. | Revisar el valor real del sensor y reponer o actuar sobre el dispositivo correspondiente. |
| `ha_backup_atrasado` | ha | Aviso | El backup automático propio de Home Assistant no tiene una copia correcta reciente. | Abrir Home Assistant → Ajustes → Copias de seguridad y comprobar el error de la última ejecución. |
| `backup_diario_atrasado` | backup | Crítico | El backup diario del homelab (FastData → Storage) no se ha completado en el plazo esperado. | Revisar `~/Library/Logs/` del backup y lanzarlo a mano si hace falta — nunca con `sudo` (ver reglas del homelab). |
| `monitor_sin_latido` | monitores | Aviso | Un proceso de monitorización programado ha dejado de confirmar que sigue ejecutándose — puede seguir "cargado" en `launchctl` y aun así no estar haciendo su trabajo. | Comprobar el LaunchAgent correspondiente (`launchctl list`) y su log en `~/Library/Logs/`. |
| `relay_caido` | relays | Aviso | Un relay `socat` que conecta un contenedor con la LAN no está respondiendo. | Reiniciar el LaunchAgent del relay correspondiente. |
| `host_externo_caido` | hosts_externos | Aviso | Un host físico externo vigilado por Beszel (Uptime Kuma o AdGuard Home) está caído. | Comprobar el host directamente y su agente de Beszel. |
| `host_externo_sin_evidencia` | hosts_externos | Informativo | No hay dato reciente sobre este host — puede estar bien y solo faltar el sondeo, no necesariamente caído. | Comprobar que `beszel_hosts_monitor.py` y su LaunchAgent siguen corriendo. |
| `beszel_hub_sin_reportar` | beszel_hub | Crítico | El propio hub de Beszel ha dejado de reportar datos frescos sobre todos sus sistemas a la vez — se pierde visión de todo lo que vigila. | Revisar el contenedor `beszel` y los logs de `auxiliary.db` (tabla `_logs`) dentro de su volumen. |
| `agente_crasheado` | agentes | Aviso | Un LaunchAgent ha terminado con un código de salida distinto de cero y no está corriendo ahora mismo. | Revisar su log en `~/Library/Logs/` y relanzarlo con `launchctl kickstart` si la causa está clara. |
| `cron_con_error` | agentes | Aviso | Un cron de Bautista/Hermes ha terminado su última ejecución con un estado distinto de éxito. | Revisar la salida del cron en `~/.hermes/profiles/bautista/cron/output/`. |
| `disco_aviso` | discos | Aviso | Un disco ha superado el 75% de uso. | Revisar qué está creciendo (logs sin rotar, backups acumulados) antes de que llegue al 90%. |
| `disco_critico` | discos | Crítico | Un disco ha superado el 90% de uso. | Liberar espacio de inmediato — revisar logs, backups antiguos o duplicados. |
| `brecha_cobertura` | inventario | Informativo | El inventario de cobertura ha detectado un componente sin estado esperado declarado, sin vigilancia real, o que no llega al dashboard. | Revisar el detalle en la pestaña Inventario y decidir si declarar un estado esperado o marcarlo intencionado. |
| `origen_sin_datos` | cualquiera | Aviso | Uno de los 10 orígenes de esta pestaña no ha podido leer su fichero de datos (no existe, o no se pudo interpretar). | Comprobar que el proceso que genera ese fichero sigue corriendo y escribiendo. |

**Nota sobre `origen_sin_datos`**: es el único tipo que puede
originarse desde cualquiera de los 10 orígenes (Edge Cases, `spec.md`)
— `componente` identifica cuál cuando ocurre.
