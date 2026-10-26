"""El arnés de tests: base de tests fijada y cliente con la app arrancada."""
from app.core.config import get_settings
from main import app


def test_la_base_de_tests_gana_sobre_el_env():
    # Aunque el .env local diga POSTGRES_DB=taller, conftest fija taller_test.
    assert get_settings().POSTGRES_DB == "taller_test"


async def test_client_arranca_la_app(client):
    assert hasattr(app.state, "engine")
    assert app.state.settings.POSTGRES_DB == "taller_test"
