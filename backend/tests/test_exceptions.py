"""
Unit tests for custom exception hierarchy.

Tests exception mapping, status codes, and error serialization including:
- Base AppError functionality (to_dict, context handling)
- Client errors (400-level): ValidationError, AuthenticationError, etc.
- Server errors (500-level): DatabaseError, CacheError, ConfigurationError
- External service errors (503): ExternalServiceError with service context
"""

from src.core.exceptions import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    CacheError,
    ConfigurationError,
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

# ===== Base AppError Tests =====


class TestAppError:
    """Test base AppError functionality"""

    def test_create_app_error(self):
        """Test creating basic AppError"""
        # Act
        error = AppError("Something went wrong")

        # Assert
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.status_code == 500  # Default
        assert error.error_type == "internal_error"

    def test_app_error_with_context(self):
        """Test AppError with additional context"""
        # Act
        error = AppError("User operation failed", user_id="123", action="delete")

        # Assert
        assert error.message == "User operation failed"
        assert error.context == {"user_id": "123", "action": "delete"}

    def test_app_error_to_dict(self):
        """Test AppError serialization to dict"""
        # Arrange
        error = AppError("Error occurred", user_id="456", symbol="AAPL")

        # Act
        result = error.to_dict()

        # Assert
        assert result == {
            "error_type": "internal_error",
            "message": "Error occurred",
            "status_code": 500,
            "user_id": "456",
            "symbol": "AAPL",
        }

    def test_app_error_to_dict_no_context(self):
        """Test to_dict without additional context"""
        # Arrange
        error = AppError("Simple error")

        # Act
        result = error.to_dict()

        # Assert
        assert result == {
            "error_type": "internal_error",
            "message": "Simple error",
            "status_code": 500,
        }

    def test_app_error_empty_context(self):
        """Test AppError with explicitly empty context"""
        # Arrange
        error = AppError("Test message")

        # Assert
        assert error.context == {}


# ===== Client Error Tests (400-level) =====


class TestValidationError:
    """Test ValidationError (400)"""

    def test_validation_error_status_code(self):
        """Test ValidationError has 400 status code"""
        # Arrange & Act
        error = ValidationError("Invalid email format")

        # Assert
        assert error.status_code == 400
        assert error.error_type == "validation_error"

    def test_validation_error_to_dict(self):
        """Test ValidationError serialization"""
        # Arrange
        error = ValidationError("Missing required field", field="email")

        # Act
        result = error.to_dict()

        # Assert
        assert result["status_code"] == 400
        assert result["error_type"] == "validation_error"
        assert result["message"] == "Missing required field"
        assert result["field"] == "email"


class TestAuthenticationError:
    """Test AuthenticationError (401)"""

    def test_authentication_error_status_code(self):
        """Test AuthenticationError has 401 status code"""
        # Arrange & Act
        error = AuthenticationError("Invalid credentials")

        # Assert
        assert error.status_code == 401
        assert error.error_type == "authentication_error"

    def test_authentication_error_with_context(self):
        """Test AuthenticationError with context"""
        # Arrange
        error = AuthenticationError("Token expired", token_type="access")

        # Act
        result = error.to_dict()

        # Assert
        assert result["status_code"] == 401
        assert result["token_type"] == "access"


class TestAuthorizationError:
    """Test AuthorizationError (403)"""

    def test_authorization_error_status_code(self):
        """Test AuthorizationError has 403 status code"""
        # Arrange & Act
        error = AuthorizationError("Insufficient permissions")

        # Assert
        assert error.status_code == 403
        assert error.error_type == "authorization_error"

    def test_authorization_error_with_resource(self):
        """Test AuthorizationError with resource context"""
        # Arrange
        error = AuthorizationError(
            "Access denied", resource="admin_panel", required_role="admin"
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["resource"] == "admin_panel"
        assert result["required_role"] == "admin"


class TestNotFoundError:
    """Test NotFoundError (404)"""

    def test_not_found_error_status_code(self):
        """Test NotFoundError has 404 status code"""
        # Arrange & Act
        error = NotFoundError("User not found")

        # Assert
        assert error.status_code == 404
        assert error.error_type == "not_found_error"

    def test_not_found_error_with_id(self):
        """Test NotFoundError with resource ID"""
        # Arrange
        error = NotFoundError("Portfolio not found", portfolio_id="123")

        # Act
        result = error.to_dict()

        # Assert
        assert result["message"] == "Portfolio not found"
        assert result["portfolio_id"] == "123"


class TestRateLimitError:
    """Test RateLimitError (429)"""

    def test_rate_limit_error_status_code(self):
        """Test RateLimitError has 429 status code"""
        # Arrange & Act
        error = RateLimitError("Too many requests")

        # Assert
        assert error.status_code == 429
        assert error.error_type == "rate_limit_error"

    def test_rate_limit_error_with_retry_info(self):
        """Test RateLimitError with retry information"""
        # Arrange
        error = RateLimitError(
            "Rate limit exceeded", retry_after=60, limit=100, window="1h"
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["retry_after"] == 60
        assert result["limit"] == 100
        assert result["window"] == "1h"


# ===== Server Error Tests (500-level) =====


class TestDatabaseError:
    """Test DatabaseError (500)"""

    def test_database_error_status_code(self):
        """Test DatabaseError has 500 status code"""
        # Arrange & Act
        error = DatabaseError("Connection timeout")

        # Assert
        assert error.status_code == 500
        assert error.error_type == "database_error"

    def test_database_error_with_details(self):
        """Test DatabaseError with connection details"""
        # Arrange
        error = DatabaseError(
            "Query failed", collection="users", operation="find", query={"age": 25}
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["collection"] == "users"
        assert result["operation"] == "find"
        assert result["query"] == {"age": 25}


class TestCacheError:
    """Test CacheError (500)"""

    def test_cache_error_status_code(self):
        """Test CacheError has 500 status code"""
        # Arrange & Act
        error = CacheError("Redis connection failed")

        # Assert
        assert error.status_code == 500
        assert error.error_type == "cache_error"

    def test_cache_error_with_key(self):
        """Test CacheError with cache key"""
        # Arrange
        error = CacheError("Failed to get value", key="user:123:session", ttl=3600)

        # Act
        result = error.to_dict()

        # Assert
        assert result["key"] == "user:123:session"
        assert result["ttl"] == 3600


class TestConfigurationError:
    """Test ConfigurationError (500)"""

    def test_configuration_error_status_code(self):
        """Test ConfigurationError has 500 status code"""
        # Arrange & Act
        error = ConfigurationError("Missing environment variable")

        # Assert
        assert error.status_code == 500
        assert error.error_type == "configuration_error"

    def test_configuration_error_with_var_name(self):
        """Test ConfigurationError with variable details"""
        # Arrange
        error = ConfigurationError(
            "Required env var not set", var_name="DATABASE_URL", required=True
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["var_name"] == "DATABASE_URL"
        assert result["required"] is True


# ===== External Service Error Tests (503) =====


class TestExternalServiceError:
    """Test ExternalServiceError (503)"""

    def test_external_service_error_status_code(self):
        """Test ExternalServiceError has 503 status code"""
        # Arrange & Act
        error = ExternalServiceError("API timeout", service="yfinance")

        # Assert
        assert error.status_code == 503
        assert error.error_type == "external_service_error"

    def test_external_service_error_requires_service(self):
        """Test ExternalServiceError requires service parameter"""
        # Act
        error = ExternalServiceError("Service unavailable", service="tencent_ses")

        # Assert
        assert error.context["service"] == "tencent_ses"

    def test_external_service_error_to_dict(self):
        """Test ExternalServiceError serialization includes service"""
        # Arrange
        error = ExternalServiceError(
            "Rate limit exceeded", service="dashscope", endpoint="/v1/chat"
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["status_code"] == 503
        assert result["error_type"] == "external_service_error"
        assert result["service"] == "dashscope"
        assert result["endpoint"] == "/v1/chat"

    def test_external_service_error_multiple_contexts(self):
        """Test ExternalServiceError with multiple context fields"""
        # Arrange
        error = ExternalServiceError(
            "API call failed",
            service="alpha_vantage",
            symbol="AAPL",
            function="TIME_SERIES_DAILY",
            attempt=3,
        )

        # Act
        result = error.to_dict()

        # Assert
        assert result["service"] == "alpha_vantage"
        assert result["symbol"] == "AAPL"
        assert result["function"] == "TIME_SERIES_DAILY"
        assert result["attempt"] == 3


# ===== Exception Hierarchy Tests =====


class TestExceptionHierarchy:
    """Test exception inheritance and polymorphism"""

    def test_all_exceptions_inherit_from_app_error(self):
        """Test that all custom exceptions inherit from AppError"""
        # Arrange
        exceptions = [
            ValidationError,
            AuthenticationError,
            AuthorizationError,
            NotFoundError,
            RateLimitError,
            DatabaseError,
            CacheError,
            ConfigurationError,
            ExternalServiceError,
        ]

        # Act & Assert
        for exc_class in exceptions:
            error = (
                exc_class("Test")
                if exc_class != ExternalServiceError
                else exc_class("Test", service="test")
            )
            assert isinstance(error, AppError)
            assert isinstance(error, Exception)

    def test_all_exceptions_have_unique_error_types(self):
        """Test that each exception has unique error_type"""
        # Arrange
        error_types = {
            ValidationError: "validation_error",
            AuthenticationError: "authentication_error",
            AuthorizationError: "authorization_error",
            NotFoundError: "not_found_error",
            RateLimitError: "rate_limit_error",
            DatabaseError: "database_error",
            CacheError: "cache_error",
            ConfigurationError: "configuration_error",
            ExternalServiceError: "external_service_error",
        }

        # Act & Assert
        for exc_class, expected_type in error_types.items():
            error = (
                exc_class("Test")
                if exc_class != ExternalServiceError
                else exc_class("Test", service="test")
            )
            assert error.error_type == expected_type

    def test_all_exceptions_have_valid_status_codes(self):
        """Test that all exceptions have appropriate HTTP status codes"""
        # Arrange
        status_codes = {
            ValidationError: 400,
            AuthenticationError: 401,
            AuthorizationError: 403,
            NotFoundError: 404,
            RateLimitError: 429,
            DatabaseError: 500,
            CacheError: 500,
            ConfigurationError: 500,
            ExternalServiceError: 503,
        }

        # Act & Assert
        for exc_class, expected_code in status_codes.items():
            error = (
                exc_class("Test")
                if exc_class != ExternalServiceError
                else exc_class("Test", service="test")
            )
            assert error.status_code == expected_code

    def test_exceptions_can_be_caught_as_app_error(self):
        """Test that all exceptions can be caught as AppError"""
        # Arrange
        error = ValidationError("Test validation")

        # Act & Assert
        try:
            raise error
        except AppError as e:
            assert e.message == "Test validation"
            assert e.status_code == 400

    def test_exceptions_can_be_caught_as_base_exception(self):
        """Test that all exceptions can be caught as Python Exception"""
        # Arrange
        error = DatabaseError("Test database")

        # Act & Assert
        try:
            raise error
        except Exception as e:
            assert str(e) == "Test database"


# ===== Integration Tests =====


class TestExceptionIntegration:
    """Test realistic exception usage scenarios"""

    def test_api_error_response_format(self):
        """Test that exception dict matches expected API response format"""
        # Arrange
        error = ValidationError("Email format invalid", field="email", value="invalid")

        # Act
        response = error.to_dict()

        # Assert - should have standard API error structure
        assert "error_type" in response
        assert "message" in response
        assert "status_code" in response
        assert response["status_code"] == 400

    def test_exception_context_preserved_through_dict(self):
        """Test that context is preserved in serialization"""
        # Arrange
        context = {
            "user_id": "12345",
            "symbol": "AAPL",
            "operation": "buy",
            "quantity": 100,
        }
        error = AuthorizationError("Insufficient balance", **context)

        # Act
        result = error.to_dict()

        # Assert
        for key, value in context.items():
            assert result[key] == value

    def test_multiple_exceptions_with_same_context_key(self):
        """Test that different exceptions can use same context keys"""
        # Arrange
        db_error = DatabaseError("Query failed", query="SELECT * FROM users")
        cache_error = CacheError("Get failed", query="user:123")

        # Act
        db_dict = db_error.to_dict()
        cache_dict = cache_error.to_dict()

        # Assert - both can have 'query' but different error_types
        assert db_dict["query"] == "SELECT * FROM users"
        assert cache_dict["query"] == "user:123"
        assert db_dict["error_type"] != cache_dict["error_type"]
