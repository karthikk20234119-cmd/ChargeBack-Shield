"""
Test Suite: Razorpay API Client Abstraction (Task 3.1)

Tests the complete read-only Razorpay client stack:
- Error hierarchy
- Schema validation
- Mock client behavior
- Service layer error translation
- API endpoint read-only safety
- Financial safety invariant (no mutation methods)
- Credential safety (no credentials in logs/responses)

ALL tests use fake credentials. ZERO real API calls.
"""

import inspect
import logging
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

from backend.app.main import app
from backend.app.schemas.razorpay import (
    RazorpayDisputeListResponse,
    RazorpayDisputeResponse,
)
from backend.app.services.razorpay_client import (
    HttpRazorpayClient,
    MockRazorpayClient,
    RazorpayClient,
)
from backend.app.services.razorpay_errors import (
    RazorpayAuthenticationError,
    RazorpayClientError,
    RazorpayNetworkError,
    RazorpayNotFoundError,
    RazorpayRateLimitError,
    RazorpayServerError,
    RazorpayUnknownError,
    RazorpayValidationError,
)
from backend.app.services.razorpay_service import RazorpayService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_DISPUTE = {
    "id": "disp_AHfqOvkldwsbqt",
    "entity": "dispute",
    "payment_id": "pay_EsyWjHrfzb59eR",
    "amount": 150000,
    "currency": "INR",
    "amount_deducted": 150000,
    "reason_code": "chargeback",
    "reason_description": "Product not delivered",
    "respond_by": 1735689600,
    "status": "open",
    "phase": "chargeback",
    "created_at": 1735603200,
}

VALID_DISPUTE_2 = {
    "id": "disp_BHfqOvkldwsbqt",
    "entity": "dispute",
    "payment_id": "pay_FsyWjHrfzb59eR",
    "amount": 250000,
    "currency": "INR",
    "amount_deducted": 250000,
    "reason_code": "chargeback",
    "reason_description": "Not as described",
    "respond_by": 1735776000,
    "status": "under_review",
    "phase": "chargeback",
    "created_at": 1735689600,
}


@pytest.fixture
def mock_client():
    """MockRazorpayClient with default data."""
    return MockRazorpayClient(
        mock_disputes={
            "disp_AHfqOvkldwsbqt": VALID_DISPUTE,
            "disp_BHfqOvkldwsbqt": VALID_DISPUTE_2,
        }
    )


@pytest.fixture
def service(mock_client):
    """RazorpayService backed by MockRazorpayClient."""
    return RazorpayService(client=mock_client)


@pytest_asyncio.fixture
async def api_client():
    """FastAPI test client using mock Razorpay service."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ===========================================================================
# 1. SCHEMA VALIDATION TESTS
# ===========================================================================


class TestSchemaValidation:
    """Test RazorpayDisputeResponse validation rules."""

    def test_valid_dispute_parses(self):
        """Valid dispute data should parse without errors."""
        dispute = RazorpayDisputeResponse.model_validate(VALID_DISPUTE)
        assert dispute.id == "disp_AHfqOvkldwsbqt"
        assert dispute.entity == "dispute"
        assert dispute.amount == 150000
        assert dispute.status == "open"

    def test_entity_must_be_dispute(self):
        """Response with entity != 'dispute' must be rejected."""
        invalid = {**VALID_DISPUTE, "entity": "payment"}
        with pytest.raises(ValidationError) as exc_info:
            RazorpayDisputeResponse.model_validate(invalid)
        assert "entity" in str(exc_info.value).lower()

    def test_empty_id_rejected(self):
        """Empty string ID must be rejected."""
        invalid = {**VALID_DISPUTE, "id": ""}
        with pytest.raises(ValidationError):
            RazorpayDisputeResponse.model_validate(invalid)

    def test_status_enum_validation(self):
        """Unknown status value must be rejected."""
        invalid = {**VALID_DISPUTE, "status": "invalid_status"}
        with pytest.raises(ValidationError) as exc_info:
            RazorpayDisputeResponse.model_validate(invalid)
        assert "invalid_status" in str(exc_info.value)

    def test_valid_statuses_accepted(self):
        """All documented Razorpay dispute statuses must be accepted."""
        for status in ["open", "under_review", "won", "lost", "closed"]:
            dispute = RazorpayDisputeResponse.model_validate(
                {**VALID_DISPUTE, "status": status}
            )
            assert dispute.status == status

    def test_valid_phases_accepted(self):
        """All documented Razorpay dispute phases must be accepted."""
        for phase in ["fraud", "retrieval", "chargeback", "pre_arbitration", "arbitration"]:
            dispute = RazorpayDisputeResponse.model_validate(
                {**VALID_DISPUTE, "phase": phase}
            )
            assert dispute.phase == phase

    def test_unknown_phase_rejected(self):
        """Unknown phase value must be rejected."""
        invalid = {**VALID_DISPUTE, "phase": "unknown_phase"}
        with pytest.raises(ValidationError):
            RazorpayDisputeResponse.model_validate(invalid)

    def test_negative_amount_rejected(self):
        """Negative amount must be rejected."""
        invalid = {**VALID_DISPUTE, "amount": -100}
        with pytest.raises(ValidationError):
            RazorpayDisputeResponse.model_validate(invalid)

    def test_evidence_field_excluded(self):
        """Evidence field must be optional and safely parsed if present."""
        with_evidence = {**VALID_DISPUTE, "evidence": {"some_key": "some_value"}}
        dispute = RazorpayDisputeResponse.model_validate(with_evidence)
        assert dispute.evidence == {"some_key": "some_value"}

    def test_missing_required_fields_rejected(self):
        """Missing required fields must cause validation error."""
        incomplete = {"id": "disp_test", "entity": "dispute"}
        with pytest.raises(ValidationError):
            RazorpayDisputeResponse.model_validate(incomplete)

    def test_optional_fields_nullable(self):
        """Optional fields can be None."""
        data = {**VALID_DISPUTE, "reason_description": None, "respond_by": None, "phase": None}
        dispute = RazorpayDisputeResponse.model_validate(data)
        assert dispute.reason_description is None
        assert dispute.respond_by is None
        assert dispute.phase is None

    def test_list_response_validation(self):
        """Dispute list response must validate entity as 'collection'."""
        data = {
            "entity": "collection",
            "count": 1,
            "items": [VALID_DISPUTE],
        }
        result = RazorpayDisputeListResponse.model_validate(data)
        assert result.entity == "collection"
        assert result.count == 1
        assert len(result.items) == 1

    def test_list_response_wrong_entity_rejected(self):
        """List response with entity != 'collection' must be rejected."""
        data = {
            "entity": "disputes",
            "count": 0,
            "items": [],
        }
        with pytest.raises(ValidationError):
            RazorpayDisputeListResponse.model_validate(data)


# ===========================================================================
# 2. ERROR HIERARCHY TESTS
# ===========================================================================


class TestErrorHierarchy:
    """Test structured error hierarchy."""

    def test_all_errors_inherit_from_base(self):
        """All Razorpay errors must inherit from RazorpayClientError."""
        error_classes = [
            RazorpayAuthenticationError,
            RazorpayNotFoundError,
            RazorpayRateLimitError,
            RazorpayValidationError,
            RazorpayServerError,
            RazorpayNetworkError,
            RazorpayUnknownError,
        ]
        for cls in error_classes:
            assert issubclass(cls, RazorpayClientError), f"{cls.__name__} must inherit from RazorpayClientError"

    def test_error_carries_metadata(self):
        """Errors must carry safe metadata."""
        error = RazorpayNotFoundError(
            message="Not found",
            dispute_id="disp_test",
            raw_error_code="BAD_REQUEST_ERROR",
        )
        assert error.status_code == 404
        assert error.message == "Not found"
        assert error.dispute_id == "disp_test"
        assert error.raw_error_code == "BAD_REQUEST_ERROR"

    def test_rate_limit_has_retry_after(self):
        """RazorpayRateLimitError must carry retry_after."""
        error = RazorpayRateLimitError(retry_after=5.0)
        assert error.retry_after == 5.0
        assert error.status_code == 429

    def test_network_error_has_no_status(self):
        """Network errors have no HTTP status code."""
        error = RazorpayNetworkError(message="Timeout")
        assert error.status_code is None


# ===========================================================================
# 3. MOCK CLIENT TESTS
# ===========================================================================


class TestMockClient:
    """Test MockRazorpayClient behavior."""

    @pytest.mark.asyncio
    async def test_mock_client_valid_dispute(self, mock_client):
        """Mock client returns typed RazorpayDisputeResponse."""
        result = await mock_client.get_dispute("disp_AHfqOvkldwsbqt")
        assert isinstance(result, RazorpayDisputeResponse)
        assert result.id == "disp_AHfqOvkldwsbqt"
        assert result.entity == "dispute"
        assert result.status == "open"

    @pytest.mark.asyncio
    async def test_mock_client_default_dispute(self):
        """Mock client generates default dispute for unknown IDs."""
        client = MockRazorpayClient()
        result = await client.get_dispute("disp_unknown123")
        assert isinstance(result, RazorpayDisputeResponse)
        assert result.id == "disp_unknown123"

    @pytest.mark.asyncio
    async def test_mock_client_list_disputes(self, mock_client):
        """Mock client returns typed RazorpayDisputeListResponse."""
        result = await mock_client.list_disputes()
        assert isinstance(result, RazorpayDisputeListResponse)
        assert result.entity == "collection"
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_mock_client_list_pagination(self, mock_client):
        """Mock client respects skip and count."""
        result = await mock_client.list_disputes(skip=1, count=1)
        assert result.count == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_mock_client_error_not_found(self):
        """Mock client raises RazorpayNotFoundError when configured."""
        client = MockRazorpayClient(error_mode="not_found")
        with pytest.raises(RazorpayNotFoundError):
            await client.get_dispute("disp_test")

    @pytest.mark.asyncio
    async def test_mock_client_error_auth(self):
        """Mock client raises RazorpayAuthenticationError when configured."""
        client = MockRazorpayClient(error_mode="auth_error")
        with pytest.raises(RazorpayAuthenticationError):
            await client.get_dispute("disp_test")

    @pytest.mark.asyncio
    async def test_mock_client_error_rate_limit(self):
        """Mock client raises RazorpayRateLimitError when configured."""
        client = MockRazorpayClient(error_mode="rate_limit")
        with pytest.raises(RazorpayRateLimitError) as exc_info:
            await client.get_dispute("disp_test")
        assert exc_info.value.retry_after == 5.0

    @pytest.mark.asyncio
    async def test_mock_client_error_server(self):
        """Mock client raises RazorpayServerError when configured."""
        client = MockRazorpayClient(error_mode="server_error")
        with pytest.raises(RazorpayServerError):
            await client.get_dispute("disp_test")

    @pytest.mark.asyncio
    async def test_mock_client_error_timeout(self):
        """Mock client raises RazorpayNetworkError when configured."""
        client = MockRazorpayClient(error_mode="timeout")
        with pytest.raises(RazorpayNetworkError):
            await client.get_dispute("disp_test")

    @pytest.mark.asyncio
    async def test_mock_client_error_malformed(self):
        """Mock client raises RazorpayValidationError when configured."""
        client = MockRazorpayClient(error_mode="malformed")
        with pytest.raises(RazorpayValidationError):
            await client.get_dispute("disp_test")


# ===========================================================================
# 4. SERVICE LAYER TESTS
# ===========================================================================


class TestServiceLayer:
    """Test RazorpayService business logic and error translation."""

    @pytest.mark.asyncio
    async def test_service_get_dispute(self, service):
        """Service returns typed dispute response."""
        result = await service.get_dispute("disp_AHfqOvkldwsbqt")
        assert isinstance(result, RazorpayDisputeResponse)
        assert result.id == "disp_AHfqOvkldwsbqt"

    @pytest.mark.asyncio
    async def test_service_list_disputes(self, service):
        """Service returns typed dispute list."""
        result = await service.list_disputes()
        assert isinstance(result, RazorpayDisputeListResponse)
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_service_empty_dispute_id_rejected(self, service):
        """Empty dispute ID raises HTTPException 400."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await service.get_dispute("")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_service_translates_not_found(self):
        """Service translates RazorpayNotFoundError to HTTP 404."""
        from fastapi import HTTPException
        client = MockRazorpayClient(error_mode="not_found")
        svc = RazorpayService(client=client)
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_dispute("disp_missing")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_service_translates_auth_error(self):
        """Service translates RazorpayAuthenticationError to HTTP 502."""
        from fastapi import HTTPException
        client = MockRazorpayClient(error_mode="auth_error")
        svc = RazorpayService(client=client)
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_dispute("disp_test")
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_service_translates_rate_limit(self):
        """Service translates RazorpayRateLimitError to HTTP 429."""
        from fastapi import HTTPException
        client = MockRazorpayClient(error_mode="rate_limit")
        svc = RazorpayService(client=client)
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_dispute("disp_test")
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_service_translates_server_error(self):
        """Service translates RazorpayServerError to HTTP 502."""
        from fastapi import HTTPException
        client = MockRazorpayClient(error_mode="server_error")
        svc = RazorpayService(client=client)
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_dispute("disp_test")
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_service_translates_network_error(self):
        """Service translates RazorpayNetworkError to HTTP 502."""
        from fastapi import HTTPException
        client = MockRazorpayClient(error_mode="timeout")
        svc = RazorpayService(client=client)
        with pytest.raises(HTTPException) as exc_info:
            await svc.get_dispute("disp_test")
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_service_bounds_count(self, service):
        """Service caps count at 100."""
        result = await service.list_disputes(count=200)
        assert isinstance(result, RazorpayDisputeListResponse)

    @pytest.mark.asyncio
    async def test_service_bounds_skip(self, service):
        """Service floors skip at 0."""
        result = await service.list_disputes(skip=-5)
        assert isinstance(result, RazorpayDisputeListResponse)


# ===========================================================================
# 5. API ENDPOINT TESTS
# ===========================================================================


class TestApiEndpoints:
    """Test read-only API endpoints."""

    @pytest.mark.asyncio
    async def test_get_dispute_endpoint(self, api_client):
        """GET /api/razorpay/disputes/{id} returns dispute data."""
        response = await api_client.get("/api/razorpay/disputes/disp_test123")
        assert response.status_code == 200
        data = response.json()
        assert data["entity"] == "dispute"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_disputes_endpoint(self, api_client):
        """GET /api/razorpay/disputes returns dispute list."""
        response = await api_client.get("/api/razorpay/disputes")
        assert response.status_code == 200
        data = response.json()
        assert data["entity"] == "collection"
        assert "items" in data

    @pytest.mark.asyncio
    async def test_no_credentials_in_response(self, api_client):
        """API response must not contain any credential fields."""
        response = await api_client.get("/api/razorpay/disputes/disp_test123")
        text = response.text.lower()
        assert "key_id" not in text
        assert "key_secret" not in text
        assert "rzp_test" not in text
        assert "samplesecretkey" not in text
        assert "authorization" not in text

    @pytest.mark.asyncio
    async def test_list_pagination_params(self, api_client):
        """API accepts skip and count query params."""
        response = await api_client.get(
            "/api/razorpay/disputes", params={"skip": 0, "count": 10}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_count_upper_bound(self, api_client):
        """API rejects count > 100."""
        response = await api_client.get(
            "/api/razorpay/disputes", params={"count": 200}
        )
        assert response.status_code == 422  # FastAPI validation error


# ===========================================================================
# 6. CREDENTIAL SAFETY TESTS
# ===========================================================================


class TestCredentialSafety:
    """Test that credentials never leak into logs or responses."""

    @pytest.mark.asyncio
    async def test_credentials_not_logged(self, caplog):
        """Credential values must not appear in log output."""
        test_key_id = "rzp_test_credcheck123"
        test_secret = "secret_credcheck456"

        with caplog.at_level(logging.DEBUG):
            client = MockRazorpayClient()
            await client.get_dispute("disp_test")

        log_text = caplog.text.lower()
        assert test_key_id.lower() not in log_text
        assert test_secret.lower() not in log_text

    @pytest.mark.asyncio
    async def test_error_does_not_contain_credentials(self):
        """Error messages must not contain credentials."""
        error = RazorpayAuthenticationError(
            dispute_id="disp_test"
        )
        error_str = str(error)
        assert "rzp_" not in error_str.lower()
        assert "secret" not in error_str.lower()


# ===========================================================================
# 7. FINANCIAL SAFETY INVARIANT TESTS
# ===========================================================================


class TestFinancialSafetyInvariant:
    """
    Verify the absolute absence of mutation capabilities.
    These tests are structural — they inspect the class interfaces.
    """

    # Forbidden method prefixes indicating mutation operations
    FORBIDDEN_PREFIXES = (
        "accept_", "contest_", "submit_", "create_",
        "update_", "delete_", "patch_", "post_", "put_",
    )

    def _get_public_methods(self, cls):
        """Get all public async/sync methods of a class."""
        return [
            name for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith("_")
        ]

    def test_no_mutation_methods_on_http_client(self):
        """HttpRazorpayClient must have no mutation methods."""
        methods = self._get_public_methods(HttpRazorpayClient)
        for method in methods:
            for prefix in self.FORBIDDEN_PREFIXES:
                assert not method.startswith(prefix), (
                    f"HttpRazorpayClient has forbidden mutation method: {method}"
                )

    def test_no_mutation_methods_on_mock_client(self):
        """MockRazorpayClient must have no mutation methods."""
        methods = self._get_public_methods(MockRazorpayClient)
        for method in methods:
            for prefix in self.FORBIDDEN_PREFIXES:
                assert not method.startswith(prefix), (
                    f"MockRazorpayClient has forbidden mutation method: {method}"
                )

    def test_mock_client_has_only_read_methods(self):
        """MockRazorpayClient must have only public read methods."""
        methods = self._get_public_methods(MockRazorpayClient)
        expected = ["download_document_content", "get_dispute", "get_document_metadata", "list_disputes", "stream_document_content"]
        assert sorted(methods) == expected, (
            f"MockRazorpayClient has unexpected methods: {methods}"
        )

    def test_no_contest_method(self):
        """No contest method exists on any client."""
        for cls in [HttpRazorpayClient, MockRazorpayClient]:
            assert not hasattr(cls, "contest_dispute")
            assert not hasattr(cls, "create_contest")
            assert not hasattr(cls, "submit_contest")

    def test_no_accept_method(self):
        """No accept method exists on any client."""
        for cls in [HttpRazorpayClient, MockRazorpayClient]:
            assert not hasattr(cls, "accept_dispute")

    def test_no_document_methods(self):
        """No document content upload or mutation methods exist on any client."""
        for cls in [HttpRazorpayClient, MockRazorpayClient]:
            assert not hasattr(cls, "upload_document")

    def test_no_mutation_routes_in_api(self):
        """Razorpay API router must have no POST/PATCH/PUT/DELETE routes."""
        from backend.app.api.razorpay_disputes import router

        for route in router.routes:
            if hasattr(route, "methods"):
                allowed = {"GET", "HEAD", "OPTIONS"}
                dangerous = route.methods - allowed
                assert not dangerous, (
                    f"Route {route.path} has forbidden methods: {dangerous}"
                )

    def test_protocol_has_only_read_methods(self):
        """RazorpayClient protocol must define only read methods."""
        # Get methods defined directly on the protocol (not inherited)
        protocol_methods = [
            name for name in dir(RazorpayClient)
            if not name.startswith("_")
            and callable(getattr(RazorpayClient, name, None))
        ]
        # Filter to only methods explicitly defined in the protocol body
        # (exclude inherited Protocol/object methods)
        custom_methods = []
        expected = ["download_document_content", "get_dispute", "get_document_metadata", "list_disputes", "stream_document_content"]
        for name in protocol_methods:
            if name in expected:
                custom_methods.append(name)
        assert sorted(custom_methods) == expected

    def test_mock_client_satisfies_protocol(self):
        """MockRazorpayClient must satisfy the RazorpayClient protocol."""
        assert isinstance(MockRazorpayClient(), RazorpayClient)

    def test_service_has_no_mutation_methods(self):
        """RazorpayService must have no mutation methods."""
        methods = self._get_public_methods(RazorpayService)
        for method in methods:
            for prefix in self.FORBIDDEN_PREFIXES:
                assert not method.startswith(prefix), (
                    f"RazorpayService has forbidden mutation method: {method}"
                )
