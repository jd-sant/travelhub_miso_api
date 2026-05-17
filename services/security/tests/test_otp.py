from core.otp import generate_otp


def test_generate_otp_returns_six_digits():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_generate_otp_pads_with_zeros():
    """Even small numbers should be zero-padded to 6 digits."""
    # Run many times to catch the padding logic
    for _ in range(100):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()


def test_generate_otp_custom_length():
    otp = generate_otp(length=8)
    assert len(otp) == 8
    assert otp.isdigit()
