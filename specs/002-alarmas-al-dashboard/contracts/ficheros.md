# Contrato — Ficheros de entrega al dashboard

**Feature**: [../spec.md](../spec.md)

No hay CLI ni API HTTP nueva en este feature (`FR-005`): el contrato
externo son los ficheros que el mecanismo nuevo escribe y que
`docker/homelab-dashboard/scripts/app.py` lee — mismo patrón de contrato
que ya usan `socat_relays.json` y `docker_monitor_state.json` con el
dashboard.

## `docker_monitor_state.json` (ya existe — consumidor nuevo, no productor nuevo)

Este feature **lee** este fichero por primera vez desde el dashboard; no
cambia quién lo escribe ni su formato. Ver `data-model.md`.

**Garantía que asume `get_containers()`**: el fichero puede no existir
(primer arranque, `docker_monitor.py` nunca corrió) o estar temporalmente
bloqueado durante la escritura. En cualquiera de los dos casos,
`get_containers()` DEBE seguir devolviendo el estado en vivo de
`docker ps` sin `down_since` para ningún contenedor — un fallo al leer
este fichero no puede tumbar el panel de contenedores, que ya funcionaba
antes de este feature.

## `beszel_hosts.json` (nuevo)

**Productor**: el script nuevo de este feature, cada 5 minutos
(`research.md` §5).

**Consumidor**: una función nueva en `app.py` (`get_external_hosts()` o
equivalente), sumada a `collect()`.

**Esquema**: ver `data-model.md`, sección "Estado de host externo".

**Garantías**:

1. **Nunca modifica nada de Beszel ni de los hosts vigilados** — es una
   lectura de solo consulta contra el volumen de datos de Beszel
   (`research.md` §3); ninguna escritura, ningún reinicio.
2. **Un ciclo fallido no reescribe el fichero con datos falsos.** Si la
   lectura contra Beszel falla (hub caído, volumen no montado, consulta
   sin resultados), el script no toca `beszel_hosts.json` — lo deja
   envejecer. El dashboard decide "sin evidencia" por antigüedad
   (`FR-004`), nunca por un valor `"status": "desconocido"` escrito a
   propósito, que sería un segundo vocabulario para lo mismo.
3. **Los dos hosts en alcance siempre aparecen juntos.** El script no
   escribe un `beszel_hosts.json` parcial con un solo host — si no puede
   leer los dos, no escribe ninguno (mismo principio que la garantía 2:
   dato completo y fresco, o dato viejo y detectable, nunca dato a
   medias).

## Latido (`heartbeat.py`)

**Productor**: el mismo script nuevo, job `"beszel-hosts"`.

**Consumidor**: `get_monitor_heartbeats()` en `app.py`, vía la entrada
nueva en `MONITOR_JOBS` (`research.md` §4) — mismo contrato que ya usan
los otros 5 monitores, sin campo nuevo.

## Fuera de este contrato

- El esquema interno de la tabla `systems` de Beszel — es una dependencia
  de implementación del script nuevo (`research.md` §3), no algo que el
  dashboard consuma directamente ni que otro componente del homelab deba
  conocer.
- Cualquier cambio a `docker_monitor.py` o a su formato de salida — este
  feature es solo un consumidor nuevo de un contrato que ya existía.
