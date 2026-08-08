"""test_evaluate — T024 (caducidad, intencionados, completitud FR-010) y
T029 (clasificación de brechas, US2). Sin tocar Docker/HA/Telegram
reales: las respuestas de `_homelab_bridge` se controlan con
`unittest.mock.patch`.
"""

from __future__ import annotations

from datetime import date, timedelta
from time import time
from unittest.mock import patch

from inventory import evaluate
from inventory.model import CATEGORIAS, Componente
from inventory.sources import RawComponente
from tests.selftest import check


def _raw(categoria: str, nombre: str, **meta) -> RawComponente:
    return RawComponente(
        componente=Componente(categoria=categoria, nombre_actual=nombre),
        meta=meta,
    )


def test_caducidad_90_dias() -> None:
    hoy = date(2026, 8, 8)
    check(
        "sin fecha de revisión no es caducada",
        evaluate.is_declaration_stale(None, hoy) is False,
    )
    check(
        "revisada hace 89 días sigue vigente",
        evaluate.is_declaration_stale(hoy - timedelta(days=89), hoy) is False,
    )
    check(
        "revisada hace 91 días está caducada",
        evaluate.is_declaration_stale(hoy - timedelta(days=91), hoy) is True,
    )
    check(
        "exactamente 90 días todavía no caduca (> no >=)",
        evaluate.is_declaration_stale(hoy - timedelta(days=90), hoy) is False,
    )


def test_intencionados() -> None:
    with patch.object(evaluate.bridge, "docker_never_restart", return_value={"frigate"}):
        check(
            "frigate es intencionado",
            evaluate.is_intentional(_raw("contenedor", "frigate")) is True,
        )
        check(
            "otro contenedor no lo es",
            evaluate.is_intentional(_raw("contenedor", "traefik")) is False,
        )

    check(
        "entidad HA deshabilitada es intencionada",
        evaluate.is_intentional(
            _raw("entidad_ha", "sensor.x", disabled_by="user")
        )
        is True,
    )
    check(
        "entidad HA habilitada no lo es",
        evaluate.is_intentional(_raw("entidad_ha", "sensor.x", disabled_by=None))
        is False,
    )


def test_completitud_fr010() -> None:
    """Ninguna categoría puede devolver una respuesta vacía/None en los
    tres campos — FR-010."""
    with patch.object(evaluate.bridge, "docker_never_restart", return_value=set()), \
         patch.object(evaluate.bridge, "ha_monitor_checked_entities", return_value=set()), \
         patch.object(evaluate.bridge, "read_heartbeat", return_value=None):
        for categoria in CATEGORIAS:
            raw = _raw(categoria, f"componente-de-prueba-{categoria}")
            ev = evaluate.evaluate_component(raw)
            check(
                f"{categoria}: estado_declarado_status tiene valor",
                ev.estado_declarado_status in ("vigente", "caducada", "ausente"),
            )
            check(
                f"{categoria}: llega_a_dashboard tiene valor",
                ev.llega_a_dashboard in ("si", "no", "sin_evidencia"),
            )
            check(
                f"{categoria}: esta_vigilado es booleano",
                isinstance(ev.esta_vigilado, bool),
            )


def test_declaracion_sin_revision_es_vigente() -> None:
    with patch.object(evaluate.bridge, "docker_never_restart", return_value=set()):
        ev = evaluate.evaluate_component(_raw("contenedor", "traefik"), last_reviewed_at=None)
        check(
            "componente recién declarado (sin fecha) cuenta como vigente",
            ev.estado_declarado_status == "vigente",
        )


def test_declaracion_caducada_se_refleja() -> None:
    vieja = date.today() - timedelta(days=200)
    with patch.object(evaluate.bridge, "docker_never_restart", return_value=set()):
        ev = evaluate.evaluate_component(_raw("contenedor", "traefik"), last_reviewed_at=vieja)
        check(
            "declaración de hace 200 días sale caducada",
            ev.estado_declarado_status == "caducada",
        )


def test_vigilancia_telegram_por_latido_real() -> None:
    """FR-006, actualizado el 2026-08-08 al construir telegram_monitor.py:
    ya no es 'siempre False' — depende del latido real, con caducidad
    propia (15 min, tres pasadas del monitor cada 5 min)."""
    with patch.object(evaluate.bridge, "read_heartbeat", return_value=None):
        ev = evaluate.evaluate_component(_raw("telegram", "Canal de entrega de Telegram"))
        check("sin latido nunca ⇒ no vigilado", ev.esta_vigilado is False)
        check("sin latido ⇒ mecanismo vacío", ev.mecanismo_vigilancia is None)

    with patch.object(
        evaluate.bridge, "read_heartbeat",
        return_value={"epoch": time(), "status": "ok"},
    ):
        ev = evaluate.evaluate_component(_raw("telegram", "Canal de entrega de Telegram"))
        check("latido reciente ⇒ vigilado", ev.esta_vigilado is True)
        check("latido reciente ⇒ mecanismo informado", ev.mecanismo_vigilancia is not None)
        check("sigue sin llegar al dashboard homelab", ev.llega_a_dashboard == "no")

    with patch.object(
        evaluate.bridge, "read_heartbeat",
        return_value={"epoch": time() - 3600, "status": "ok"},  # hace 1 h
    ):
        ev = evaluate.evaluate_component(_raw("telegram", "Canal de entrega de Telegram"))
        check("latido rancio (>15 min) ⇒ no cuenta como vigilado", ev.esta_vigilado is False)


def test_clasificacion_telegram_solo_es_riesgo_si_no_vigilado() -> None:
    vigilado = evaluate.EvaluacionParcial(
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="telegram_monitor.py",
        llega_a_dashboard="no",
        es_intencionado=False,
    )
    check(
        "telegram vigilado pero sin llegar al dashboard ⇒ tipo normal, no riesgo concentrado",
        evaluate.classify_gap(vigilado, "telegram") == "no_llega_a_dashboard",
    )

    no_vigilado = evaluate.EvaluacionParcial(
        tiene_estado_declarado=False,
        estado_declarado_status="ausente",
        esta_vigilado=False,
        mecanismo_vigilancia=None,
        llega_a_dashboard="no",
        es_intencionado=False,
    )
    check(
        "telegram sin vigilar de verdad ⇒ sigue siendo riesgo concentrado",
        evaluate.classify_gap(no_vigilado, "telegram") == "riesgo_concentrado_telegram",
    )


def test_es_brecha_respeta_intencionados() -> None:
    ev_mala = evaluate.EvaluacionParcial(
        tiene_estado_declarado=False,
        estado_declarado_status="ausente",
        esta_vigilado=False,
        mecanismo_vigilancia=None,
        llega_a_dashboard="no",
        es_intencionado=True,
    )
    check(
        "intencionado nunca es brecha, aunque las tres respuestas fallen",
        evaluate.es_brecha(ev_mala) is False,
    )

    ev_ok = evaluate.EvaluacionParcial(
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="docker_monitor.py",
        llega_a_dashboard="si",
        es_intencionado=False,
    )
    check("las tres respuestas satisfactorias no es brecha", evaluate.es_brecha(ev_ok) is False)

    ev_falla_dashboard = evaluate.EvaluacionParcial(
        tiene_estado_declarado=True,
        estado_declarado_status="vigente",
        esta_vigilado=True,
        mecanismo_vigilancia="docker_monitor.py",
        llega_a_dashboard="no",
        es_intencionado=False,
    )
    check(
        "fallar solo 'llega al dashboard' ya cuenta como brecha",
        evaluate.es_brecha(ev_falla_dashboard) is True,
    )
