# Research: Reinicio de Agentes y Relays

## §1. Espacio de `id` compartido — de dos tablas a tres

`store._siguiente_id_compartido()` calcula el próximo `id` como
`max(MAX(intentos_remediacion.id), MAX(intentos_reinicio.id)) + 1`, en
vez de fiarse del `AUTOINCREMENT` propio de cada tabla — corregido en
021 tras un hallazgo real contra producción (dos secuencias
independientes, ambas empezando en 1, colisionaban en cuanto las dos
tablas tenían filas). `localizar_intento()` prueba primero
`intentos_remediacion`, luego `intentos_reinicio`, para que
`aprobar`/`rechazar`/`deshacer`/`historial` resuelvan sobre la tabla
correcta sin que el llamador tenga que saber de antemano qué tipo de
intento es.

**Decisión**: `intentos_agente` entra en el mismo espacio compartido.
`_siguiente_id_compartido()` pasa a `max(a, b, c) + 1` con las tres
tablas. `localizar_intento()` prueba `intentos_remediacion` →
`intentos_reinicio` → `intentos_agente`, en ese orden (el orden ya
existente se conserva, el caso nuevo se añade al final — ningún
llamador existente cambia de comportamiento).

**Por qué no una secuencia independiente para `intentos_agente`**: es
exactamente el bug que 021 ya encontró y corrigió — un tercer
`AUTOINCREMENT` propio volvería a colisionar con los otros dos en
cuanto las tres tablas tuvieran filas. El coste de mantener el patrón
ya establecido (tres `MAX()` en vez de dos) es marginal frente al
riesgo de reintroducir el mismo bug.

**Riesgo real a vigilar en tasks.md**: cualquier código que asuma "solo
dos tablas" (comentarios, tests con nombres como
`test_ids_compartidos_2021`) debe actualizarse a la vez, no después —
si `_siguiente_id_compartido()` cambia pero `localizar_intento()` no
(o al revés), un intento de agente podría crearse con un `id` que ya
existe en otra tabla sin que nada lo detecte hasta un `aprobar`
resolviendo sobre el intento equivocado.

## §2. Ejecución real del reinicio — sin bridge, nueva en este paquete

`restart_container()` (021) bridgea a `docker_monitor.restart_container()`
—un script privado ya existente y ya corregido tras un bug real
(2026-07-26)—. Para agentes **no existe ningún script privado
equivalente**: `CASUISTICA-026-acciones-reversibles.md` confirmó que
hoy nada en `/Volumes/FastData/homelab/scripts/` ejecuta
`launchctl kickstart` de forma automática — los únicos usos existentes
solo lo imprimen como sugerencia para que Miquel lo teje a mano.

**Decisión**: `ejecutar_reiniciar_agente(label, requiere_sudo)` vive
directamente en `acciones.py`, mismo criterio que `ejecutar_rotar_log()`
(que tampoco bridgea nada — usa `Path.rename` directamente porque no
había ningún mecanismo previo que reutilizar). Comando:

- `amsterdam9.*`: `launchctl kickstart -k gui/$(id -u)/<label>`
- `com.homeassistant.*`: `sudo -n launchctl kickstart -k system/<label>`
  — `-n` (non-interactive): si el `sudoers` no está instalado o no
  cubre exactamente ese comando, falla inmediatamente en vez de
  colgarse esperando una contraseña que nunca va a llegar.

`subprocess.run([...], timeout=15, capture_output=True)`. El código de
salida de `kickstart` **nunca decide el resultado por sí solo** — solo
se usa para el `detalle` del intento si falla. El resultado real lo da
la verificación en vivo de §2b.

## §2b. Verificación en vivo tras el reinicio — nunca `LAUNCHAGENTS_RAW`

**Hallazgo de `/speckit-analyze` (D1, 2026-08-16):** el borrador
original de esta sección decía "se verifica el estado real después,
no el código de salida" sin especificar cómo — con el riesgo real de
que se releyera `LAUNCHAGENTS_RAW` para esa verificación.
`LAUNCHAGENTS_RAW` es un volcado que **se sobreescribe cada 5
minutos** (docstring de `diagnostico.evidencia.agente`) — inútil para
confirmar algo que acaba de pasar hace segundos. El precedente real
(`docker_monitor.restart_container()`, `CLAUDE.md` general: "success
significa verificado corriendo tras 10 s") hace una comprobación **en
vivo**, no relee un snapshot periódico.

**Decisión**: `ejecutar_reiniciar_agente()` hace la comprobación ella
misma, en la misma llamada — mismo patrón que `restart_container()`
(ejecutar + verificar es una sola responsabilidad, no dos funciones
separadas):

1. Lanza `kickstart` (arriba).
2. Espera un margen corto para que `launchd` reaccione — 3 segundos
   por defecto (`REMEDIACION_AGENTE_ESPERA_VERIFICACION_SEGUNDOS`,
   configurable; más corto que los ~10s de contenedores porque no hay
   arranque de imagen de por medio, solo relanzar un proceso nativo ya
   presente en disco — a ajustar con datos reales tras el primer
   despliegue si resulta insuficiente).
3. Consulta el estado **en vivo**, nunca `LAUNCHAGENTS_RAW`:
   `launchctl list <label>` (forma de un solo argumento — imprime el
   estado detallado de ese label concreto, distinto de `launchctl
   list` sin argumentos que imprime la tabla completa que ya vuelca
   `LAUNCHAGENTS_RAW`). Se considera `running` si el label aparece con
   un PID asignado.
4. `True` solo si el paso 3 confirma `running` — un `kickstart` con
   código de salida 0 pero el proceso caído otra vez en 3s (crash-loop)
   es `False`, no `True` (Principio II: el resultado es el estado real,
   nunca lo que devolvió el comando).

**Confirmado contra la máquina real (2026-08-16, tras instalar el
`sudoers` de T032):** en macOS, las acciones que **cambian** estado
del dominio `system` (`kickstart`, `bootstrap`, `bootout`) requieren
root — las que solo **leen** (`list`, `print`) no, ni siquiera sobre un
LaunchDaemon root. Comprobado en producción: `launchctl list
com.homeassistant.esphome-sal-relay` sin ningún `sudo` devuelve el
estado completo (PID, programa, argumentos) con código de salida 0. El
diseño de `_agente_activo_ahora()` (sin `sudo`, para las dos ramas) era
correcto tal cual — no hizo falta ampliar el `sudoers` para cubrir
`list`.

`REMEDIACION_TEST_FORZAR_FALLO_AGENTE` (variable de entorno, mismo
patrón que `REMEDIACION_TEST_FORZAR_FALLO` de 021) fuerza `False` sin
tocar `launchctl` — hook de pruebas para el cortacircuito.

**Hallazgo real de T031 (2026-08-16): `launchctl kickstart` tarda ~18s
en devolver el control en esta máquina.** No es un cuelgue — es una
latencia real y consistente (medida dos veces, exactamente 18.0s en
ambas), probablemente por la cantidad de jobs registrados en `launchd`
en este homelab concreto. Descartado que fuera cosa de la sesión de
Claude Code: Miquel lo reprodujo igual en una Terminal normal.
Aislado con pruebas controladas (`start_new_session=True`, `stdin`/
`stdout`/`stderr` con `DEVNULL` real, `os.system`) — el resultado fue
el mismo en todas: la operación tarda, no se cuelga. El timeout
original de `ejecutar_reiniciar_agente()` (15s) cortaba en seco una
operación que sí iba a terminar bien 3s más tarde — un `fallido` falso
por mal calibrado, no un fallo de diseño ni del entorno. Corregido a
`REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS = 30` (nueva constante,
configurable, con margen real sobre el dato medido). Confirmado de
extremo a extremo tras la corrección: `aprobar` sobre un LaunchAgent
desechable real → `ejecutado — reiniciado y verificado`, ~21s totales,
PID nuevo confirmado en vivo.

## §3. Comprobación de `sudoers` — de solo lectura, nunca ejecuta

FR-023 exige saber si el permiso está instalado sin arriesgarse a
ejecutar el reinicio solo para comprobarlo. `sudo -n -l <comando>`
(con `-l` y un comando literal a continuación) le pregunta a `sudo`
si ese comando exacto está permitido para el usuario actual **sin
ejecutarlo** — código de salida 0 si está permitido, distinto de 0 si
no (falta la regla, o pediría contraseña).

**Decisión**: `_homelab_bridge.sudoers_permitido(label: str) -> bool`
ejecuta `sudo -n -l launchctl kickstart -k system/<label>` y devuelve
`código_salida == 0`. Nunca lanza (mismo principio "a prueba de
fallos" del resto del bridge) — cualquier excepción o timeout se trata
como `False` (permiso no confirmado, no "sin dato" — más seguro tratar
un fallo de comprobación como bloqueado que como permitido).

Se llama una vez por `com.homeassistant.*` candidato al escribir el
snapshot (`_snapshot_agentes()`), no en cada evaluación de DeepSeek —
comprobar el permiso no depende de si hay un episodio activo, así que
separar ambas cosas evita una llamada a `sudo` de más por cada ciclo
de 5 minutos por agente cuando lo que cambia con más frecuencia es si
el agente está caído, no si el permiso está instalado.

## §4. Fuente de la lista de 43 candidatos — reutilizada, no copiada

`inventory.sources.launchagent_components()` (fuente ya existente,
usada por Inventario) lee `launchctl list` en vivo y filtra por
prefijo (`amsterdam9.*`, `com.homeassistant.*`) — la misma fuente que
ya cuenta los 32+11 en `CASUISTICA-026-acciones-reversibles.md`.
`remediacion` no debe copiar esa lógica de filtrado por segunda vez.

**Decisión**: `comprobar_reiniciar_agente()` no mantiene su propia
lista de labels — recorre `LAUNCHAGENTS_RAW` (la misma fuente cruda
que ya usa `diagnostico.evidencia.agente`, vía una función nueva y
pequeña en `_homelab_bridge.py`, `listar_agentes_conocidos()`, que
filtra por los dos prefijos) y evalúa los que no tienen proceso activo
— nunca `inventory.sources` directamente (`remediacion` no importa de
`inventory`, research.md de 019 §2, sin cambios). Un label nuevo que
aparezca en `LAUNCHAGENTS_RAW` con uno de los dos prefijos entra
automáticamente en el próximo ciclo, sin tocar código — cumple
spec.md User Story 4, Acceptance Scenario 2.

## §5. Prompt y parseo — módulo nuevo, mismo patrón que contenedores

`deepseek_agentes.py` mirroring `deepseek_contenedores.py`:
`construir_prompt_agente(episodio, acciones_candidatas)` con
instrucciones adaptadas a "un LaunchAgent/LaunchDaemon que no tiene un
proceso activo" en vez de "un contenedor Docker no está running and
healthy" — mismo formato de respuesta JSON
(`{"accion_aplica": "reiniciar_agente" | null, "razonamiento": "..."}`),
mismo uso de `diagnostico.deepseek._extraer_contenido_y_tokens` (025)
para el parseo, misma validación contra `acciones.TIPOS_ACCION`
completo (no solo `reiniciar_agente` — mismo criterio ya aceptado en
`deepseek_contenedores._accion_valida`, no se endurece aquí).

## §6. Cortacircuito y aviso — constantes reutilizadas, sin nuevas

Clarifications (sesión 2026-08-16): mismo umbral que contenedores.
`REMEDIACION_CB_MAX_INTENTOS`/`REMEDIACION_CB_VENTANA_HORAS` (ya
definidas en `acciones.py`) se reutilizan tal cual —
`bridge.recent_restart_attempts()` necesita una versión que cuente
sobre `intentos_agente` en vez de `intentos_reinicio`
(`recent_agent_restart_attempts()`, misma consulta, tabla distinta) —
`breaker_decision()` (pura, ya bridgeada) no cambia. Igual para
`REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` (FR-014).

## §7. "Beszel (hub)" — confirmado sin cambio de backend

`_snapshot_contenedores()` (022) ya recorre `bridge.listar_contenedores()`
completo (39, sin excluir ninguno) y calcula su clasificación —
`beszel` ya está en ese array hoy, con su intento vigente si lo hay.
FR-015 se satisface por completo con el `join` del lado del dashboard
(por nombre: fila de Inventario `"Beszel (hub)"` ↔ entrada `"beszel"`
del bloque `contenedores[]`) — no hace falta ningún cambio en
`_snapshot_contenedores()` ni en ningún otro sitio de este repo.

## §8. Snapshot ampliado — bloque `agentes[]`

`escribir_snapshot()` gana un tercer bloque, mismo nivel que `logs[]`
y `contenedores[]`:

```json
{
  "agentes": [
    {
      "label": "amsterdam9.health.docker",
      "tipo": "amsterdam9",
      "running": true,
      "clasificacion": "ia",
      "sudoers_instalado": null,
      "intento_vigente": null
    },
    {
      "label": "com.homeassistant.esphome-sal-relay",
      "tipo": "com.homeassistant",
      "running": false,
      "clasificacion": "ia",
      "sudoers_instalado": false,
      "intento_vigente": {"estado": "sin_evaluar", "detalle": "...", "creado_en": "..."}
    }
  ]
}
```

`sudoers_instalado` es `null` para `amsterdam9.*` (la pregunta no
aplica — nunca necesita `sudo`), `true`/`false` para
`com.homeassistant.*`. `clasificacion` reutiliza `clasificacion.py`
— requiere una función nueva y pequeña,
`clasificar_agente(label, modo)`, mismo criterio que
`clasificar_log()` (no hay eje crítico/no-crítico para agentes: `"ia"`
si `modo` viene de una configuración real, sin la distinción manual/
automática que sí tiene sentido para logs). Detalle completo en
`contracts/snapshot-json.md`.

## §9. Ampliación de "Correcciones" — qué necesita el dashboard, no cómo lo pinta

FR-020/FR-021 son responsabilidad del dashboard privado, pero este
plan documenta qué dato le falta hoy: `ALARM_HISTORY_FILE` solo
registra una entrada cuando una alarma activa deja de estarlo
(`reconcile_alarm_history`, comparación entre sondeos) — nunca ve un
intento `pendiente`/`rechazado`/`fallido`/`cortacircuito` mientras la
alarma sigue activa, porque esos estados viven en
`remediacion_estado.json` (bloques `logs[]`/`contenedores[]`/
`agentes[]`), no en `ALARM_HISTORY_FILE`.

**Corrección (verificando T028, 2026-08-16): `logs[]` NO tenía
`intento_vigente` "desde 020"** — esa afirmación, en la primera
versión de esta sección, no se comprobó contra el código real. Solo
`contenedores[]` (022) y `agentes[]` (T024 de esta misma feature) lo
tenían. Añadido ahora (`store.intento_vigente()`, mismo criterio
exacto que `intento_reinicio_vigente()`/`intento_agente_vigente()`,
cableado en `escribir_snapshot()`) para que los tres bloques sean
simétricos — sin este arreglo, FR-020 quedaba sin cumplir para
`rotar_log` pese a que el requisito lo nombra explícitamente ("logs,
contenedores, y agentes").

La ampliación de Correcciones en sí consiste en que el dashboard, al
pintarla, además de su fuente actual, cruce cada alarma activa con el
`intento_vigente` del componente correspondiente (si lo hay) — mismos
tres bloques del snapshot que ya usa Alarmas (022) para la misma
finalidad, ninguna fuente nueva.
