"""remediacion — Frente 2: ejecuta acciones reales sobre el homelab
(Principios IV-VIII, Modelo Operacional B). Ya NO es independiente de
`diagnostico` (lo era hasta 019) — desde 021 importa tres cosas
concretas y acotadas: `diagnostico.evidencia.congelar_vivo` (recogida
de evidencia), `diagnostico.deepseek.llamar_deepseek` (llamada HTTP
pura, sin lógica de negocio), y `diagnostico.gasto` (presupuesto
diario compartido) — nunca `diagnostico.store`/`model` ni la vía de
`causa_probable` (research.md §2 de specs/021-remediacion-contenedores/).

Dos tipos de acción:

- `rotar_log` (019): condición determinista, sin DeepSeek — rota
  (nunca borra) un log de una lista cerrada de 17 logs reales del
  homelab cuando supera un umbral de tamaño.
- `reiniciar_contenedor` (021): la decisión NO es una condición fija —
  para cada contenedor no crítico que no está `running and healthy`,
  se reúne su evidencia real y se le pregunta a DeepSeek si reiniciar
  resuelve el caso, o si ninguna acción de la lista cerrada aplica.

Cada tipo de acción (`rotar_log`) o cada contenedor individual
(`reiniciar_contenedor`) tiene un modo, `manual` (por defecto) o
`automatico`, que Miquel controla siempre él mismo desde
`remediacion.cli` — estar en la lista cerrada de acciones reversibles
es condición necesaria para poder actuar, nunca suficiente por sí sola
para hacerlo sin permiso.

En modo manual, una condición detectada (o una recomendación de
DeepSeek) se registra como propuesta pendiente de aprobación. En modo
automático, se ejecuta directamente y se registra igual. `rotar_log`
es además reversible con un procedimiento de rollback escrito
(Principio VI): rotar renombra, nunca trunca ni borra, y deshacer
nunca sobreescribe lo que se haya escrito después de la rotación.
`reiniciar_contenedor` no tiene esa vía de deshacer (FR-016 de 021) —
excepción documentada explícitamente, no incumplimiento silencioso.

No ejecuta nunca ninguna acción sobre un componente crítico ni sobre
`frigate` — ni siquiera les pregunta a DeepSeek (FR-006 de 021). No
expone ningún estado accionable en el dashboard — el CLI sigue siendo
la única superficie de control. Avisa por Telegram cuando: una
rotación automática falla (019), ninguna acción de DeepSeek aplica
(021, FR-009), el cortacircuito de reinicios se abre (021, FR-011), o
una incapacidad de evaluar persiste varios ciclos seguidos (021,
FR-019 — contrapartida del Principio VII enmendado en
constitution.md v2.0.0: `docker_monitor.py` cede la decisión de
reinicio de los no críticos a este paquete, pero esa cesión exige que
un fallo persistente para decidir nunca quede en silencio). Un éxito,
o un fallo en modo manual, nunca notifican.

Ver `specs/019-remediacion-automatica/` y
`specs/021-remediacion-contenedores/` para spec, plan y contratos.
"""
