from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.core.database import ahora_utc


def _validar_password_72_bytes(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("La contraseña debe ser una cadena de texto")
    bytes_len = len(v.encode("utf-8"))
    if bytes_len < 1 or bytes_len > 72:
        raise ValueError("La contraseña debe tener entre 1 y 72 bytes en UTF-8")
    return v


def _validar_texto_limpio(v: str) -> str:
    if "\x00" in v:
        raise ValueError("El texto no puede contener el carácter NUL")
    limpio = v.strip()
    if not limpio:
        raise ValueError("El campo no puede estar vacío")
    return limpio


def _validar_vence_en_futuro_con_tz(v: datetime | None) -> datetime | None:
    if v is None:
        return None
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("vence_en debe incluir zona horaria explícita")
    if v <= ahora_utc():
        raise ValueError("vence_en debe ser una fecha en el futuro")
    return v


PasswordBcryptStr = Annotated[str, AfterValidator(_validar_password_72_bytes)]
TextoNoVacio = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_validar_texto_limpio)]
RolValido = Literal["ADMIN", "RECEPCION", "MECANICO", "CLIENTE"]
VenceEnFuturo = Annotated[datetime | None, AfterValidator(_validar_vence_en_futuro_con_tz)]


# Constantes de acciones para evento_seguridad (DD-15)
ACCION_CARGA_INICIAL = "Carga de los datos iniciales"
ACCION_ALTA_CLIENTE = "Alta de usuario cliente"
ACCION_CAMBIO_PASSWORD = "Cambio de contraseña"
ACCION_ALTA_PERSONAL = "Alta de usuario de personal"
ACCION_ASIGNACION_ROL = "Asignación de rol"
ACCION_REVOCACION_ROL = "Revocación de rol"


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Contratos de entrada ---


class RegistroRequest(StrictSchema):
    email: EmailStr
    nombre: str = Field(min_length=1)
    password: PasswordBcryptStr
    documento: str = Field(min_length=1)
    telefono: str = Field(min_length=1)


class LoginRequest(StrictSchema):
    email: EmailStr
    password: PasswordBcryptStr


class CambiarPasswordRequest(StrictSchema):
    password_actual: PasswordBcryptStr
    password_nueva: PasswordBcryptStr


class AltaPersonalRequest(StrictSchema):
    email: EmailStr
    nombre: TextoNoVacio
    password: PasswordBcryptStr
    rol: RolValido


class AsignarRolRequest(StrictSchema):
    rol: RolValido
    vence_en: VenceEnFuturo = None


# --- Contratos de salida ---


class RegistroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    documento: str
    telefono: str
    cliente_id: int | None = None


class LoginResponse(BaseModel):
    mensaje: str = "Sesión iniciada"
    debe_cambiar_password: bool
    expira_en_segundos: int


class MensajeResponse(BaseModel):
    mensaje: str


class UsuarioYoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool
    roles_vigentes: list[str]
    roles_token: list[str]


class UsuarioPersonalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    activo: bool
    debe_cambiar_password: bool
    rol: str


class AsignacionRolResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    rol: str
    desde: datetime
    vence_en: datetime | None = None
    revocada_en: datetime | None = None
    otorgada_por: int | None = None


class EventoSeguridadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cuando: datetime
    actor: str
    accion: str
