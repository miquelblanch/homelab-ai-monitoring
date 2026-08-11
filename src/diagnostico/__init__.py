"""diagnostico — Diagnóstico de Episodios (Frente 2, sin remediación).

Congela evidencia real de un episodio — de contenedor (en vivo o de
`restart_history`) o de disco (feature 009, en vivo o de un momento
pasado concreto) —, pide a DeepSeek varias hipótesis de causa probable
ya contrastadas contra esa evidencia, y registra cada hipótesis y la
conclusión final. No ejecuta ni propone ninguna acción correctiva sobre
el homelab — eso es explícitamente fuera de alcance (spec.md FR-012,
FR-013a de 007; FR-008 de 009). El resto de orígenes de la Central de
Alarmas (Home Assistant, backups, relays, hosts externos, el hub de
Beszel, agentes, inventario) siguen fuera de alcance — generalizar a
cada uno queda para features posteriores. Ver
specs/007-diagnostico-episodios/ y specs/009-diagnostico-discos/ para
spec, plan y contratos.
"""
