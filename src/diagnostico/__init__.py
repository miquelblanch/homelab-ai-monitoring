"""diagnostico — Diagnóstico de Episodios (Frente 2, sin remediación).

Congela evidencia real de un episodio de contenedor (en vivo o de
`restart_history`), pide a DeepSeek varias hipótesis de causa probable ya
contrastadas contra esa evidencia, y registra cada hipótesis y la
conclusión final. No ejecuta ni propone ninguna acción correctiva sobre
el homelab — eso es explícitamente fuera de alcance (spec.md FR-012,
FR-013a). Ver specs/007-diagnostico-episodios/ para spec, plan y
contratos.
"""
