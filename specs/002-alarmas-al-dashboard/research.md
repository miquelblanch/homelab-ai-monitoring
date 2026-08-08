# Research — Alarmas Ya Calculadas al Panel del Dashboard

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-08-08

Cada decisión se contrastó contra el código real del homelab —
`docker_monitor.py`, `dump_socat_status.py`, `heartbeat.py` y
`docker/homelab-dashboard/scripts/app.py` — y, para el punto 3, contra el
propio hub de Beszel en marcha, no contra lo que ya decía la documentación.

## 1. Fundir la alarma de contenedor en la fila que ya existe (Clarification 1, FR-001/FR-003)

**Decision**: `get_containers()` en `app.py` lee además
`docker_monitor_state.json` (mismo directorio `/data` que ya monta el
contenedor del dashboard) y añade `down_since` a cada contenedor por
nombre. En el frontend, la tarjeta de cada contenedor pasa a mostrar
"Caído desde `<fecha>`" cuando ese campo no es nulo, sin crear ninguna
fila ni sección nueva.

**Rationale**: es la traducción directa de la Clarification 1. El propio
formato del fichero ya usa la clave `container:<nombre>` — el mismo nombre
que expone `docker ps`, así que el cruce es una búsqueda por clave, sin
lógica de emparejamiento adicional.

**Hallazgo que simplifica un edge case del spec**: `docker_monitor.py`
hace `continue` inmediato para cualquier contenedor en `NEVER_RESTART`
(`frigate`) — nunca escribe ni actualiza su entrada en el estado. La
tarjeta de `frigate` simplemente no encuentra ninguna clave que fusionar,
así que nunca muestra alarma sin necesidad de una excepción explícita en
el código nuevo.

**Alternatives considered**: una fila/sección aparte solo para episodios
recuperados (Opción B/C de la Clarification) — descartada por decisión
explícita de Miquel: menos superficie nueva en el dashboard, cumple el
Principio XII de forma más directa.

## 2. Umbral de frescura para "sin evidencia" (Clarification 2, FR-004)

**Decision**: 15 minutos, pero solo para el latido nuevo de este feature
(`beszel-hosts`, ver punto 4) — no como un segundo mecanismo de frescura
para los datos de `docker_monitor.py`.

**Rationale**: al implementar la Clarification 2 se encontró que
`docker_monitor.py` **ya tiene** su propio latido vigilado en el panel
"Estado de los monitores" (`MONITOR_JOBS` en `app.py`, entrada
`docker-monitor`, `max_age_s=1800` — 30 min, no 15). Aplicarle también 15
min a la lectura de `docker_monitor_state.json` habría creado dos
respuestas distintas a la misma pregunta ("¿sigue vivo `docker_monitor.py`?")
con umbrales distintos. Se corrige `FR-004` del spec para que el umbral de
15 min se aplique únicamente al latido nuevo que este feature introduce, y
los contenedores seguán apoyándose en el latido de `docker-monitor` que ya
existía. El propio umbral de 15 min sí tiene precedente exacto en el
código: `MONITOR_JOBS` ya usa `900` s (15 min) para `telegram-monitor`, que
también corre cada 5 minutos — mismo ritmo, mismo margen de 3×.

**Alternatives considered**: umbral único de 15 min para ambos orígenes,
tal como se planteó en `/speckit-clarify` — descartado tras leer
`MONITOR_JOBS` en `app.py` (ver arriba).

## 3. Cómo leer el estado que Beszel calcula sobre Kuma y AdGuard (FR-002, FR-007)

Investigado contra el hub de Beszel real, no contra documentación:

- El volumen `beszel_hub_data` (SQLite, PocketBase) **no es accesible como
  ruta de fichero desde macOS** — OrbStack lo monta dentro de su propia VM
  Linux (`docker volume inspect` da `/var/lib/docker/volumes/.../_data`,
  que no existe en el host). Cualquier lectura tiene que pasar por Docker,
  no por un `open()` directo.
- El hub expone una API HTTP (PocketBase, puerto ya documentado en
  `CLAUDE.md` del homelab general) — probada en vivo:
  `GET /api/collections/systems/records` responde `200` pero con
  `totalItems: 0` sin autenticación; la colección `systems` está protegida.
  Usarla exige crear un usuario/token nuevo en Beszel y guardar una
  credencial nueva en `.secrets/` — viable, pero es alcance adicional no
  trivial (flujo de auth de PocketBase sin verificar todavía) para un
  feature que la propia `spec.md` (Assumptions) ya acota como "mecanismo
  intermedio a decidir en el plan", no como oportunidad para ampliar
  alcance.
- La vía por volumen montado **ya está probada y funciona**: `docker run
  --rm -v beszel_hub_data:/data <imagen-con-sqlite3> sqlite3 /data/data.db
  "select name, status from systems;"` devolvió en vivo `AdGuardHome|up` y
  `UptimeKuma|up` durante la investigación de este mismo proyecto (ver
  conversación previa, y la nota ya existente en el `CLAUDE.md` del
  homelab general sobre leer `data.db` de Beszel montando el volumen, no
  con `docker cp`). Montar el volumen completo (no copiar un fichero
  suelto) es exactamente lo que evita el problema de WAL ya documentado
  ahí — el propio `sqlite3` sabe leer `data.db`+`-wal`+`-shm` juntos si los
  tres están presentes, que es el caso al montar el volumen entero.

**Decision**: la vía del volumen montado, no la API HTTP, para v1.
Concretamente: `docker run --rm -v beszel_hub_data:/data python:3.11-alpine
python3 -c "<script corto con el módulo `sqlite3` de la stdlib>"` en vez de
una imagen `alpine` + `apk add sqlite` en cada ciclo — `python:3.11-alpine`
ya trae `sqlite3` en su librería estándar, así que no depende de red en
cada ejecución (solo la primera vez que Docker descarga la imagen), y
mantiene el mismo runtime (Python 3.11) que el resto del homelab.

**Rationale**: cero credenciales nuevas, cero superficie de autenticación
nueva que mantener, reutiliza un método ya verificado en producción sobre
este mismo volumen. El coste es acoplarse al esquema interno de la tabla
`systems` de Beszel (podría cambiar en una actualización futura del
software) — riesgo aceptado explícitamente, documentado aquí para que sea
visible si algún día se rompe.

**Alternatives considered**: API HTTP de Beszel (PocketBase) con
credencial propia — más robusta a un cambio de esquema interno, pero
queda aparcada para una iteración futura si el acceso por volumen resulta
frágil en la práctica (mismo criterio que feature 001 aplicó a la API
WebSocket de Home Assistant en su `research.md` §3).

## 4. Vigilancia del propio mecanismo nuevo (Clarification 2ª, FR-008)

**Decision**: el script nuevo (ver `data-model.md` y "Project Structure")
escribe su latido con `heartbeat.write("beszel-hosts", ...)` al final de
cada ciclo, igual que `docker_monitor.py`. Se añade una entrada a
`MONITOR_JOBS` en `app.py` (`("beszel-hosts", "Estado de hosts externos
(Beszel)", 900)`) y su descripción correspondiente en `MONITOR_INFO` —
aparece en el panel "Estado de los monitores" que ya existe, sin tabla ni
sección nueva.

**Rationale**: traducción directa de la respuesta A a la Clarification de
`/speckit-clarify`. `900` s coincide con el patrón ya usado por
`telegram-monitor` (mismo ritmo de 5 min, mismo margen ×3).

## 5. Cadencia y disparo del script nuevo

**Decision**: LaunchAgent nuevo, `amsterdam9.beszel.hosts-reader`,
`StartInterval` de 300 s (5 min) — mismo patrón que
`amsterdam9.dashboard.socat` (`dump_socat_status.py`), que también escribe
un JSON de estado al mismo directorio cada 5 minutos para que el
dashboard lo lea sin tocar Docker en cada carga de página.

**Rationale**: coherente con la cadencia de `docker_monitor.py` (5 min) y
con el patrón ya existente de "un LaunchAgent nativo escribe un JSON
pequeño; el dashboard solo lo lee" — evita que cargar la página dispare un
`docker run` nuevo cada vez (más lento, y acopla el tiempo de carga del
dashboard a la latencia de Docker).

**Alternatives considered**: ejecutar la consulta a Beszel directamente
dentro de `get_external_hosts()` en cada carga del dashboard — descartado:
`app.py` corre dentro de un contenedor Docker sin acceso a `docker run`
(sería Docker-in-Docker), y además introduciría latencia variable en cada
carga de página por algo que solo cambia cada 5 minutos como mucho.

## 6. Fichero de salida del script nuevo

**Decision**: `docker/homelab-orchestrator/data/beszel_hosts.json` — mismo
directorio que `socat_relays.json`, `docker_monitor_state.json` e
`inventario.json`, ya montado en `/data` dentro del contenedor del
dashboard. Esquema en `data-model.md`.

**Rationale**: mismo patrón ya usado tres veces en ese directorio; cero
infraestructura nueva de almacenamiento.
