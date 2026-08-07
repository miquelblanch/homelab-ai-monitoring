# Principios de entrada para `speckit-constitution`

>No es la constitución: es lo que se le pasa a la skill.
> Derivados de diferentes barridos.
> Modelo de actuación elegido: el agente actúa solo en acciones reversibles
> y de bajo riesgo; todo lo demás es propuesta.

Sistema de vigilancia profunda y remediación del homelab.

1. Ninguna alerta se silencia mientras la condición persista. NO NEGOCIABLE.
   Se puede espaciar la reemisión; no se puede callar.

2. Un componente está sano solo si demuestra su último resultado, no su
   ejecución. Código de salida y proceso vivo no son salud.

3. Todo lo vigilado tiene un estado esperado declarado. Lo que no lo tenga,
   no se vigila. La declaración caduca y se revisa.

4. Ninguna acción correctiva sin un diagnóstico que la justifique.

5. El agente actúa solo sobre una lista cerrada de acciones reversibles,
   declarada en el spec. Todo lo demás se detiene y espera aprobación
   humana explícita. NO NEGOCIABLE.

6. Reversible significa que la vuelta atrás está escrita.

7. Una acción, un actor. Nadie remedia lo que ya remedia otro. La
   remediación automática existente sigue funcionando aunque esto falle.

8. Toda acción e hipótesis se registra con su justificación y su desenlace.

9. Nada es mejor hasta que se mide contra la línea base: el barrido del
   01-08-2026 detectó 11 problemas reales invisibles al dashboard, con 2
   falsos positivos de 12.

10. Local por defecto. Lo que salga de la máquina se justifica caso por caso.

11. Toda conclusión debe ser reproducible en diferido.
