from unittest.mock import patch, MagicMock

import pytest
from adapters.services.smtp_otp_sender import SmtpOtpSender


@patch("smtplib.SMTP")
def test_smtp_otp_sender_sends_email(mock_smtp_class):
    mock_server = MagicMock()
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("os.environ", {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test@gmail.com",
        "SMTP_PASSWORD": "app-password",
        "SMTP_FROM": "test@gmail.com",
    }):

        sender = SmtpOtpSender()
        sender.send("user@example.com", "123456")

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@gmail.com", "app-password")
        mock_server.sendmail.assert_called_once()
        call_args = mock_server.sendmail.call_args
        assert call_args[0][1] == "user@example.com"
        assert "123456" in call_args[0][2]


@patch("smtplib.SMTP")
def test_smtp_otp_sender_raises_on_failure(mock_smtp_class):
    mock_server = MagicMock()
    mock_server.sendmail.side_effect = Exception("SMTP error")
    mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
    mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

    with patch.dict("os.environ", {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_USER": "test@gmail.com",
        "SMTP_PASSWORD": "app-password",
        "SMTP_FROM": "test@gmail.com",
    }):

        sender = SmtpOtpSender()
        with pytest.raises(Exception, match="SMTP error"):
            sender.send("user@example.com", "123456")
