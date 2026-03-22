"""Unit tests for request/response infrastructure."""

import pytest
from gulp_sdk.utils import RequestLogger, RetryPolicy, format_error_message


@pytest.mark.unit
async def test_request_logger_mask_headers():
    """Test that sensitive headers are masked."""
    logger = RequestLogger()
    
    headers = {
        "authorization": "Bearer secret-token",
        "content-type": "application/json",
        "x-api-key": "api-secret",
    }
    
    masked = logger._mask_headers(headers)
    assert masked["authorization"] == "***MASKED***"
    assert masked["x-api-key"] == "***MASKED***"
    assert masked["content-type"] == "application/json"


@pytest.mark.unit
async def test_retry_policy_should_retry():
    """Test retry policy decision logic."""
    policy = RetryPolicy(max_retries=3)
    
    # Should retry on 5xx
    assert policy.should_retry(500, 0)
    assert policy.should_retry(503, 0)
    
    # Should retry on specific client errors
    assert policy.should_retry(429, 0)  # Too many requests
    assert policy.should_retry(408, 0)  # Request timeout
    
    # Should not retry on client errors
    assert not policy.should_retry(400, 0)
    assert not policy.should_retry(404, 0)
    assert not policy.should_retry(401, 0)
    
    # Should stop after max retries
    assert not policy.should_retry(500, 3)


@pytest.mark.unit
async def test_retry_policy_delay():
    """Test exponential backoff delay calculation."""
    policy = RetryPolicy(
        max_retries=3,
        initial_delay=1.0,
        max_delay=10.0,
        backoff_factor=2.0,
    )
    
    # Delays should increase exponentially
    delay_0 = policy.get_delay(0)
    delay_1 = policy.get_delay(1)
    delay_2 = policy.get_delay(2)
    
    assert 0.9 < delay_0 < 1.1  # ~1.0 ± 10% jitter
    assert 1.8 < delay_1 < 2.2  # ~2.0 ± 10% jitter
    assert 3.6 < delay_2 < 4.4  # ~4.0 ± 10% jitter


@pytest.mark.unit
async def test_format_error_message():
    """Test error message formatting."""
    msg = format_error_message("Operation failed", status_code=404)
    assert "404" in msg
    assert "Operation failed" in msg
    
    msg = format_error_message(
        "Bad request",
        status_code=422,
        response_data={"data": "Invalid parameter"},
    )
    assert "422" in msg
    assert "Invalid parameter" in msg
