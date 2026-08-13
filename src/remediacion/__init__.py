"""remediacion — Primera pieza del Frente 2 que ejecuta acciones reales
sobre el homelab (Principios IV-VIII, Modelo Operacional B). Paquete
independiente de `diagnostico` — no importa nada de ese módulo ni pasa
por DeepSeek: actúa sobre condiciones deterministas verificables en el
momento (research.md §1 de specs/019-remediacion-automatica/).

Un único tipo de acción en esta primera versión, `rotar_log`: rota
(nunca borra) un log de una lista cerrada de dos (`health-docker.log`,
`health-ha.log`) cuando supera un umbral de tamaño. Cada tipo de
acción tiene un modo, `manual` (por defecto) o `automatico`, que
Miquel controla siempre él mismo desde `remediacion.cli` — estar en la
lista cerrada de acciones reversibles es condición necesaria para
poder actuar, nunca suficiente por sí sola para hacerlo sin permiso.

En modo manual, una condición detectada se registra como propuesta
pendiente de aprobación. En modo automático, se ejecuta directamente y
se registra igual. En los dos modos, toda acción es reversible con un
procedimiento de rollback escrito (Principio VI): rotar renombra,
nunca trunca ni borra, y deshacer nunca sobreescribe lo que se haya
escrito después de la rotación.

No ejecuta nunca ninguna acción sobre un componente crítico. No
notifica por Telegram ni expone nada en el dashboard — el CLI es la
única superficie (FR-014). Ver specs/019-remediacion-automatica/ para
spec, plan y contratos.
"""
