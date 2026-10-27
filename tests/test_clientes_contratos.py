"""CH-06: contratos de entrada y salida de clientes y vehículos (sin base)."""
import pytest
from pydantic import ValidationError

from app.modules.clientes.schemas import ClienteCrear, VehiculoCrear, VehiculoLeer

CLIENTE = dict(nombre="Ana Pérez", documento="40111222", telefono="261 555-1234")
VEHICULO = dict(patente="AE123BC", marca="Fiat", modelo="Cronos", anio=2022)


# --- ClienteCrear ------------------------------------------------------------------

def test_cliente_valido_sin_espacios_alrededor():
    c = ClienteCrear(**{**CLIENTE, "documento": "  40111222 ", "nombre": " Ana Pérez "})
    assert (c.documento, c.nombre) == ("40111222", "Ana Pérez")


@pytest.mark.parametrize("extra", [{"usuario_id": 6}, {"id": 1}, {"rol": "ADMIN"}])
def test_cliente_rechaza_campos_no_declarados(extra):
    with pytest.raises(ValidationError):
        ClienteCrear(**CLIENTE, **extra)


@pytest.mark.parametrize("campo", ["nombre", "documento", "telefono"])
@pytest.mark.parametrize("valor", ["", "   ", None])
def test_cliente_rechaza_vacios_y_nulos(campo, valor):
    with pytest.raises(ValidationError):
        ClienteCrear(**{**CLIENTE, campo: valor})


@pytest.mark.parametrize("campo", ["nombre", "documento", "telefono"])
def test_cliente_rechaza_faltantes(campo):
    datos = {k: v for k, v in CLIENTE.items() if k != campo}
    with pytest.raises(ValidationError):
        ClienteCrear(**datos)


@pytest.mark.parametrize("campo, largo", [("nombre", 121), ("documento", 21), ("telefono", 31)])
def test_cliente_rechaza_textos_demasiado_largos(campo, largo):
    with pytest.raises(ValidationError):
        ClienteCrear(**{**CLIENTE, campo: "1" * largo})
    ClienteCrear(**{**CLIENTE, campo: "1" * (largo - 1)})  # el borde se acepta


@pytest.mark.parametrize("campo", ["nombre", "documento", "telefono"])
def test_cliente_rechaza_el_caracter_nul(campo):
    # PostgreSQL no acepta NUL en un texto: sin esto terminaría en 500 (RN-18).
    with pytest.raises(ValidationError):
        ClienteCrear(**{**CLIENTE, campo: "40\x00111"})


# --- VehiculoCrear -----------------------------------------------------------------

@pytest.mark.parametrize("anio", [1950, 2100, 2015])
def test_anio_dentro_del_rango(anio):
    assert VehiculoCrear(**{**VEHICULO, "anio": anio}).anio == anio


@pytest.mark.parametrize("anio", [1949, 2101, 0, -2020, "dosmil", None, 2015.5])
def test_anio_fuera_del_rango_o_no_entero(anio):
    with pytest.raises(ValidationError):
        VehiculoCrear(**{**VEHICULO, "anio": anio})


@pytest.mark.parametrize(
    "entrada, guardada",
    [(" ae 123 bc ", "AE123BC"), ("abc123", "ABC123"), ("AE123BC", "AE123BC")],
)
def test_patente_normalizada(entrada, guardada):
    assert VehiculoCrear(**{**VEHICULO, "patente": entrada}).patente == guardada


@pytest.mark.parametrize("patente", ["", "   ", "AB-123-CD", "AB1", "A" * 11, "AÑ123BC", "AB\x00123"])
def test_patente_invalida(patente):
    with pytest.raises(ValidationError):
        VehiculoCrear(**{**VEHICULO, "patente": patente})


@pytest.mark.parametrize("extra", [{"cliente_id": 2}, {"borrado_en": None}, {"id": 9}])
def test_vehiculo_rechaza_campos_no_declarados(extra):
    with pytest.raises(ValidationError):
        VehiculoCrear(**VEHICULO, **extra)


@pytest.mark.parametrize("campo", ["marca", "modelo"])
def test_marca_y_modelo_obligatorios_y_acotados(campo):
    for valor in ("", "  ", "x" * 61):
        with pytest.raises(ValidationError):
            VehiculoCrear(**{**VEHICULO, campo: valor})


# --- Salidas -------------------------------------------------------------------------

def test_la_salida_del_vehiculo_no_expone_borrado_en():
    assert set(VehiculoLeer.model_fields) == {"id", "cliente_id", "patente", "marca", "modelo", "anio"}
