# Contrato — Entrega del resultado (Telegram y dashboard)

**Feature**: [../spec.md](../spec.md) · Ver también `research.md` §6 y §7.

`FR-018` exige entregar por canales que ya existen. Este contrato fija qué
recibe cada canal, para que el resto del homelab (y el propio dashboard)
sepan qué esperar sin tener que leer el código.

## Telegram

- Un mensaje por ejecución (no uno por brecha) usando
  `homelab_secrets.telegram()`, mismo mecanismo que `docker_monitor.py` y
  `ha_monitor.py`.
- Contenido: recuento total (`X/Y componentes sin brecha`), listado
  filtrado de brechas (`FR-011`) con componente + qué pregunta falla, y si
  aplica, la alerta de riesgo concentrado de Telegram (Edge Case, `FR-006`)
  **destacada aparte al principio del mensaje**, no mezclada en la lista.
- Si el propio envío falla, el fallo se registra localmente (log +
  latido, ver `cli.md`); no hay reintento automático dentro de la misma
  ejecución — el disparo a demanda (`FR-014`) ya permite a Miquel repetir
  la ejecución cuando quiera.

## Dashboard

El dashboard (`docker/homelab-dashboard/scripts/app.py`) **no lee
genéricamente** lo que se deje en `docker/homelab-orchestrator/data/` —
tiene una lista fija de lectores (`get_system`, `get_disks`,
`get_containers`, `get_crons`, `get_launchagents`, `get_socat_relays`,
combinados en `collect()`) y un frontend embebido en el mismo fichero.
Verificado leyendo el código real — no es una suposición (ver
`research.md` §6).

Este feature entrega al dashboard con **dos piezas**, no una:

1. Un fichero `inventario.json` en `docker/homelab-orchestrator/data/`
   (mismo patrón de fichero que `socat_relays.json`), con: fecha de la
   ejecución, `total_componentes`, `total_brechas`, y el listado filtrado
   de brechas con su `tipo` (mismo vocabulario que `brechas.tipo` en
   `data-model.md`).
2. Un cambio pequeño y localizado en `app.py`: una función
   `get_inventory()` que lea ese fichero (mismo estilo que
   `get_socat_relays()`, con el mismo manejo de "fichero no encontrado"),
   sumada a `collect()`, y una sección nueva en el HTML/JS embebido para
   mostrarla — una sección más entre las seis que ya existen, no una
   página ni un servicio nuevo.

**No es una alarma nueva del dashboard** en el sentido del Principio XII:
es un panel informativo de cobertura, no sustituye ni duplica las alarmas
que ya generan `docker_monitor.py`/`ha_monitor.py`/`verify_backups.py` —
de hecho, ninguna de ellas llega hoy al dashboard (`docker_monitor_state.json`
y `ha_monitor_state.json` existen en `/data` pero `app.py` no los lee).
Corregir una brecha y convertirla en una alarma de verdad es trabajo de un
feature posterior (ver Assumptions del spec).
