from base64 import urlsafe_b64decode, urlsafe_b64encode
from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_bytes

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390000
PBKDF2_MIN_ITERATIONS = 100000
PBKDF2_MAX_ITERATIONS = 1000000
SALT_SIZE = 16


def hash_password(password: str) -> str:
    salt = token_bytes(SALT_SIZE)
    derived_key = pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    salt_b64 = urlsafe_b64encode(salt).decode("utf-8")
    hash_b64 = urlsafe_b64encode(derived_key).decode("utf-8")
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, hash_b64 = encoded_hash.split("$", maxsplit=3)
        if algorithm != f"pbkdf2_{PBKDF2_ALGORITHM}":
            return False

        iterations = int(iterations_str)
        if not PBKDF2_MIN_ITERATIONS <= iterations <= PBKDF2_MAX_ITERATIONS:
            return False

        salt = urlsafe_b64decode(salt_b64.encode("utf-8"))
        expected_hash = urlsafe_b64decode(hash_b64.encode("utf-8"))
    except (ValueError, TypeError):
        return False

    candidate_hash = pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return compare_digest(candidate_hash, expected_hash)
