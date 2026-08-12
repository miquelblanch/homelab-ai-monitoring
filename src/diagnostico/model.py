"""model — Entidades del diagnóstico de episodios. Ver data-model.md.

Solo estructuras de datos (dataclasses) y las constantes de los valores
válidos por campo. Sin lógica de negocio — eso vive en evidencia.py,
deepseek.py y gasto.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Desenlace de una Hipótesis — data-model.md.
DESENLACES = ("confirmada", "descartada", "sin_evidencia_suficiente")

# Conclusión de un Diagnóstico — spec.md FR-007: exactamente uno de los dos.
CONCLUSION_TIPOS = ("causa_probable", "no_diagnosticable")


@dataclass
class Episodio:
    """Unidad de trabajo del agente — spec.md Key Entities. Una vez
    creado, `snapshot_evidencia` no se vuelve a tocar (FR-002).

    Generalizado en feature 009 (specs/009-diagnostico-discos/) para
    poder representar también un episodio de disco, en feature 010
    (specs/010-diagnostico-ha/) para uno de Home Assistant, en feature
    011 (specs/011-diagnostico-backups/) para uno de backup, en
    feature 012 (specs/012-diagnostico-relays/) para uno de relay
    `socat`, en feature 013 (specs/013-diagnostico-inventario/) para
    uno de brecha de cobertura del inventario, en feature 014
    (specs/014-diagnostico-hosts-externos/) para uno de host físico
    externo vigilado por Beszel, y en feature 015
    (specs/015-diagnostico-hub-beszel/) para uno del propio hub de
    Beszel — `componente` es el nombre genérico (nombre de contenedor,
    `label` de disco, `check_id` de `ha_monitor.CHECKS`, el momento ISO
    de una ejecución de `backup_diario_nvme.sh`, el nombre de un relay
    en vivo / el momento ISO en diferido, el `nombre_actual` de un
    componente del inventario, el nombre canónico de un host externo, o
    el momento ISO de un episodio del hub —sin ningún nombre, igual que
    backup, porque solo existe un hub—), `origen` distingue cuál de los
    ocho es
    (`"contenedor"`/`"disco"`/`"ha"`/`"backup"`/`"relay"`/`"inventario"`/`"host_externo"`/`"hub_beszel"`).
    Ninguno de los valores nuevos exige migración de esquema — `origen`
    ya es TEXT libre desde 009 (research.md §1 de 010)."""

    componente: str
    es_critico: bool
    en_vivo: bool
    ventana_inicio: str
    ventana_fin: str
    origen: str = "contenedor"
    snapshot_evidencia: dict = field(default_factory=dict)
    restart_history_id: int | None = None
    creado_en: str | None = None
    id: int | None = None


@dataclass
class Hipotesis:
    """Una causa probable propuesta para un episodio, con su contraste
    contra la evidencia — spec.md Key Entities."""

    diagnostico_id: int
    orden: int
    descripcion: str
    comprobacion: str
    desenlace: str
    id: int | None = None

    def __post_init__(self) -> None:
        if self.desenlace not in DESENLACES:
            raise ValueError(f"desenlace inválido: {self.desenlace!r}")


@dataclass
class Diagnostico:
    """El resultado de un intento de procesar un episodio — spec.md Key
    Entities. Un mismo episodio puede tener varios (Principio VIII)."""

    episodio_id: int
    conclusion_tipo: str
    conclusion_texto: str
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    coste_eur: float = 0.0
    creado_en: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.conclusion_tipo not in CONCLUSION_TIPOS:
            raise ValueError(f"conclusion_tipo inválido: {self.conclusion_tipo!r}")


@dataclass
class GastoDiario:
    """Acumulado de coste real en tokens de DeepSeek por día natural —
    spec.md Key Entities. El límite se congela por día (data-model.md)."""

    dia: str
    coste_eur_acumulado: float = 0.0
    limite_eur: float = 5.0
