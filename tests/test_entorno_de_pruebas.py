"""Entorno de pruebas: la fixture base_migrada (alembic upgrade head, nunca create_all)."""
import subprocess
import sys

import pytest

from tests.conftest import migrar_base_de_tests


@pytest.fixture
def espia_subprocess(monkeypatch):
    llamadas = []

    def falso_run(*args, **kwargs):
        llamadas.append((args, kwargs))

    monkeypatch.setattr(subprocess, "run", falso_run)
    return llamadas


def test_sin_alembic_ini_se_saltea_con_el_motivo(tmp_path, espia_subprocess):
    with pytest.raises(pytest.skip.Exception) as exc:
        migrar_base_de_tests(tmp_path, "taller_test")
    assert "se ejercita cuando CH-02 agregue las migraciones" in str(exc.value)
    assert espia_subprocess == []


@pytest.mark.parametrize("base", ["taller", "produccion", "taller_test_viejo"])
def test_la_guarda_rechaza_bases_que_no_terminan_en_test(tmp_path, espia_subprocess, base):
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    with pytest.raises(RuntimeError) as exc:
        migrar_base_de_tests(tmp_path, base)
    assert "_test" in str(exc.value)
    assert espia_subprocess == []


def test_con_alembic_ini_y_base_de_tests_corre_upgrade_head(tmp_path, espia_subprocess, monkeypatch):
    monkeypatch.delenv("ALEMBIC_DESTINO_TESTS", raising=False)
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    migrar_base_de_tests(tmp_path, "taller_test")
    (args, kwargs), = espia_subprocess
    assert args[0] == [sys.executable, "-m", "alembic", "upgrade", "head"]
    assert kwargs["check"] is True
    assert kwargs["cwd"] == tmp_path
    assert kwargs["env"]["POSTGRES_DB"] == "taller_test"


def test_el_destino_de_la_migracion_de_tests_se_puede_acotar(tmp_path, espia_subprocess, monkeypatch):
    # Permite correr la suite sin aplicar revisiones todavía no aprobadas (checkpoints de CH-02).
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    monkeypatch.setenv("ALEMBIC_DESTINO_TESTS", "0001")
    migrar_base_de_tests(tmp_path, "taller_test")
    (args, _), = espia_subprocess
    assert args[0][-2:] == ["upgrade", "0001"]


def test_sin_variable_el_destino_es_head(tmp_path, espia_subprocess, monkeypatch):
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    monkeypatch.delenv("ALEMBIC_DESTINO_TESTS", raising=False)
    migrar_base_de_tests(tmp_path, "taller_test")
    (args, _), = espia_subprocess
    assert args[0][-2:] == ["upgrade", "head"]


async def test_base_migrada_deja_la_tabla_de_versiones(base_migrada, client):
    # Se saltea hasta CH-02 (sin alembic.ini); con las migraciones corre de punta a punta.
    from sqlalchemy import text

    async with client._transport.app.state.session_factory() as session:
        resultado = await session.exec(text("SELECT count(*) FROM alembic_version"))
        assert resultado.scalar_one() == 1
