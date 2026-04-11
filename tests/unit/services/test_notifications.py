import pytest

from src.services import notifications


@pytest.mark.asyncio
async def test_send_critical_alert_skips_when_webhook_missing(monkeypatch, mocker) -> None:
    monkeypatch.setattr(notifications.settings.slack, "WEBHOOK_URL", "")
    async_client_cls = mocker.patch("src.services.notifications.httpx.AsyncClient")

    await notifications.send_critical_alert("order-1", "reason", {"status": "FAILED"})

    async_client_cls.assert_not_called()


@pytest.mark.asyncio
async def test_send_critical_alert_posts_payload(monkeypatch, mocker) -> None:
    monkeypatch.setattr(
        notifications.settings.slack,
        "WEBHOOK_URL",
        "https://hooks.slack.com/services/test/test/test",
    )

    mock_client = mocker.AsyncMock()
    mock_response = mocker.Mock()
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response

    async_client_cm = mocker.MagicMock()
    async_client_cm.__aenter__ = mocker.AsyncMock(return_value=mock_client)
    async_client_cm.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch("src.services.notifications.httpx.AsyncClient", return_value=async_client_cm)

    await notifications.send_critical_alert(
        order_id="order-42",
        reason="Order stuck in compensating",
        context={"billing_status": "SUCCESS"},
    )

    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.await_args.kwargs
    assert call_kwargs["json"]["attachments"][0]["title"].endswith("Order order-42")
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_send_critical_alert_handles_http_errors(monkeypatch, mocker) -> None:
    monkeypatch.setattr(
        notifications.settings.slack,
        "WEBHOOK_URL",
        "https://hooks.slack.com/services/test/test/test",
    )

    mock_client = mocker.AsyncMock()
    mock_client.post.side_effect = RuntimeError("network failed")

    async_client_cm = mocker.MagicMock()
    async_client_cm.__aenter__ = mocker.AsyncMock(return_value=mock_client)
    async_client_cm.__aexit__ = mocker.AsyncMock(return_value=None)
    mocker.patch("src.services.notifications.httpx.AsyncClient", return_value=async_client_cm)

    logger_error = mocker.patch.object(notifications.logger, "error")

    await notifications.send_critical_alert(
        order_id="order-42",
        reason="Order stuck in compensating",
        context={"inventory_status": "FAILED"},
    )

    logger_error.assert_called_once()
