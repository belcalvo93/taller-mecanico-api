from functools import lru_cache

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# Límites de validación (spec "configuracion").
JWT_SECRET_MIN_LENGTH = 32
BCRYPT_COST_MIN = 4
BCRYPT_COST_MAX = 31


class Settings(BaseSettings):
    """Configuración leída del entorno o de un .env no versionado.

    El entorno pisa al .env. Los secretos no tienen valor por defecto: si faltan
    o están vacíos, construir Settings falla y la app no arranca.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Base de datos
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr = Field(min_length=1)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    SQL_ECHO: bool = False

    # Token y cookie
    JWT_SECRET_KEY: SecretStr = Field(min_length=JWT_SECRET_MIN_LENGTH)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = Field(default=1800, gt=0)
    COOKIE_SECURE: bool = False

    # bcrypt
    BCRYPT_COST: int = Field(default=12, ge=BCRYPT_COST_MIN, le=BCRYPT_COST_MAX)
    BCRYPT_MAX_CONCURRENT: int = Field(default=4, ge=1)

    @computed_field(repr=False)
    @property
    def DATABASE_URL(self) -> str:
        # URL.create escapa @, : y / sin concatenar a mano (regla 17).
        return URL.create(
            "postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    """Settings perezoso y cacheado: nunca se instancia al importar (regla 7)."""
    return Settings()
