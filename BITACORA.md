# Bitácora

> Una línea por sesión, con fecha — ver `METODO.md`. Qué medir: tiempo
> especificar vs implementar, ambigüedades que encontró `clarify`, tareas
> que salieron bien sin intervención, veces que se corrigió el spec en
> vez del código, veces que se reescribió el spec entero, si el spec
> sigue describiendo lo que hay al cerrar el hito.

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
