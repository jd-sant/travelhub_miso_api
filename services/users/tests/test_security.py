from core.security import hash_password, verify_password


def _replace_iterations(encoded_hash: str, iterations: int) -> str:
    algorithm, _, salt_b64, hash_b64 = encoded_hash.split("$", maxsplit=3)
    return f"{algorithm}${iterations}${salt_b64}${hash_b64}"


def test_verify_password_accepts_valid_hash() -> None:
    password = "miPasswordSegura123"
    encoded_hash = hash_password(password)

    assert verify_password(password, encoded_hash)


def test_verify_password_rejects_low_iterations() -> None:
    password = "miPasswordSegura123"
    encoded_hash = hash_password(password)
    poisoned_hash = _replace_iterations(encoded_hash, 1)

    assert not verify_password(password, poisoned_hash)


def test_verify_password_rejects_high_iterations() -> None:
    password = "miPasswordSegura123"
    encoded_hash = hash_password(password)
    poisoned_hash = _replace_iterations(encoded_hash, 5_000_000)

    assert not verify_password(password, poisoned_hash)
