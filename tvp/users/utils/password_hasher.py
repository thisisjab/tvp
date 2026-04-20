from typing import Self

import structlog
from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = structlog.get_logger()


class PasswordHasher:
    def __init__(self: Self) -> None:
        self._ph: Argon2PasswordHasher = Argon2PasswordHasher()

    def hash(self: Self, *, plain_text: str) -> str:
        return self._ph.hash(plain_text)

    def verify(self: Self, *, hash_: str, plain_text: str) -> bool:
        try:
            self._ph.verify(hash_, plain_text)
        except VerifyMismatchError:
            return False
        except Exception as e:  # noqa: BLE001
            logger.warning("Cannot verify password.", exc_info=e)
            return False
        else:
            return True


password_hasher = PasswordHasher()
