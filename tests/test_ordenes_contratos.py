"""CH-08 grupo 2: contratos de entrada y de salida de órdenes (RN-10, RN-18)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import HistorialEstadoOrden, ItemOrden, OrdenTrabajo
from app.modules.ordenes.schemas import ItemOrdenCrear, OrdenCrear, armar_detalle
from app.modules.repuestos.models import Repuesto

CONSIGNA = {
    "vehiculo_id": 2,
    "falla": "Frenos que rechinan",
    "items": [{"repuesto_id": 2, "cantidad": 1}, {"repuesto_id": 4, "cantidad": 3}],
}


def con(**cambios):
    return {**CONSIGNA, **cambios}


def item(**kw):
    return {"repuesto_id": 1, "cantidad": 1, **kw}


def test_acepta_el_cuerpo_de_la_consigna():
    orden = OrdenCrear.model_validate(CONSIGNA)
    assert orden.vehiculo_id == 2
    assert [(i.repuesto_id, i.cantidad) for i in orden.items] == [(2, 1), (4, 3)]


@pytest.mark.parametrize("extra", [{"total": 1}, {"estado": "TERMINADA"}, {"creada_en": "2026-01-01T00:00:00Z"},
                                   {"mecanico_id": 4}])
def test_rechaza_campos_no_declarados_en_la_orden(extra):
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(**extra))


def test_rechaza_precio_en_un_item():
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(items=[item(precio_unitario="1.00")]))


def test_rechaza_items_vacios():
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(items=[]))


@pytest.mark.parametrize("falla", ["", "   ", "ruido\u0000raro", "x" * 501])
def test_rechaza_falla_invalida(falla):
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(falla=falla))


def test_falla_se_recorta():
    assert OrdenCrear.model_validate(con(falla="  ruido  ")).falla == "ruido"


def test_rechaza_repuesto_repetido():
    with pytest.raises(ValidationError, match="repet"):
        OrdenCrear.model_validate(con(items=[item(repuesto_id=3), item(repuesto_id=3, cantidad=2)]))
    OrdenCrear.model_validate(con(items=[item(repuesto_id=3), item(repuesto_id=4)]))


@pytest.mark.parametrize("cantidad", [0, -1, 10_001])
def test_cantidad_fuera_de_rango(cantidad):
    with pytest.raises(ValidationError):
        ItemOrdenCrear.model_validate(item(cantidad=cantidad))


@pytest.mark.parametrize("cantidad", [1, 10_000])
def test_cantidad_en_el_borde(cantidad):
    assert ItemOrdenCrear.model_validate(item(cantidad=cantidad)).cantidad == cantidad


@pytest.mark.parametrize("valor", [0, 2_147_483_648, -3])
def test_ids_fuera_de_rango(valor):
    with pytest.raises(ValidationError):
        ItemOrdenCrear.model_validate(item(repuesto_id=valor))
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(vehiculo_id=valor))


def test_ids_en_el_borde():
    assert ItemOrdenCrear.model_validate(item(repuesto_id=2_147_483_647)).repuesto_id == 2_147_483_647


def test_mas_de_cincuenta_items():
    muchos = [item(repuesto_id=n) for n in range(1, 52)]
    with pytest.raises(ValidationError):
        OrdenCrear.model_validate(con(items=muchos))
    OrdenCrear.model_validate(con(items=muchos[:50]))


# --- armar_detalle: función pura, sin base ---------------------------------------------

def _orden(items, historial, mecanico_id=None, estado="PENDIENTE", total="0.00"):
    cuando = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    orden = OrdenTrabajo(id=9, vehiculo_id=1, mecanico_id=mecanico_id, estado=estado,
                         falla="Ruido", creada_en=cuando, total=Decimal(total))
    cliente = Cliente(id=1, nombre="Laura Cliente", documento="1", telefono="1")
    vehiculo = Vehiculo(id=1, cliente_id=1, patente="AB123CD", marca="VW", modelo="Gol", anio=2015)
    vehiculo.cliente = cliente
    orden.vehiculo = vehiculo
    orden.items = [
        ItemOrden(id=i, orden_id=9, repuesto_id=r, cantidad=c, precio_unitario=Decimal(p),
                  repuesto=Repuesto(id=r, codigo=cod, descripcion=desc, precio=Decimal(p), stock=1))
        for i, r, c, p, cod, desc in items
    ]
    orden.historial = [
        HistorialEstadoOrden(id=n, orden_id=9, desde_estado=d, hasta_estado=h, usuario_id=u, cuando=cuando)
        for n, d, h, u in historial
    ]
    return orden


def test_armar_detalle_calcula_subtotales_ordena_items_y_serializa_importes():
    orden = _orden(
        items=[(2, 4, 3, "12000.00", "ACE-530", "Aceite"), (1, 2, 1, "32000.00", "FRE-010", "Pastillas")],
        historial=[(1, None, "PENDIENTE", 3)], total="68000.00",
    )
    detalle = armar_detalle(orden)
    assert [i.repuesto_id for i in detalle.items] == [2, 4]  # por id de ítem (1 y 2)
    assert [i.subtotal for i in detalle.items] == [Decimal("32000.00"), Decimal("36000.00")]
    assert (detalle.patente, detalle.cliente, detalle.mecanico_id) == ("AB123CD", "Laura Cliente", None)
    assert detalle.items[0].codigo == "FRE-010" and detalle.items[0].descripcion == "Pastillas"
    salida = detalle.model_dump(mode="json")
    assert salida["total"] == "68000.00"
    assert salida["items"][0]["precio_unitario"] == "32000.00"
    assert salida["items"][1]["subtotal"] == "36000.00"
    assert salida["historial"] == [
        {"desde_estado": None, "hasta_estado": "PENDIENTE", "usuario_id": 3, "cuando": "2026-10-28T12:00:00Z"}
    ]
    assert set(salida) == {"id", "estado", "patente", "cliente", "total", "creada_en",
                           "mecanico_id", "falla", "items", "historial"}


def test_armar_detalle_triangulado_con_otros_importes():
    orden = _orden(
        items=[(5, 7, 10, "6500.50", "BUJ", "Bujía")],
        historial=[(1, None, "PENDIENTE", 3), (2, "PENDIENTE", "EN_REPARACION", 4)],
        mecanico_id=4, estado="EN_REPARACION", total="65005.00",
    )
    detalle = armar_detalle(orden)
    assert detalle.items[0].subtotal == Decimal("65005.00")
    assert detalle.model_dump(mode="json")["items"][0]["subtotal"] == "65005.00"
    assert [h.hasta_estado for h in detalle.historial] == ["PENDIENTE", "EN_REPARACION"]
    assert detalle.mecanico_id == 4 and detalle.estado == "EN_REPARACION"
