# Bitácora

> Una línea por sesión, con fecha — ver `METODO.md`. Qué medir: tiempo
> especificar vs implementar, ambigüedades que encontró `clarify`, tareas
> que salieron bien sin intervención, veces que se corrigió el spec en
> vez del código, veces que se reescribió el spec entero, si el spec
> sigue describiendo lo que hay al cerrar el hito.

## 2026-08-12 — Feature 010, ciclo completo (specify → implement), ruptura parcial de `METODO.md`

**Distinta de las rupturas de 008/009**: esta vez Miquel sí ejecutó él
mismo `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks` y
`/speckit-analyze` (los cuatro llegaron como comandos escritos por él,
no decididos por Claude). La ruptura fue más estrecha y explícita: al
llegar a `/speckit-implement`, Claude paró y preguntó antes de escribir
ningún código (`METODO.md` dice "todo el código" es de Miquel) — Miquel
respondió "Implementa tú esta vez", y más tarde pidió también el commit
y el push. Registrar esto con precisión importa para el propio
experimento: no es "Claude hizo todo el ciclo" como 008/009, es "Miquel
llevó el diseño, Claude llevó la implementación a petición explícita,
con una pausa de confirmación en el punto exacto donde cambiaba el
reparto".

- **Qué se pidió**: generalizar el motor de diagnóstico (007, ya
  generalizado a discos en 009) a un tercer origen: Home Assistant —
  checks de entidad, el recorder corrupto, y la disponibilidad de la
  API. Tercero de los 7 orígenes restantes de la Central de Alarmas;
  quedan 6.
- **Ambigüedades detectadas por `clarify`**: 1 — el check `ha_api`
  (tipo `api_ping`, sin entidad asociada) no encajaba en ninguna de las
  dos categorías de evidencia que el material de partida daba por
  buenas. Encontrado comparando el spec contra `ha_monitor.py` real, no
  por inspección del propio spec — el Principio XIII (Cobertura
  Sistemática) fue literalmente el motivo de la pregunta.
- **`/speckit-analyze` encontró 5 hallazgos, 0 críticos**: dos huecos de
  cobertura MEDIUM (SC-004 sin validación real del recorder *sano*,
  SC-002 sin selftest explícito de varias hipótesis para origen `ha`),
  una inconsistencia de dependencias MEDIUM (T024 no listaba T007 como
  prerrequisito pese a invocar el flag que T007 conecta), y dos LOW
  (una nota de verificación de research.md sin tarea asignada, un
  resumen incompleto en `plan.md`). Los tres MEDIUM se cerraron durante
  `implement`, no antes: los dos huecos de cobertura escribiendo los
  tests/validaciones correctamente desde el principio, y la
  inconsistencia de T024 corrigiendo la nota de dependencia al marcar
  la tarea.
- **Tareas implementadas sin intervención: 24 de 24** — ninguna falló.
  Pero la mayor parte del tiempo de la sesión no lo absorbió `tasks.md`,
  sino la validación en vivo: **4 problemas reales del motor**, ninguno
  anticipado por ninguna tarea, encontrados solo porque la validación
  usó DeepSeek/HA/Docker reales en vez de pararse en los selftests
  simulados (que ya tenían mocks "bien formados" por construcción, así
  que ninguno de los 4 podía aparecer ahí):
  1. `parsear_respuesta()` descartaba respuestas completas y válidas
     que el modelo de razonamiento escribía en `reasoning_content` en
     vez de `content` — afecta al motor compartido por 007/009 también,
     no solo a HA.
  2. Una entidad de alta frecuencia (`sal_nivel`, sensor de voltaje)
     reventó un prompt a 280.454 tokens sin producir ningún
     diagnóstico — la premisa de diseño ("las entidades de HA solo
     cambian de estado de vez en cuando") era cierta para baterías
     Zigbee y falsa para sensores de medición continua.
  3. `docker_logs_tail("homeassistant")` devolvía siempre `""` — ese
     contenedor escribe en `stderr`, no en `stdout`, y el `_run_ro()`
     heredado de 007 solo capturaba `stdout`.
  4. Un check `ha_api` sano se diagnosticaba como `causa_probable`
     citando un error real pero no relacionado de otra integración —
     el prompt no le decía al modelo si *ese check concreto* estaba
     fallando, así que rellenaba el hueco con el ruido más cercano.
  Cada uno se confirmó antes de tocar código (reproducido, no asumido),
  y los tres primeros se corrigieron sin pedir confirmación de nuevo
  (bugs claros, de bajo riesgo, dentro del alcance de lo que FR-003 ya
  exigía); el cuarto se paró a preguntar porque cambiaba la forma del
  snapshot (`data-model.md`) y el propio diseño de qué cuenta como
  evidencia, no solo corregía un error de ejecución.
- **Veces que se corrigió el spec en lugar del código**: 0. Al revés:
  se corrigió el código y **el spec se actualizó para seguir
  describiéndolo** — los 4 hallazgos quedaron escritos en
  `research.md` §10-§13 y `data-model.md`, con fecha, causa raíz y
  validación real, no como una discrepancia silenciosa entre lo que
  dice el documento y lo que hace el código.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  después de las 4 actualizaciones post-hoc de arriba — sin ellas,
  `research.md` habría quedado desfasado del código real en el mismo
  commit que lo cerraba.
- **Validación real, con coste real**: API de HA real, contenedor
  `homeassistant` real (corrupción de recorder simulada con
  `docker exec ... touch`/`rm`, limpiada de inmediato), DeepSeek real.
  Los 7 escenarios de `quickstart.md` validados con datos reales, no
  solo simulados. Coste real acumulado: 0,236 € — muy por debajo del
  límite compartido de 5 €/día, confirmado por consulta directa a
  `gasto_diario` (FR-007/SC-003).
- **Dato para el método**: cuarta sesión seguida (tras 007, 008, 009)
  donde la validación contra infraestructura real encuentra algo que
  ningún selftest simulado podía encontrar — esta vez el número más
  alto hasta ahora (4 hallazgos reales en una sola sesión de
  `implement`). Refuerza el mismo argumento que ya dejaron 007/008/009:
  "selftest en verde" y "feature funciona contra el sistema real" son
  preguntas distintas, y la brecha entre ambas parece crecer, no
  reducirse, a medida que el motor se generaliza a orígenes con formas
  de evidencia más variadas (HA es el primero sin una tabla SQL propia
  de la que leer).

## 2026-08-11 — Feature 009, ciclo completo (specify → implement), tercera vez fuera de proceso

**Ruptura deliberada de `METODO.md`, tercera vez en la misma sesión
larga.** Mismo patrón que 008: Miquel decidió el qué ("Pues hagamos
1" — generalizar el diagnóstico a un segundo origen), Claude ejecutó
todo el ciclo. Mismo aviso de siempre: estos números miden qué
encuentra el método sin Miquel al mando, no el método en sí.

- **Qué se pidió**: generalizar el motor de diagnóstico (007) más allá
  de contenedores. Antes de escribir nada, investigación real: de los 9
  orígenes restantes de la Central de Alarmas, solo discos tiene datos
  históricos de verdad en `homelab.db` (`disk_metrics`, 13.992 filas) —
  los otros 7 no tienen ninguna tabla propia. Decidido con Miquel:
  empezar por discos, uno a la vez, no los 9 de golpe (mismo criterio
  que ya usaron los features 004/005 para no tratar entidades distintas
  como un bloque).
- **Segundo hallazgo de la investigación previa**: a diferencia de
  `beszel` (49 reinicios reales para 007), no existe ningún incidente
  real de disco que usar como línea base — los tres discos del homelab
  llevan tiempo sanos. Aceptado como limitación conocida en el propio
  `plan.md` (Principio IX), no ocultada.
- **Ambigüedades detectadas por `clarify`**: 1 — qué pasa si el disco
  diagnosticado es el mismo donde vive `diagnostico.db` y no queda
  espacio para escribir el resultado (un riesgo que no existía para
  contenedores, cuya evidencia y registro viven en sitios
  independientes). Miquel aceptó el riesgo tal cual, sin mecanismo de
  respaldo nuevo.
- **`/speckit-analyze` encontró 3 hallazgos reales**: una inconsistencia
  de formato (`T002` marcada `[P]` pese a depender de `T001`), un hueco
  de cobertura (SC-002 — varias hipótesis para un episodio de disco —
  sin ninguna tarea que lo comprobara), y una infraespecificación real
  (la convención horaria de `MOMENTO_ISO` en `--disco-historico` no
  estaba escrita en ningún sitio — exactamente la categoría de fallo
  que ya costó una sesión de depuración entera en 008 sobre este mismo
  paquete). Los tres se corrigieron antes de implementar.
- **Tareas implementadas sin intervención real: 19 de 19** — ninguna
  falló, pero la implementación sí encontró trabajo no anticipado en
  ningún artefacto: renombrar `episodios.contenedor` a `componente`
  exigió tocar 5 sitios de `tests/selftest/*.py` que construían
  `Episodio(contenedor=...)` con el nombre antiguo — no estaban en
  `tasks.md` porque son consecuencia mecánica de T001/T002, no trabajo
  nuevo de diseño.
- **Migración de esquema sobre datos de producción, con cautela
  explícita**: `episodios.contenedor` → `componente` + `origen` nuevo,
  aplicada primero contra una **copia** de `diagnostico.db` real (9
  episodios, 17 diagnósticos, 26 hipótesis — verificados intactos byte
  a byte en los campos que no debían cambiar) antes de tocar el
  fichero de producción. Tareas T014/T015 separadas a propósito por
  esto mismo.
- **Validación real con DeepSeek, no solo selftest simulado**: los tres
  discos reales del homelab (FastData, Storage, Sistema), sanos,
  diagnosticados de verdad — los tres concluyeron `no_diagnosticable`
  con 3-4 hipótesis contrastadas cada uno (el modelo razonó sobre
  tendencia de crecimiento del uso, backups sin rotar, fallo de
  hardware — sin inventar ninguna causa). Reproducibilidad (SC-001)
  confirmada con dos diagnósticos reales del mismo episodio histórico.
  Gasto compartido (FR-007) confirmado por aritmética exacta contra
  `gasto_diario` real: coste de contenedor + coste de disco = acumulado
  del día, sin discrepancia.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí —
  ninguna decisión de `research.md` tuvo que revisarse tras la
  validación real, a diferencia de 008 (que sí encontró un bug de
  diseño real en implementación). La investigación previa a especificar
  (qué orígenes tienen datos reales, qué convención horaria usar) pagó
  aquí: menos sorpresas en `implement` que en las dos sesiones
  anteriores.
- **Dato para el método**: tercera sesión seguida donde `/speckit-analyze`
  encuentra algo real (008: 1 hallazgo sobre 007 + 1 sobre 008 propio;
  009: 3 hallazgos). La categoría que más se repite — convención
  horaria sin documentar — ya apareció en 008 como bug de
  implementación y en 009 como hallazgo de análisis antes de llegar a
  implementar; la disciplina de escribirlo explícitamente en
  `research.md`/`contracts/` esta vez evitó repetir el mismo bug.

## 2026-08-11 — Feature 008, ciclo completo (specify → implement), otra vez fuera de proceso

**Ruptura deliberada de `METODO.md`, segunda vez en la misma sesión
larga.** A petición explícita de Miquel ("Sigo tú", "Ejecuta tú el
specify", "Implement ya"), Claude ejecutó el ciclo completo —
`specify` → `clarify` → `plan` → `tasks` → `analyze` → `implement` —
de principio a fin. Mismo aviso que la sesión anterior: los números de
abajo no miden el método con Miquel al mando, miden qué encuentra el
método cuando se sigue igual de disciplinado sin él.

- **Qué se pidió**: exponer en el dashboard los diagnósticos que ya
  produce el motor de 007, solo lectura, colgado de una pestaña ya
  existente — visto en la sesión anterior como feature 008 (el hueco
  que dejó cerrarse la deuda técnica sin necesitar spec).
- **El spec cambió de sitio dos veces antes de llegar a `/speckit-plan`
  y otra vez durante `/speckit-plan`**. Primera: el material de partida
  decía "pestaña Correcciones"; al escribirlo, Miquel decidió que fuera
  solo visor y colgado de Correcciones. Segunda (real, encontrada al
  preparar `/speckit-plan`, no al escribir el spec): "Correcciones" no
  es la lista de alarmas activas — es el historial de alarmas ya
  **resueltas**; la lista activa es la pestaña "Alarmas", separada.
  Tercera: puesto a elegir entre las dos con la distinción ya clara,
  Miquel cambió el destino a "Alarmas" — más accionable, coincide con
  el caso de uso que 007 ya había validado de verdad (diagnóstico en
  vivo de un contenedor crítico). El spec, `research.md`, `data-model.md`,
  `contracts/` y `quickstart.md` se reescribieron enteros la segunda
  vez — la única reescritura completa de un artefacto en todo el
  proyecto hasta ahora.
- **Ambigüedades detectadas por `clarify`**: 1 — cuándo un diagnóstico
  de una caída anterior no debe mostrarse como si fuera de la actual.
  Miquel confirmó el valor por defecto y añadió un requisito no
  anticipado: las fechas del episodio y del diagnóstico deben estar
  siempre visibles, nunca solo la conclusión sola.
- **`/speckit-analyze` encontró 1 hallazgo real** (I1, HIGH): el
  contrato decía que la clave `diagnostico` no aparecía en absoluto
  para alarmas ajenas/agrupadas; `data-model.md` y `tasks.md` ya
  asumían que sí aparecía, como `null`. Resuelto unificando en la
  segunda convención (más simple de implementar).
- **Tareas implementadas sin intervención real: 13 de 16.** Las otras
  3 no fallaron por error de tarea — revelaron problemas de diseño que
  ninguna revisión de código podía encontrar:
  1. El desempate entre dos episodios a la misma distancia no seguía
     "el más reciente" que el propio `research.md` había decidido —
     encontrado releyendo el código ya escrito, antes de desplegar.
  2. Un `SyntaxWarning` real por un escape sin duplicar en el JS
     embebido, más una lógica de formateo de euros confusa —
     encontrado en los logs del contenedor al reconstruirlo.
  3. **El más importante**: el algoritmo de emparejamiento comparaba
     `down_since` contra un único punto (`ventana_inicio`). Probado
     contra un episodio real (`congelar --vivo` de un contenedor
     parado a propósito para la prueba), falló exactamente el caso de
     uso central del feature — diagnosticar en vivo poco después de la
     caída — porque `ventana_inicio` de un episodio `--vivo` es el
     principio de toda una hora de contexto de métricas, no el inicio
     real de la caída. Ninguna de las 16 tareas de `tasks.md`, ni la
     revisión de `/speckit-analyze`, podía haber encontrado esto sin
     ejecutar el código contra un caso real — se corrigió comparando
     contra el **rango** `[ventana_inicio, ventana_fin]` en vez de un
     punto.
- **Validación real, no solo selftest simulado**: contenedor
  reconstruido y desplegado en producción; funciones probadas dentro
  del contenedor real contra `diagnostico.db` real; **captura de
  pantalla con un navegador real** (Playwright/Chromium, instalado
  para la ocasión) confirmando visualmente el bloque de diagnóstico,
  las dos fechas y el gasto diario. El entorno de pruebas (un
  contenedor parado a propósito, `docker_monitor_state.json` alterado
  temporalmente para simular una alarma) se restauró exactamente al
  estado previo — diff vacío confirmado contra la copia de seguridad.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  incluida la corrección del algoritmo de emparejamiento, documentada
  en `research.md` §3 con la fecha y el caso real que la motivó, no
  como una discrepancia silenciosa entre el spec y el código.
- **Dato para el método**: de los tres problemas reales encontrados en
  esta sesión (el pivote Correcciones→Alarmas, el hallazgo I1, y el
  bug del rango de fechas), **ninguno lo encontró la revisión de
  código ni `/speckit-analyze` — los tres aparecieron al ejecutar
  contra datos y contenedores reales**. Coincide con lo que ya apuntó
  la sesión de 007 (T030): en este proyecto, la validación real sigue
  encontrando categorías de fallo que ninguna revisión estática cubre.

## 2026-08-07/08 — Feature 001, ciclo completo (specify → implement)

Primer feature del proyecto. Una sola sesión cubrió el ciclo entero:
`constitution` (ya existía) → `specify` → `clarify` → `plan` → `tasks` →
`analyze` → `implement`.

- **Especificar vs implementar**: la mayor parte del tiempo se fue en
  `specify` — varias rondas de revisión con Miquel ampliando alcance
  (granularidad de entidad en HA, hosts externos, Hermes/Telegram como
  riesgo concentrado, disparo a demanda) antes de cerrar el spec.
  `implement` fue más rápido de lo esperado porque el propio `plan.md`
  ya había investigado contra el código real del homelab (convenciones,
  rutas, estructura de datos), así que hubo poco que decidir sobre la
  marcha.
- **Ambigüedades detectadas por `clarify`**: 3, ninguna descartada por
  cupo — identidad de un componente entre ejecuciones, retención del
  histórico, umbral de caducidad de una declaración (90 días).
- **Tareas implementadas sin intervención**: 39 de 40. La única que se
  paró a propósito fue T036 (parche del dashboard en producción, fuera
  del repo) — parada explícita para pedir confirmación antes de tocar un
  fichero en producción, no un fallo de implementación.
- **Veces que se corrigió el spec en lugar del código**: 2.
  1. Durante `/speckit-plan`: el ejemplo "container ID de Docker" en la
     Clarification 1 era técnicamente impreciso (el ID interno cambia en
     cada recreación; lo estable es el nombre) — corregido en `spec.md`
     antes de que hubiera código apoyado en el dato erróneo.
  2. Durante `/speckit-implement`: el paso 6 de `quickstart.md` probaba
     el mecanismo de respaldo del riesgo de Telegram con `--no-telegram`,
     que es un *skip* deliberado, no un fallo — se corrigió para forzar
     credenciales vacías de verdad, y se verificó contra el código real
     que el latido sale `fail` en ese caso.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay?**: sí, con una salvedad
  anotada aparte — Beszel/hosts externos/Recordatorios de Nextcloud
  quedaron marcados en `spec.md` (Assumptions) como candidatos a
  **feature 002** (mostrar en el dashboard las alarmas que ya calculan
  `docker_monitor.py`/`ha_monitor.py`, hoy invisibles) en vez de meterlos
  en este feature — decisión explícita con Miquel, no un hueco sin
  documentar.
- **Dato no previsto en ningún artefacto**: la primera ejecución real
  encontró 830 componentes y 385 brechas (línea base del Principio IX
  exigía ≥11). El propio volumen reveló un límite no cubierto por
  ninguna tarea: un mensaje de Telegram con 385 líneas probablemente
  supera el límite de 4096 caracteres de la API — anotado como pendiente,
  no arreglado en esta sesión.

## 2026-08-09 — Features 002-005, sin bitácora propia (hueco de proceso)

Entre el feature 001 y el 006 se cerraron cuatro features más
(`002-alarmas-al-dashboard`, `003-latidos-beszel-calendario`,
`004-triage-entidad-ha`, `005-movil-y-backup-ha`) sin anotar una línea
aquí en su momento — se hizo el ciclo completo de Spec Kit en cada uno
(hay `spec.md`/`plan.md`/`tasks.md` reales para los cuatro) pero las
métricas de proceso (ambigüedades, tareas sin intervención, spec vs
código) no se registraron. Se deja constancia del hueco en vez de
reconstruir con memoria las cifras de sesiones ya cerradas — inventar
un número aproximado sería peor que admitir que no se midió.

## 2026-08-09 — Feature 006, ciclo completo (specify → implement) + resolución de hallazgos post-implement

Central de Alarmas: pestaña nueva que unifica 10 orígenes ya
vigilados en una sola lista con explicación y remediación fijas por
tipo, sin IA. Ciclo completo en una sesión:
`specify` → `clarify` → `plan` → `tasks` → `analyze` → `implement` →
una segunda vuelta de `analyze` resuelta explícitamente a petición de
Miquel.

- **Especificar vs implementar**: al revés que el feature 001 — aquí
  `implement` llevó más rondas que `specify`. El propio `plan.md`
  investigó bien contra el código real (`app.py`), pero la superficie
  de T002 (10 orígenes con formas de datos todas distintas) hizo que
  apareciera un problema real de diseño ya en la fase de implementación:
  el catálogo de tipos de HA asumía que `app.py` podía leer el campo
  `type` de cada check (`api_ping`/`entity_available`/...), y ese campo
  nunca se serializa a `ha_monitor_state.json` — solo vive en el
  `ha_monitor.py` privado. Se resolvió con una heurística sobre
  `motivo`+`label`+id del check, sin volver a `/speckit-plan`: una
  decisión de implementación legítima, no un cambio de alcance.
- **Ambigüedades detectadas**: 5 en total — 2 durante `/speckit-specify`
  (granularidad de la remediación por submotivo; aviso especial para
  contenedores críticos) + 3 durante `/speckit-clarify`, ninguna de
  estas últimas marcada como `[NEEDS CLARIFICATION]` en el spec
  original pese a ser reales (agrupación de alarmas en cascada,
  criterio de orden por gravedad, antigüedad opcional cuando el origen
  no la calcula). Los 5 se resolvieron con la opción recomendada.
- **Tareas implementadas sin intervención**: 18 de 18 en la primera
  pasada de `/speckit-implement`, más 3 tareas nuevas (T019-T021)
  añadidas y completadas en una segunda pasada al resolver los
  hallazgos de `/speckit-analyze` — 21 de 21 en total, cero fallos.
  Sí hubo una corrección propia durante la validación (no un fallo de
  tarea): un `SyntaxWarning` en el escape de una regex JS dentro del
  string Python de la plantilla, detectado al ejecutar la
  autocomprobación de T012, corregido antes de continuar.
- **Veces que se corrigió el spec en lugar del código**: al menos 11,
  todas en `/speckit-analyze` — 3 de severidad HIGH que Miquel pidió
  arreglar de inmediato (conteo "9 orígenes" cuando el propio
  `data-model.md` ya enumeraba 10; conteo "17 tipos" con una tabla de
  19 filas; `host_externo_sin_evidencia` clasificado de forma
  contradictoria en `spec.md` frente a `data-model.md`) y 8 más de
  severidad MEDIUM/LOW que Miquel pidió arreglar después, ya con el
  feature implementado y funcionando (terminología "motivo raíz" sin
  equiparar a `tipo`; regla de antigüedad de un grupo sin documentar;
  criterio de `cron_con_error` sin anclar a ningún enumerado; un
  ejemplo técnicamente inexacto repetido 4 veces; y 3 huecos de
  cobertura entre requisito e implementación sin tarea de verificación
  — ver más abajo). Dato interesante para el método: los 8 MEDIUM/LOW
  se resolvieron **sin tocar una sola línea de código de `app.py`** —
  solo documentación más 3 tareas nuevas de verificación manual — lo
  que sugiere que esa categoría de hallazgo es barata de posponer más
  allá de `/speckit-implement` sin acumular deuda real.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  y verificado contra el dashboard real en cada paso (no solo por
  inspección de código) — 5 de las correcciones de `/speckit-analyze`
  se re-comprobaron en vivo (provocando alarmas reales o simuladas)
  después de corregir la documentación, no solo se dieron por buenas.
- **Hallazgo fuera de todo artefacto de Spec Kit**: antes de comitear,
  una revisión manual encontró que 6 referencias a la IP LAN real
  (`192.168.4.87`) se habían colado en `quickstart.md`/`tasks.md`/
  `data-model.md` — exactamente lo que la regla "Repositorio público"
  de `BRIEFING.md` prohíbe, y que el propio `spec.md` de este feature
  ya citaba como restricción (Assumptions). Ninguna skill de Spec Kit
  tiene un paso que compruebe esto — quedó a criterio de la revisión
  antes de `git push`. Se corrigieron las 6 (sustituidas por
  `homelab.amsterdam9.home`, ya usado así en specs 001/002) antes del
  commit. Nota aparte: `specs/005-movil-y-backup-ha/quickstart.md` ya
  tenía esta misma fuga desde antes, sin corregir — deuda preexistente,
  no de esta sesión, anotada aquí para no perderla de vista.

## 2026-08-11 — Sesión fuera de proceso: Claude ejecuta, no solo revisa; feature 008 se cierra antes de nacer

**Ruptura deliberada de `METODO.md`.** A petición explícita de Miquel
("lo ejecutas tú esta vez", luego "hazlo tú mismo"), esta sesión la
ejecutó Claude de principio a fin — algo que `METODO.md` reserva a
Miquel precisamente para que aprenda el método y para que las métricas
de proceso sean reales. Se anota aquí en vez de en silencio: los
números de esta sesión (abajo) no son comparables a los de una sesión
normal del proyecto, y no deberían usarse para medir el método en sí.

- **Qué se pidió**: preparar el feature 008 (deuda técnica pendiente:
  4 piezas ya detectadas — ver la sesión de feature 006/007 más abajo y
  `BRIEFING.md`). Antes de escribir `/speckit-specify`, Miquel decidió
  recuperar la cuarta pieza (5 hallazgos de `/speckit-analyze` de 007
  cuyo contenido nunca se guardó) volviendo a correr `/speckit-analyze`
  sobre `007-diagnostico-episodios`, en vez de reconstruirlos de
  memoria.
- **Lo que pasó en vez de un ciclo de Spec Kit para 008**: la segunda
  pasada de `/speckit-analyze` sobre 007 encontró 6 hallazgos nuevos
  (U1-U3, I1-I2, C1 — distintos en número y contenido de los 5
  originales, dados por irrecuperables). Al pedir Miquel "prepáralos
  tú", se resolvieron los 6 directamente: un fix de código real
  (`deepseek.py` — el parser aceptaba en silencio más de una hipótesis
  `confirmada` a la vez, pese a que el propio prompt exige exactamente
  una), un test nuevo, y reescritura de `spec.md`/`research.md`/
  `data-model.md`/`quickstart.md` de 007 para que el criterio de
  reproducibilidad (SC-001/FR-002) documentado coincida con lo que de
  verdad se puede sostener contra un LLM en la nube, y para fijar por
  fin los `restart_history_id` concretos de la línea base de `beszel`
  (nunca se habían registrado en ningún artefacto). Esas correcciones
  cerraron, de paso, las otras tres piezas de deuda que iban a formar
  el alcance de 008. Al llegar al punto de escribir la descripción de
  partida para `/speckit-specify`, no quedaba nada que especificar.
- **Hallazgo fuera de todo artefacto de Spec Kit**: al sanear la fuga
  de IP conocida (`specs/005-movil-y-backup-ha/quickstart.md`), un
  barrido del mismo patrón por todo el repo encontró una segunda fuga
  no catalogada — los relays de Frigate en la sección "Feature 004" de
  `BRIEFING.md` citaban la IP real en vez de `homelab.amsterdam9.home`.
  Mismo patrón que el hallazgo de la sesión de feature 006
  (2026-08-09): ninguna skill de Spec Kit comprueba esto, sigue a
  criterio de la revisión manual.
- **¿El spec de 007 sigue describiendo lo que hay al cerrar esta
  sesión?**: sí — es precisamente lo que esta sesión restauró. Antes de
  ella, `spec.md`/`research.md` de 007 describían un criterio de
  reproducibilidad más estricto del que el código y la validación real
  (T030) podían sostener; ahora coinciden.
- **Dato para el método, no para el proyecto**: esta sesión demuestra
  que "recuperar hallazgos perdidos re-ejecutando `/speckit-analyze`"
  funciona — no reprodujo los mismos 5 hallazgos literales (imposible,
  nunca se guardaron), pero encontró una cobertura equivalente o mejor
  del mismo terreno real. Vale como precedente para la próxima vez que
  se encuentre un hueco de proceso similar.

## 2026-08-10 — Feature 007, ciclo completo (specify → implement) + validación real con DeepSeek

Primer feature de Frente 2: diagnóstico de episodios de contenedor con
DeepSeek, sin ninguna acción correctiva. Ciclo completo en una sesión:
`specify` (una repetición por un error de herramienta) → `clarify` (3
preguntas) → `plan` → `tasks` (33 tareas) → `analyze` → resolución de 3
hallazgos a petición explícita de Miquel → `implement` → validación real
contra la API de DeepSeek (no solo selftests simulados) una vez Miquel
creó la credencial.

- **Especificar vs implementar**: al contrario que el feature 001 y en
  la línea del 006 — `implement` encontró dos problemas de diseño reales
  que ni `plan.md` ni `data-model.md` habían anticipado, y que
  `/speckit-analyze` tampoco pudo detectar porque no ejecuta código
  contra datos reales. (1) `container_metrics`/`disk_metrics` tienen 30
  días de retención (documentado en el `CLAUDE.md` general del homelab,
  pero no traído al diseño de este feature); los 49 reinicios de
  `beszel` (marzo-mayo 2026) ya no tenían ningún dato de detalle al
  llegar a `implement` — se corrigió con un respaldo a
  `container_metrics_hourly` (agregado permanente). (2)
  `disk_metrics_near` devolvía "las 3 muestras más próximas" sin límite
  de distancia — para un episodio de abril, eso eran datos de disco de
  agosto, que el LLM podría haber leído como evidencia real del momento
  del episodio; se corrigió con un filtro de tolerancia. Los dos se
  encontraron al ejecutar T030 (validación contra la línea base de
  `beszel`) contra `homelab.db` real, no por inspección de código.
- **Ambigüedades detectadas por `clarify`**: 3 (alcance solo
  contenedores; disparo bajo demanda; identidad del episodio = snapshot
  congelado al elegir diagnosticar). Una cuarta clarificación se añadió
  a mano, fuera del propio comando `/speckit-clarify`: Miquel pidió
  inicialmente remediación automática al 100% sin distinguir críticos,
  se le explicó el conflicto con el Principio V (NO NEGOCIABLE) y con
  `docker_monitor.py`/`SOUL.md` ya vigentes, y se acordó en su lugar
  reforzar FR-013/FR-013a (diagnóstico obligatorio de críticos, cero
  acción sobre ellos) — el momento de mayor riesgo de la sesión, resuelto
  parando a pedir confirmación en vez de implementar la petición inicial.
- **Tareas implementadas sin intervención**: 31 de 33 en la primera
  pasada de `/speckit-implement` — T030 y T032 quedaron bloqueadas
  porque `.secrets/deepseek.env` no existía todavía (verificado, no
  asumido). Miquel creó la credencial en la misma sesión y las 2
  restantes se completaron después → 33 de 33 al cierre. Ninguna tarea
  falló de verdad; sí hubo una corrección de prompt en `deepseek.py`
  durante la validación real (ver hallazgo más abajo), fuera de lo que
  ninguna tarea de `tasks.md` pedía.
- **Veces que se corrigió el spec/plan en lugar del código**: 3, todas
  en `/speckit-analyze`, a petición explícita de Miquel ("resolver B1 E1
  E2"): un margen de gasto "prudente" sin cifra concreta en `research.md`
  (sustituido por la constante `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`, que
  además pasó a ser el `max_tokens` real de la petición); SC-001
  (reproducibilidad) y SC-002/FR-011 (línea base de `beszel`) solo tenían
  verificación manual — se añadieron 2 tareas nuevas (T023, T031) con
  selftests automatizados antes de implementar nada. Quedaron sin tocar,
  por decisión explícita de Miquel, 5 hallazgos más de severidad
  MEDIUM/LOW (C1-C3, F1).
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí, con
  un cambio hecho en caliente tras la validación real: el modelo por
  defecto pasó de `deepseek-chat` (el asumido al escribir `research.md`)
  a `deepseek-v4-flash`, a petición de Miquel una vez confirmado que el
  feature funcionaba — documentado con fecha en `research.md` y
  `contracts/cli.md`, no dejado como una discrepancia silenciosa.
- **Hallazgo fuera de todo artefacto de Spec Kit**: la validación real
  contra DeepSeek (imposible de reproducir con los selftests, que usan
  respuestas ya bien formadas) encontró que el modelo, específicamente
  al diagnosticar un contenedor crítico sano sin ningún episodio real
  que explicar, marcaba una hipótesis `"confirmada"` en la misma
  respuesta que concluía `no_diagnosticable` — viola el invariante
  FR-007 tal como el propio prompt lo pedía. El parser lo rechazó
  correctamente 3 veces seguidas (ninguna causa falsa se persistió), a
  costa de 3 llamadas reales desperdiciadas (~0,0015 € en total). Causa
  raíz: el prompt no distinguía "esta comprobación se completó" de "esta
  hipótesis ES la causa" para la palabra "confirmada" — corregido con una
  aclaración explícita; la siguiente llamada fue consistente. No se ha
  vuelto a probar en volumen si la ambigüedad reaparece en otros
  contenedores — queda anotado en `tasks.md` (T030) como algo a vigilar
  en uso real, no como cerrado del todo. Aparte, también en la
  validación real (no en ningún selftest): el mismo episodio
  diagnosticado dos veces dio la misma conclusión pero un número
  distinto de hipótesis (0 y 3) — exactamente el Edge Case de varianza
  entre llamadas que el spec ya preveía como posible; queda como hallazgo
  registrado, no resuelto en esta sesión.
