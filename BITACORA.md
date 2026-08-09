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
