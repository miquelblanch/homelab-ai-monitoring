# Research — Remediación Asistida por DeepSeek: Contenedores

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## §1 — Reutilizar `diagnostico.evidencia.congelar_vivo()`, no una copia nueva

**Decisión**: la evidencia de un contenedor (métricas recientes,
`docker inspect`, `docker logs` tail) se reúne llamando directamente a
`diagnostico.evidencia.congelar_vivo(conn_diagnostico, contenedor)` —
la misma función que ya usa el motor de diagnóstico (007) para el
origen `contenedor` en vivo.

**Rationale**: esa función ya existe, ya está probada, y ya resuelve
exactamente el mismo problema (qué evidencia reunir de un contenedor
en el momento). Escribir una segunda versión en `remediacion`
duplicaría ~30 líneas que divergirían con el tiempo — por ejemplo, si
se amplía qué se considera evidencia relevante de un contenedor
(017/018 ya ampliaron qué orígenes tienen evidencia propia), una copia
en `remediacion` se quedaría desactualizada sin que nadie lo notara,
el mismo patrón de bug silencioso que este proyecto existe para
evitar.

**Efecto secundario aceptado**: cada evaluación de un contenedor caído
crea un `Episodio` nuevo en `diagnostico.db` (vía `congelar_vivo`),
aunque `remediacion` nunca lo use para generar una hipótesis de causa.
Es coherente, no un efecto colateral raro — un episodio real ocurrió,
y queda registrado donde ya se registran todos los episodios de este
origen, consultable con las mismas herramientas.

**Alternativas consideradas**:
- Duplicar la función en `remediacion` — rechazado por riesgo de
  divergencia (arriba).
- Extraer `congelar_vivo` a un módulo compartido fuera de ambos
  paquetes — más "correcto" en abstracto, pero cambia la estructura de
  `diagnostico` (007-017, ya cerrado y estable) para un beneficio
  marginal frente a simplemente importar. Rechazado por alcance:
  tocar código ya cerrado de otra feature sin necesidad real.

## §2 — `remediacion` deja de ser independiente de `diagnostico`, con límites explícitos

**Decisión**: `remediacion` importa tres cosas concretas de
`diagnostico`, y nada más:

1. `diagnostico.evidencia.congelar_vivo` — recogida de evidencia (§1).
2. `diagnostico.deepseek.llamar_deepseek` — la llamada HTTP pura
   (`prompt`, `modelo` → respuesta cruda de la API), sin ninguna
   lógica de negocio de hipótesis.
3. `diagnostico.gasto` — `hay_presupuesto`, `registrar_coste`,
   `gasto_hoy` — el presupuesto diario compartido (§8).

**Lo que NO importa, explícitamente**: `diagnostico.store`,
`diagnostico.model` (`Diagnostico`, `Hipotesis`), ni la lógica de
`diagnosticar_episodio()` — la vía de `causa_probable` sigue sin
usarse, tal y como confirmó Miquel (spec.md Clarifications, tercera
pregunta). `remediacion` nunca lee ni escribe una `Hipotesis`.

**Rationale**: desde 019, el docstring de `remediacion` decía
"paquete independiente de diagnostico — no importa nada de ese
módulo". Esa frase describía correctamente v1 (`rotar_log`, sin
DeepSeek). Ya no describe v2: esta feature necesita evidencia real y
una llamada a DeepSeek, y ambas ya existen, probadas, en `diagnostico`.
Mantener la independencia total obligaría a duplicar código de
producción ya probado — el mismo tipo de decisión que 019 (research.md
§11) ya resolvió reutilizar en vez de duplicar, para el caso análogo
del bridge hacia `homelab_secrets.py`.

**Lo que se actualiza para reflejarlo**: el docstring de
`src/remediacion/__init__.py` (que decía "no importa nada de ese
módulo") y cualquier mención equivalente en `README.md`/
`constitution.md` — parte de las tareas de esta feature (`tasks.md`),
no un efecto colateral silencioso.

## §3 — Pregunta nueva a DeepSeek, no reutiliza `construir_prompt`

**Decisión**: `remediacion` tiene su propia función de construcción
de prompt (`deepseek_contenedores.construir_prompt_remediacion`), no
reutiliza `diagnostico.deepseek.construir_prompt` — sí reutiliza
`llamar_deepseek` (la llamada HTTP en sí, §2).

**Rationale**: `construir_prompt` de `diagnostico` pregunta "¿cuál es
la causa probable de este episodio?" — una pregunta abierta, de
diagnóstico de causa raíz, que en 36/36 casos reales termina en
`no_diagnosticable`. La pregunta de `remediacion` es distinta y más
concreta: "dada esta evidencia, ¿aplica `reiniciar_contenedor`, o
ninguna acción de esta lista cerrada resuelve el caso?" — una decisión
binaria sobre una acción conocida, no una hipótesis abierta sobre una
causa desconocida. Son preguntas de naturaleza distinta y merecen
prompts distintos; forzar la misma pregunta a servir para las dos
cosas repetiría el motivo por el que 019 evitó depender de
`causa_probable` desde el principio.

**Forma de la respuesta esperada** (mismo patrón `response_format:
json_object` que ya usa `llamar_deepseek`):

```json
{
  "accion_aplica": "reiniciar_contenedor",
  "razonamiento": "..."
}
```

o, cuando ninguna acción resuelve el caso:

```json
{
  "accion_aplica": null,
  "razonamiento": "..."
}
```

`parsear_respuesta_remediacion()` (nueva, en `deepseek_contenedores.py`)
valida que `accion_aplica` sea `null` o uno de los valores de
`acciones.TIPOS_ACCION` conocidos — **nunca** confía en un valor libre
devuelto por el modelo como si fuera una acción válida (FR-003, la
lista cerrada la impone el código, no la respuesta de DeepSeek).

## §4 — `docker_monitor.py`: de actor a biblioteca

**Decisión**: `docker_monitor.py` (privado) pierde, dentro de su
`main()`, el bloque que decide reiniciar un contenedor no crítico
caído (líneas ~405-430 de la versión actual) — ese bloque pasa a vivir
en `remediacion.acciones`, que llama a las funciones puras de
`docker_monitor.py` en vez de reimplementarlas:

- `docker_monitor.restart_container(name, reason)` — reinicio +
  verificación real de `running` tras `VERIFY_DELAY_S`.
- `docker_monitor.breaker_decision(attempts, max_attempts)` — función
  pura, decide si el cortacircuito permite un nuevo intento.
- `docker_monitor.CRITICAL`, `docker_monitor.NEVER_RESTART` — mismos
  conjuntos, reutilizados como límite no negociable (FR-006), no
  redefinidos (mismo patrón que `inventory._homelab_bridge.
  docker_critical()`/`docker_never_restart()` ya establecido en el
  feature 001).

`docker_monitor.py` conserva, sin cambios: recogida de métricas cada 5
min, comprobación de discos, el bloque de alerta+skip para contenedores
críticos caídos (FR-012b se solapa con esto — decisión: **se conserva
en `docker_monitor.py`**, no se duplica en `remediacion`, porque ya
existe y ya funciona — ver nota abajo).

**Nota sobre el aviso de "crítico caído"**: el spec (FR-012b) exige
que el sistema avise cuando un crítico está caído. `docker_monitor.py`
ya lo hace hoy, sin cambios necesarios — no hace falta que
`remediacion` lo repita. `remediacion` se limita a **no evaluar nunca**
un contenedor crítico (FR-006), dejando ese aviso donde ya existe.
Evita un aviso duplicado (uno de `docker_monitor.py`, otro de
`remediacion`) por el mismo evento.

**Rationale de reutilizar en vez de reimplementar**: `restart_container()`
se corrigió una vez, el 2026-07-26, tras un bug real (marcaba
`success` basado en el código de salida de `docker restart`, no en si
el contenedor había quedado corriendo de verdad). Reimplementar esa
lógica en `remediacion` arriesga repetir el mismo bug ya corregido —
coste innecesario para un beneficio (aislamiento total público/privado)
que este proyecto ya no persigue de forma absoluta (ver los bridges ya
existentes en `inventory`/`remediacion`).

## §5 — `restart_history` queda congelada, no se migra

**Decisión**: `restart_history` (tabla de `metrics_db.py`, en
`homelab.db`) deja de recibir filas nuevas a partir del corte — los
intentos de `remediacion` se registran en `intentos_reinicio`
(`remediacion.db`), una tabla nueva, no en `restart_history`.

**Rationale**: son bases de datos y paquetes distintos
(`metrics_db.py` es privado, parte del stack de monitorización general
del homelab; `remediacion.db` es del proyecto público). Escribir en
las dos duplicaría el evento y arriesgaría que diverjan (un intento
marcado `ejecutado` en una y `fallido` en otra por un fallo parcial de
escritura). El histórico de `restart_history` sigue siendo válido y
consultable para todo lo ocurrido **antes** del corte (incluido el
caso 1 de `BRIEFING.md`, los 49 reinicios de `beszel`) — simplemente
deja de crecer.

**Alternativa considerada y rechazada**: escribir en ambas tablas para
no "perder" continuidad histórica en un único sitio. Rechazado: el
criterio de muerte y otras herramientas que leen `restart_history` ya
saben tratar huecos temporales (lo hacen con el propio hueco de
mayo-julio de `container_metrics_hourly`, documentado en
`CLAUDE.md`) — es preferible una fuente de verdad clara por período a
dos fuentes sincronizadas a mano.

## §6 — Granularidad por contenedor: tabla nueva, no reutiliza `configuracion_accion`

**Decisión**: `configuracion_contenedor` es una tabla nueva
(`remediacion.db`), con `contenedor` como clave primaria (no
`tipo_accion`) — no se reutiliza `configuracion_accion` de 019.

**Rationale**: `configuracion_accion` (`tipo_accion TEXT PRIMARY KEY`)
modela exactamente un interruptor por tipo de acción entero — es
correcto para `rotar_log` (17 logs, un interruptor) y sería incorrecto
forzarlo a modelar 26 interruptores independientes. Añadir una columna
`componente` opcional a la tabla existente complicaría su significado
para `rotar_log` sin necesidad; una tabla nueva y explícita es más
clara que una columna que solo se usa a veces.

## §7 — Modo inicial: automático para los 26, sin excepción

Ya confirmado en `spec.md` (Clarifications) — documentado aquí solo
para que el plan lo declare explícitamente como decisión de diseño:
la migración inserta las 26 filas de `configuracion_contenedor` en
modo `automatico` como parte del despliegue (tarea explícita en
`tasks.md`), no como comportamiento por defecto del código al
encontrar un contenedor sin fila — a diferencia de `get_modo()` de
019, que sí trata "sin fila" como manual. Aquí, "sin fila" para un
contenedor de los 26 originales no debería ocurrir tras el despliegue;
si ocurre (contenedor nuevo, no crítico, añadido después), sí se trata
como manual — ese caso concreto está cubierto por FR-002 del spec.

## §8 — Presupuesto diario: mismo mecanismo, sin contabilidad separada

**Decisión**: antes de cada llamada a DeepSeek, `remediacion` llama a
`diagnostico.gasto.hay_presupuesto(conn_diagnostico, tokens_entrada_estimados)`
— la misma comprobación que ya hace `diagnostico.cli` antes de
diagnosticar un episodio. Tras la llamada, `registrar_coste()` en la
misma tabla `gasto_diario` de `diagnostico.db`.

**Rationale**: son llamadas al mismo proveedor (DeepSeek), con el
mismo límite económico real — llevar dos contadores separados
permitiría gastar el doble del límite pensado, exactamente lo que
FR-013/FR-014 prohíben. Reutilizar la tabla ya existente es más simple
que replicarla con otro nombre.

## §9 — Fallo de la llamada ≠ "ninguna acción aplica"

**Decisión**: `llamar_deepseek()` devuelve `None` en cualquier fallo
(sin credencial, timeout, error HTTP — ya es su contrato actual,
`diagnostico/deepseek.py`). `deepseek_contenedores.evaluar()` propaga
esa distinción con un tercer estado explícito, `sin_evaluar` — nunca
lo colapsa a "ninguna acción aplica" (`accion_aplica: null` con
respuesta real) ni a "reiniciar" por defecto.

**Rationale**: son señales completamente distintas. "Ninguna acción
aplica" es una conclusión real de DeepSeek, con razonamiento, sobre
evidencia real — vale la pena el aviso de US4. "No se pudo evaluar"
es un fallo de infraestructura (sin presupuesto, sin red, respuesta
inválida) que no dice nada sobre el contenedor — tratarlo como
cualquiera de los otros dos casos sería inventar una conclusión que
DeepSeek nunca llegó a producir, justo lo que el Principio IV prohíbe.
