"""CH-07: contratos de entrada y salida del módulo repuestos (sin base de datos)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto
from app.modules.repuestos.schemas import (
    HistorialPrecioLeer,
    MovimientoStockLeer,
    ReposicionCrear,
    RepuestoActualizar,
    RepuestoCrear,
    RepuestoLeer,
)

VALIDO = {"codigo": "FIL-010", "descripcion": "Filtro de aire", "precio": "5500.50", "stock_inicial": 3}


def campos_con_error(exc: pytest.ExceptionInfo[ValidationError]) -> set[str]:
    return {str(e["loc"][0]) for e in exc.value.errors()}


# --- RepuestoCrear (2.1) --------------------------------------------------------------------

def test_crear_valido_normaliza_textos_y_precio():
    datos = RepuestoCrear(**{**VALIDO, "codigo": "  FIL-010 ", "precio": 5500.5})
    assert datos.codigo == "FIL-010"
    assert datos.precio == Decimal("5500.5")
    assert datos.stock_inicial == 3


def test_crear_stock_inicial_por_defecto_es_cero():
    sin_stock = {k: v for k, v in VALIDO.items() if k != "stock_inicial"}
    assert RepuestoCrear(**sin_stock).stock_inicial == 0


@pytest.mark.parametrize("extra", [{"stock": 5}, {"borrado_en": "2026-10-28T10:00:00Z"}, {"id": 9}])
def test_crear_rechaza_campos_no_declarados(extra):
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**VALIDO, **extra)
    assert campos_con_error(exc) == set(extra)


@pytest.mark.parametrize("campo", ["codigo", "descripcion", "precio"])
def test_crear_exige_los_campos_obligatorios(campo):
    datos = {k: v for k, v in VALIDO.items() if k != campo}
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**datos)
    assert campos_con_error(exc) == {campo}


@pytest.mark.parametrize("codigo", ["", "   ", "AB\x00C", "X" * 41])
def test_crear_rechaza_codigo_vacio_con_nul_o_largo(codigo):
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**{**VALIDO, "codigo": codigo})
    assert campos_con_error(exc) == {"codigo"}


@pytest.mark.parametrize("descripcion", ["", "Filtro\x00", "D" * 201])
def test_crear_rechaza_descripcion_vacia_con_nul_o_larga(descripcion):
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**{**VALIDO, "descripcion": descripcion})
    assert campos_con_error(exc) == {"descripcion"}


@pytest.mark.parametrize("precio", [0, -1, "-0.01", "abc", "NaN", "Infinity", "12.345", "123456789.00"])
def test_crear_rechaza_precios_invalidos(precio):
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**{**VALIDO, "precio": precio})
    assert campos_con_error(exc) == {"precio"}


@pytest.mark.parametrize("precio", ["0.01", 1, "99999999.99"])
def test_crear_acepta_precios_en_el_borde(precio):
    assert RepuestoCrear(**{**VALIDO, "precio": precio}).precio > 0


@pytest.mark.parametrize("stock", [-1, 2_147_483_648, 1.5, "mucho"])
def test_crear_rechaza_stock_inicial_invalido(stock):
    with pytest.raises(ValidationError) as exc:
        RepuestoCrear(**{**VALIDO, "stock_inicial": stock})
    assert campos_con_error(exc) == {"stock_inicial"}


# --- RepuestoActualizar y ReposicionCrear (2.2) ---------------------------------------------

def test_actualizar_solo_trae_lo_enviado():
    datos = RepuestoActualizar(precio="9500.00")
    assert datos.model_dump(exclude_unset=True) == {"precio": Decimal("9500.00")}
    assert RepuestoActualizar(descripcion=" Nueva ").model_dump(exclude_unset=True) == {"descripcion": "Nueva"}


@pytest.mark.parametrize("extra", [{"stock": 5}, {"codigo": "NUEVO"}, {"borrado_en": None}])
def test_actualizar_rechaza_stock_codigo_y_campos_no_declarados(extra):
    with pytest.raises(ValidationError) as exc:
        RepuestoActualizar(**extra)
    assert campos_con_error(exc) == set(extra)


@pytest.mark.parametrize("campo", ["descripcion", "precio"])
def test_actualizar_rechaza_null_explicito(campo):
    with pytest.raises(ValidationError) as exc:
        RepuestoActualizar(**{campo: None})
    assert campos_con_error(exc) == {campo}


@pytest.mark.parametrize("precio", [0, "-5", "x", "10.999"])
def test_actualizar_rechaza_precio_invalido(precio):
    with pytest.raises(ValidationError) as exc:
        RepuestoActualizar(precio=precio)
    assert campos_con_error(exc) == {"precio"}


def test_actualizar_rechaza_descripcion_vacia():
    with pytest.raises(ValidationError):
        RepuestoActualizar(descripcion="  ")


def test_reposicion_motivo_por_defecto():
    datos = ReposicionCrear(cantidad=5)
    assert (datos.cantidad, datos.motivo) == (5, "Reposición")
    assert ReposicionCrear(cantidad=2, motivo=" Compra a proveedor ").motivo == "Compra a proveedor"


@pytest.mark.parametrize("cantidad", [0, -3, 2_147_483_648, 1.5, "muchas"])
def test_reposicion_rechaza_cantidad_invalida(cantidad):
    with pytest.raises(ValidationError) as exc:
        ReposicionCrear(cantidad=cantidad)
    assert campos_con_error(exc) == {"cantidad"}


@pytest.mark.parametrize("extra", [{"stock": 1}, {"orden_id": 2}])
def test_reposicion_rechaza_campos_no_declarados(extra):
    with pytest.raises(ValidationError):
        ReposicionCrear(cantidad=1, **extra)


@pytest.mark.parametrize("motivo", ["", "Mal\x00motivo", "M" * 201])
def test_reposicion_rechaza_motivo_invalido(motivo):
    with pytest.raises(ValidationError) as exc:
        ReposicionCrear(cantidad=1, motivo=motivo)
    assert campos_con_error(exc) == {"motivo"}


# --- Salidas (2.3) ----------------------------------------------------------------------------

AHORA = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def test_repuesto_leer_no_expone_borrado_en():
    repuesto = Repuesto(id=1, codigo="FIL-001", descripcion="Filtro de aceite", precio=Decimal("8500.00"),
                        stock=10, borrado_en=AHORA)
    salida = RepuestoLeer.model_validate(repuesto).model_dump()
    assert salida == {"id": 1, "codigo": "FIL-001", "descripcion": "Filtro de aceite",
                      "precio": Decimal("8500.00"), "stock": 10}


def test_repuesto_leer_serializa_el_precio_como_texto_con_dos_decimales():
    repuesto = Repuesto(id=1, codigo="FIL-001", descripcion="Filtro", precio=Decimal("8500.00"), stock=1)
    assert RepuestoLeer.model_validate(repuesto).model_dump(mode="json")["precio"] == "8500.00"


def test_movimiento_leer_trae_todos_los_campos():
    movimiento = MovimientoStock(id=7, repuesto_id=3, orden_id=None, usuario_id=1, cantidad=5,
                                 motivo="Reposición", cuando=AHORA)
    assert MovimientoStockLeer.model_validate(movimiento).model_dump() == {
        "id": 7, "repuesto_id": 3, "orden_id": None, "usuario_id": 1, "cantidad": 5,
        "motivo": "Reposición", "cuando": AHORA,
    }


def test_historial_precio_leer_trae_todos_los_campos():
    cambio = HistorialPrecio(id=2, repuesto_id=1, usuario_id=1, precio_anterior=Decimal("8500.00"),
                             precio_nuevo=Decimal("9500.00"), cuando=AHORA)
    assert HistorialPrecioLeer.model_validate(cambio).model_dump(mode="json") == {
        "id": 2, "repuesto_id": 1, "usuario_id": 1, "precio_anterior": "8500.00",
        "precio_nuevo": "9500.00", "cuando": "2026-10-28T12:00:00Z",
    }
