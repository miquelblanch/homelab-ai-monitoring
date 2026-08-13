"""remediacion — Primera pieza del Frente 2 que ejecuta acciones reales
sobre el homelab (Principios IV-VIII, Modelo Operacional B). Paquete
independiente de `diagnostico` — no importa nada de ese módulo ni pasa
por DeepSeek: actúa sobre condiciones deterministas verificables en el
momento (research.md §1 de specs/019-remediacion-automatica/).

Un único tipo de acción en esta primera versión, `rotar_log`: rota
(nunca borra) un log de una lista cerrada de 17 logs reales del
homelab (LOGS_VIGILADOS, ampliada de 2 a 17 en research.md §7) cuando
supera un umbral de tamaño. Cada tipo de acción tiene un modo,
`manual` (por defecto) o `automatico`, que Miquel controla siempre él
mismo desde `remediacion.cli` — estar en la lista cerrada de acciones
reversibles es condición necesaria para poder actuar, nunca suficiente
por sí sola para hacerlo sin permiso.

En modo manual, una condición detectada se registra como propuesta
pendiente de aprobación. En modo automático, se ejecuta directamente y
se registra igual. En los dos modos, toda acción es reversible con un
procedimiento de rollback escrito (Principio VI): rotar renombra,
nunca trunca ni borra, y deshacer nunca sobreescribe lo que se haya
escrito después de la rotación.

No ejecuta nunca ninguna acción sobre un componente crítico. No
expone ningún estado accionable en el dashboard — el CLI sigue siendo
la única superficie de control (FR-014). Si una rotación en modo
automático falla, sí avisa por Telegram — único aviso que envía este
paquete, añadido el 2026-08-13 a petición de Miquel (research.md §11);
un éxito, o un fallo en modo manual, nunca notifican. Ver
specs/019-remediacion-automatica/ para spec, plan y contratos.
"""
