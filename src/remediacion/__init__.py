"""remediacion — Frente 2: ejecuta acciones reales sobre el homelab
(Principios IV-VIII, Modelo Operacional B). Ya NO es independiente de
`diagnostico` (lo era hasta 019) — desde 021 importa tres cosas
concretas y acotadas: `diagnostico.evidencia.congelar_vivo` (recogida
de evidencia), `diagnostico.deepseek.llamar_deepseek` (llamada HTTP
pura, sin lógica de negocio), y `diagnostico.gasto` (presupuesto
diario compartido) — nunca `diagnostico.store`/`model` ni la vía de
`causa_probable` (research.md §2 de specs/021-remediacion-contenedores/).

Tres tipos de acción:

- `rotar_log` (019): condición determinista, sin DeepSeek — rota
  (nunca borra) un log de una lista cerrada de 17 logs reales del
  homelab cuando supera un umbral de tamaño.
- `reiniciar_contenedor` (021): la decisión NO es una condición fija —
  para cada contenedor no crítico que no está `running and healthy`,
  se reúne su evidencia real y se le pregunta a DeepSeek si reiniciar
  resuelve el caso, o si ninguna acción de la lista cerrada aplica.
- `reiniciar_agente` (026): mismo patrón que `reiniciar_contenedor`,
  para LaunchAgents de usuario (`amsterdam9.*`) y LaunchDaemons root de
  relays de Home Assistant (`com.homeassistant.*`, con permiso `sudo`
  acotado al comando exacto vía `sudoers` — nunca genérico). Primera
  vez que este paquete ejecuta un comando de sistema (`launchctl`)
  directamente en vez de bridgear a un script privado — no existe
  ningún equivalente a `docker_monitor.py` para agentes
  (specs/026-reiniciar-agentes-relays/research.md §2). La verificación
  de que un reinicio funcionó de verdad es siempre en vivo
  (`launchctl list <label>`), nunca contra el volcado periódico que
  usa el motor de diagnóstico (research.md §2b).

Cada tipo de acción (`rotar_log`, `reiniciar_agente`) o cada
contenedor individual (`reiniciar_contenedor`) tiene un modo, `manual`
(por defecto) o `automatico`, que Miquel controla siempre él mismo
desde `remediacion.cli` — estar en la lista cerrada de acciones
reversibles es condición necesaria para poder actuar, nunca suficiente
por sí sola para hacerlo sin permiso. `reiniciar_agente` es por tipo
de acción, no por agente individual (a diferencia de
`reiniciar_contenedor`) — un agente no tiene eje crítico/no-crítico.

En modo manual, una condición detectada (o una recomendación de
DeepSeek) se registra como propuesta pendiente de aprobación. En modo
automático, se ejecuta directamente y se registra igual. `rotar_log`
es además reversible con un procedimiento de rollback escrito
(Principio VI): rotar renombra, nunca trunca ni borra, y deshacer
nunca sobreescribe lo que se haya escrito después de la rotación.
`reiniciar_contenedor` y `reiniciar_agente` no tienen esa vía de
deshacer (FR-016 de 021, FR-007 de 026) — excepción documentada
explícitamente, no incumplimiento silencioso.

No ejecuta nunca ninguna acción sobre un componente crítico ni sobre
`frigate` — ni siquiera les pregunta a DeepSeek (FR-006 de 021). No
expone ningún estado accionable en el dashboard — el CLI sigue siendo
la única superficie de control. Avisa por Telegram cuando: una
rotación automática falla (019), ninguna acción de DeepSeek aplica
(021/026, FR-009 de 021 / FR-002 de 026), el cortacircuito de
reinicios se abre (021/026, FR-011 de 021 / FR-009 de 026), o una
incapacidad de evaluar persiste varios ciclos seguidos (021/026,
FR-019 de 021 / FR-014 de 026 — contrapartida del Principio VII
enmendado en constitution.md v2.0.0: `docker_monitor.py` cede la
decisión de reinicio de los no críticos a este paquete, pero esa
cesión exige que un fallo persistente para decidir nunca quede en
silencio). Un éxito, o un fallo en modo manual, nunca notifican.

Ver `specs/019-remediacion-automatica/`,
`specs/021-remediacion-contenedores/` y
`specs/026-reiniciar-agentes-relays/` para spec, plan y contratos.
"""
