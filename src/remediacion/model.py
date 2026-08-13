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
