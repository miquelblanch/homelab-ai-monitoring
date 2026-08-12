"""diagnostico — Diagnóstico de Episodios (Frente 2, sin remediación).

Congela evidencia real de un episodio — de contenedor (en vivo o de
`restart_history`), de disco (feature 009, en vivo o de un momento
pasado concreto), de Home Assistant (feature 010: un check de entidad,
de recorder corrupto, o de disponibilidad de la API, en vivo o de un
momento pasado concreto), o de backup (feature 011: el log de una
ejecución de `backup_diario_nvme.sh`, en vivo o de un momento pasado
dentro de la ventana de retención) —, pide a DeepSeek varias hipótesis
de causa probable ya contrastadas contra esa evidencia, y registra cada
hipótesis y la conclusión final. No ejecuta ni propone ninguna acción
correctiva sobre el homelab — eso es explícitamente fuera de alcance
(spec.md FR-012, FR-013a de 007; FR-008 de 009, 010 y 011). El resto de
orígenes de la Central de Alarmas (relays, hosts externos, el hub de
Beszel, agentes, inventario) siguen fuera de alcance — generalizar a
cada uno queda para features posteriores. Ver
specs/007-diagnostico-episodios/, specs/009-diagnostico-discos/,
specs/010-diagnostico-ha/ y specs/011-diagnostico-backups/ para spec,
plan y contratos.
"""
