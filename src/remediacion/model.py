"""model — Entidades de remediación. Ver data-model.md.

Solo estructuras de datos (dataclasses) y las constantes de los valores
válidos por campo. Sin lógica de negocio — eso vive en acciones.py y
store.py.
"""

from __future__ import annotations

from dataclasses import dataclass

# Modo de un tipo de acción — data-model.md, FR-001/FR-002.
MODOS = ("manual", "automatico")

# Estado de un intento de remediación — data-model.md. Sin "aprobado"
# como estado persistido: aprobar ejecuta la rotación en la misma
# llamada (User Story 2 de spec.md).
ESTADOS = ("pendiente", "rechazado", "ejecutado", "fallido", "deshecho")


@dataclass
class ConfiguracionAccion:
    """El modo vigente de un tipo de acción — spec.md Key Entities.
    Empieza siempre en "manual" (FR-002); solo Miquel lo cambia."""

    tipo_accion: str
    modo: str = "manual"
    actualizado_en: str | None = None


@dataclass
class IntentoRemediacion:
    """Una propuesta o ejecución concreta de una acción — spec.md Key
    Entities. `modo_en_deteccion` conserva el modo vigente cuando se
    creó, para que el historial (FR-004) sea fiel aunque el modo
    cambie después."""

    tipo_accion: str
    componente: str
    ruta: str
    modo_en_deteccion: str
    estado: str
    detalle: str
    fichero_rotado: str | None = None
    creado_en: str | None = None
    resuelto_en: str | None = None
    id: int | None = None


# ── Contenedores (specs/021-remediacion-contenedores/) ──────────────────

# Estado de un intento de reinicio de contenedor — data-model.md de 021.
# Sin "deshecho": FR-016 no promete una operación de deshacer para esta
# acción, a diferencia de rotar_log.
ESTADOS_INTENTO_REINICIO = (
    "pendiente",
    "rechazado",
    "ejecutado",
    "fallido",
    "cortacircuito",
    "sin_accion",
    "sin_evaluar",
)


@dataclass
class ConfiguracionContenedor:
    """El modo vigente de un contenedor no crítico concreto — a
    diferencia de ConfiguracionAccion, la clave es el componente
    individual, no un tipo de acción entero (research.md §6 de 021)."""

    contenedor: str
    modo: str = "manual"
    actualizado_en: str | None = None


@dataclass
class IntentoReinicio:
    """Una propuesta o ejecución de reiniciar_contenedor originada por
    una evaluación de DeepSeek — data-model.md de 021. Sin campo de
    rollback (FR-016)."""

    contenedor: str
    modo_en_deteccion: str
    estado: str
    detalle: str
    episodio_id: int | None = None
    accion_recomendada: str | None = None
    razonamiento_deepseek: str | None = None
    coste_eur: float | None = None
    creado_en: str | None = None
    resuelto_en: str | None = None
    id: int | None = None


@dataclass
class EvaluacionDeepSeek:
    """Resultado interno de preguntarle a DeepSeek si una acción
    aplica a un contenedor concreto — no tiene tabla propia, se
    persiste como IntentoReinicio (data-model.md de 021)."""

    accion_recomendada: str | None
    razonamiento: str | None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    fallo: bool = False
    motivo_fallo: str | None = None
