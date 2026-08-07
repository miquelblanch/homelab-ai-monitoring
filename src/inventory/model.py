"""model — Entidades del inventario. Ver data-model.md.

Solo estructuras de datos (dataclasses) y las constantes de los valores
válidos por campo. Sin lógica de negocio — eso vive en evaluate.py,
identity.py y diff.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# Categorías de Componente — FR-001 a FR-006.
CATEGORIAS = (
    "contenedor",
    "integracion",
    "entidad_ha",
    "host_externo",
    "hermes",
    "telegram",
    "infra_monitorizacion",
)

# Estado de una declaración de estado esperado — FR-007.
ESTADO_DECLARADO_STATUS = ("vigente", "caducada", "ausente")

# Si un fallo llegaría al dashboard — FR-009.
LLEGA_A_DASHBOARD = ("si", "no", "sin_evidencia")

# Tipo de brecha — FR-011, Edge Case de FR-006.
TIPOS_BRECHA = (
    "sin_declaracion",
    "declaracion_caducada",
    "sin_vigilancia",
    "no_llega_a_dashboard",
    "riesgo_concentrado_telegram",
)

DISPARADORES = ("manual", "programado")

DECLARACION_CADUCA_DIAS = 90  # Clarification 3, FR-007


@dataclass
class Componente:
    """Unidad mínima de inventario — spec.md Key Entities."""

    categoria: str
    nombre_actual: str
    identificador_estable: str | None = None
    origen_sin_id_estable: bool = True
    es_intencionadamente_no_vigilado: bool = False
    last_reviewed_at: date | None = None
    primera_ejecucion_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.categoria not in CATEGORIAS:
            raise ValueError(f"categoría inválida: {self.categoria!r}")
        # Si hay identificador estable, no es "sin id estable".
        self.origen_sin_id_estable = self.identificador_estable is None


@dataclass
class Hallazgo:
    """La respuesta a las tres preguntas para un Componente en una
    Ejecución concreta — spec.md Key Entities."""

    ejecucion_id: int
    componente_id: int
    tiene_estado_declarado: bool
    estado_declarado_status: str
    esta_vigilado: bool
    llega_a_dashboard: str
    mecanismo_vigilancia: str | None = None
    es_brecha: bool = False
    id: int | None = None

    def __post_init__(self) -> None:
        if self.estado_declarado_status not in ESTADO_DECLARADO_STATUS:
            raise ValueError(
                f"estado_declarado_status inválido: {self.estado_declarado_status!r}"
            )
        if self.llega_a_dashboard not in LLEGA_A_DASHBOARD:
            raise ValueError(f"llega_a_dashboard inválido: {self.llega_a_dashboard!r}")
        if self.esta_vigilado and not self.mecanismo_vigilancia:
            raise ValueError("esta_vigilado=True exige mecanismo_vigilancia")


@dataclass
class Brecha:
    """Hallazgo derivado de un componente cuya respuesta a alguna de las
    tres preguntas no es plenamente satisfactoria — spec.md Key Entities."""

    hallazgo_id: int
    tipo: str
    primera_ejecucion_id: int
    contexto: str
    conocida_por_barrido_previo: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.tipo not in TIPOS_BRECHA:
            raise ValueError(f"tipo de brecha inválido: {self.tipo!r}")

    def es_nueva(self, ejecucion_actual_id: int) -> bool:
        return self.primera_ejecucion_id == ejecucion_actual_id


@dataclass
class Ejecucion:
    """Instantánea con fecha de una pasada completa — spec.md Key Entities."""

    disparador: str
    fecha: datetime = field(default_factory=datetime.utcnow)
    total_componentes: int = 0
    total_brechas: int = 0
    es_linea_base_referencia: bool = False
    id: int | None = None

    def __post_init__(self) -> None:
        if self.disparador not in DISPARADORES:
            raise ValueError(f"disparador inválido: {self.disparador!r}")
