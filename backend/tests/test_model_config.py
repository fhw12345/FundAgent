"""
Unit tests for model configuration and pricing system.

Tests configuration dataclasses, pricing calculations, and model registry including:
- ModelPricing and ModelConfig dataclass creation
- calculate_cost_in_credits function with thinking mode
- MODELS registry structure and completeness
- get_model_config function with error handling
- get_all_models sorting and ordering
- estimate_cost wrapper function
"""

import pytest

from src.core.model_config import (
    CREDIT_TO_CNY_RATE,
    DEFAULT_MODEL,
    MODELS,
    ModelConfig,
    ModelPricing,
    calculate_cost_in_credits,
    estimate_cost,
    get_all_models,
    get_model_config,
)


# ===== ModelPricing Dataclass Tests =====


class TestModelPricing:
    """Test ModelPricing dataclass."""

    def test_create_model_pricing(self):
        """Test creating ModelPricing instance."""
        # Arrange & Act
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )

        # Assert
        assert pricing.input_cost_per_1k == 0.001
        assert pricing.output_cost_per_1k == 0.002
        assert pricing.thinking_output_multiplier == 1.0  # Default

    def test_model_pricing_with_thinking_multiplier(self):
        """Test ModelPricing with custom thinking multiplier."""
        # Arrange & Act
        pricing = ModelPricing(
            input_cost_per_1k=0.0008,
            output_cost_per_1k=0.002,
            thinking_output_multiplier=4.0,
        )

        # Assert
        assert pricing.thinking_output_multiplier == 4.0

    def test_model_pricing_default_multiplier_is_one(self):
        """Test default thinking multiplier is 1.0 (no increase)."""
        # Arrange & Act
        pricing = ModelPricing(
            input_cost_per_1k=0.006,
            output_cost_per_1k=0.024,
        )

        # Assert
        assert pricing.thinking_output_multiplier == 1.0


# ===== ModelConfig Dataclass Tests =====


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_create_model_config(self):
        """Test creating complete ModelConfig instance."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )

        # Act
        config = ModelConfig(
            model_id="test-model",
            display_name="Test Model",
            provider="test-provider",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=True,
            description="Test model description",
            order=1,
        )

        # Assert
        assert config.model_id == "test-model"
        assert config.display_name == "Test Model"
        assert config.provider == "test-provider"
        assert config.pricing == pricing
        assert config.max_tokens == 4096
        assert config.default_max_tokens == 1000
        assert config.supports_thinking is True
        assert config.description == "Test model description"
        assert config.order == 1


# ===== calculate_cost_in_credits Tests =====


class TestCalculateCostInCredits:
    """Test credit cost calculation function."""

    def test_basic_cost_calculation(self):
        """Test basic cost calculation without thinking mode."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,  # ¥0.001 per 1K tokens
            output_cost_per_1k=0.002,  # ¥0.002 per 1K tokens
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act: 1000 input, 500 output
        # Input cost: (1000/1000) * 0.001 = 0.001 CNY
        # Output cost: (500/1000) * 0.002 = 0.001 CNY
        # Total: 0.002 CNY = 0.002 / 0.001 = 2 credits
        cost = calculate_cost_in_credits(
            input_tokens=1000,
            output_tokens=500,
            model_config=config,
            thinking_enabled=False,
        )

        # Assert
        assert cost == 2.0

    def test_cost_with_thinking_mode_enabled(self):
        """Test cost calculation with thinking mode multiplier."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.0008,
            output_cost_per_1k=0.002,
            thinking_output_multiplier=4.0,  # 4x for thinking
        )
        config = ModelConfig(
            model_id="qwen-plus",
            display_name="Qwen Plus",
            provider="alibaba",
            pricing=pricing,
            max_tokens=32768,
            default_max_tokens=3000,
            supports_thinking=True,
            description="Balanced",
            order=1,
        )

        # Act: 1000 input, 1000 output with thinking
        # Input: (1000/1000) * 0.0008 = 0.0008 CNY
        # Output: (1000/1000) * 0.002 * 4.0 = 0.008 CNY
        # Total: 0.0088 CNY = 0.0088 / 0.001 = 8.8 credits
        cost = calculate_cost_in_credits(
            input_tokens=1000,
            output_tokens=1000,
            model_config=config,
            thinking_enabled=True,
        )

        # Assert
        assert cost == 8.8

    def test_cost_with_thinking_disabled_no_multiplier(self):
        """Test thinking mode OFF uses standard pricing."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.0008,
            output_cost_per_1k=0.002,
            thinking_output_multiplier=4.0,
        )
        config = ModelConfig(
            model_id="qwen-plus",
            display_name="Qwen Plus",
            provider="alibaba",
            pricing=pricing,
            max_tokens=32768,
            default_max_tokens=3000,
            supports_thinking=True,
            description="Balanced",
            order=1,
        )

        # Act: Same tokens, thinking OFF
        # Input: 0.0008 CNY
        # Output: (1000/1000) * 0.002 * 1.0 = 0.002 CNY (no 4x)
        # Total: 0.0028 CNY = 2.8 credits
        cost = calculate_cost_in_credits(
            input_tokens=1000,
            output_tokens=1000,
            model_config=config,
            thinking_enabled=False,
        )

        # Assert
        assert cost == 2.8

    def test_thinking_mode_ignored_if_not_supported(self):
        """Test thinking multiplier ignored if model doesn't support thinking."""
        # Arrange: Model doesn't support thinking
        pricing = ModelPricing(
            input_cost_per_1k=0.006,
            output_cost_per_1k=0.024,
        )
        config = ModelConfig(
            model_id="qwen3-max",
            display_name="Qwen3 Max",
            provider="alibaba",
            pricing=pricing,
            max_tokens=65536,
            default_max_tokens=4000,
            supports_thinking=False,  # Does NOT support thinking
            description="Premium",
            order=4,
        )

        # Act: Thinking enabled but model doesn't support it
        # Input: (1000/1000) * 0.006 = 0.006 CNY
        # Output: (1000/1000) * 0.024 * 1.0 = 0.024 CNY (no multiplier)
        # Total: 0.03 CNY = 30 credits
        cost = calculate_cost_in_credits(
            input_tokens=1000,
            output_tokens=1000,
            model_config=config,
            thinking_enabled=True,  # Ignored
        )

        # Assert
        assert cost == 30.0

    def test_zero_tokens_zero_cost(self):
        """Test zero tokens results in zero cost."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act
        cost = calculate_cost_in_credits(
            input_tokens=0,
            output_tokens=0,
            model_config=config,
        )

        # Assert
        assert cost == 0.0

    def test_input_only_cost(self):
        """Test cost calculation with only input tokens."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act: Only input tokens
        # Input: (2000/1000) * 0.001 = 0.002 CNY = 2 credits
        cost = calculate_cost_in_credits(
            input_tokens=2000,
            output_tokens=0,
            model_config=config,
        )

        # Assert
        assert cost == 2.0

    def test_output_only_cost(self):
        """Test cost calculation with only output tokens."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act: Only output tokens
        # Output: (1500/1000) * 0.002 = 0.003 CNY = 3 credits
        cost = calculate_cost_in_credits(
            input_tokens=0,
            output_tokens=1500,
            model_config=config,
        )

        # Assert
        assert cost == 3.0

    def test_cost_rounded_to_two_decimals(self):
        """Test that cost is rounded to 2 decimal places."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.0007,
            output_cost_per_1k=0.0013,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act: Should result in non-round number
        # Input: (1234/1000) * 0.0007 = 0.0008638 CNY
        # Output: (5678/1000) * 0.0013 = 0.0073814 CNY
        # Total: 0.0082452 CNY = 8.2452 credits → 8.25
        cost = calculate_cost_in_credits(
            input_tokens=1234,
            output_tokens=5678,
            model_config=config,
        )

        # Assert
        assert cost == 8.25

    def test_negative_input_tokens_raises_error(self):
        """Test that negative input tokens raises ValueError."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="input_tokens must be non-negative"):
            calculate_cost_in_credits(
                input_tokens=-100,
                output_tokens=500,
                model_config=config,
            )

    def test_negative_output_tokens_raises_error(self):
        """Test that negative output tokens raises ValueError."""
        # Arrange
        pricing = ModelPricing(
            input_cost_per_1k=0.001,
            output_cost_per_1k=0.002,
        )
        config = ModelConfig(
            model_id="test",
            display_name="Test",
            provider="test",
            pricing=pricing,
            max_tokens=4096,
            default_max_tokens=1000,
            supports_thinking=False,
            description="Test",
            order=1,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="output_tokens must be non-negative"):
            calculate_cost_in_credits(
                input_tokens=500,
                output_tokens=-100,
                model_config=config,
            )


# ===== MODELS Registry Tests =====


class TestModelsRegistry:
    """Test MODELS registry structure and data."""

    def test_models_registry_not_empty(self):
        """Test that MODELS registry is not empty."""
        # Assert
        assert len(MODELS) > 0

    def test_models_registry_has_expected_models(self):
        """Test that MODELS contains expected model IDs."""
        # Assert - Known models as of implementation
        expected_models = ["qwen-plus", "qwen3-max", "deepseek-v3.2-exp", "deepseek-v3"]
        for model_id in expected_models:
            assert model_id in MODELS, f"Model '{model_id}' missing from registry"

    def test_all_models_have_complete_config(self):
        """Test that all models have complete configuration."""
        # Act & Assert
        for model_id, config in MODELS.items():
            assert isinstance(config, ModelConfig)
            assert config.model_id == model_id
            assert config.display_name
            assert config.provider
            assert config.pricing
            assert config.max_tokens > 0
            assert config.default_max_tokens > 0
            assert config.description
            assert config.order > 0

    def test_all_models_have_alibaba_provider(self):
        """Test that all current models use Alibaba provider."""
        # Act & Assert
        for config in MODELS.values():
            assert config.provider == "alibaba"

    def test_all_models_have_positive_pricing(self):
        """Test that all models have positive pricing."""
        # Act & Assert
        for config in MODELS.values():
            assert config.pricing.input_cost_per_1k > 0
            assert config.pricing.output_cost_per_1k > 0

    def test_default_model_exists_in_registry(self):
        """Test that DEFAULT_MODEL exists in MODELS."""
        # Assert
        assert DEFAULT_MODEL in MODELS
        assert DEFAULT_MODEL == "qwen-plus"

    def test_qwen_plus_supports_thinking(self):
        """Test that qwen-plus supports thinking mode."""
        # Assert
        assert MODELS["qwen-plus"].supports_thinking is True
        assert MODELS["qwen-plus"].pricing.thinking_output_multiplier == 4.0

    def test_qwen3_max_no_thinking(self):
        """Test that qwen3-max does not support thinking."""
        # Assert
        assert MODELS["qwen3-max"].supports_thinking is False


# ===== get_model_config Tests =====


class TestGetModelConfig:
    """Test get_model_config function."""

    def test_get_existing_model_config(self):
        """Test retrieving existing model configuration."""
        # Act
        config = get_model_config("qwen-plus")

        # Assert
        assert config.model_id == "qwen-plus"
        assert config.display_name == "Qwen Plus"

    def test_get_model_config_returns_correct_instance(self):
        """Test that returned config matches registry."""
        # Act
        config = get_model_config("deepseek-v3")

        # Assert
        assert config == MODELS["deepseek-v3"]

    def test_get_nonexistent_model_raises_error(self):
        """Test that nonexistent model ID raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Model 'nonexistent' not found"):
            get_model_config("nonexistent")

    def test_get_model_error_message_lists_available(self):
        """Test error message includes available models."""
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            get_model_config("invalid-model")

        error_message = str(exc_info.value)
        assert "Available models:" in error_message
        assert "qwen-plus" in error_message

    def test_get_all_known_models(self):
        """Test retrieving all known models without errors."""
        # Arrange
        known_models = ["qwen-plus", "qwen3-max", "deepseek-v3.2-exp", "deepseek-v3"]

        # Act & Assert
        for model_id in known_models:
            config = get_model_config(model_id)
            assert config.model_id == model_id


# ===== get_all_models Tests =====


class TestGetAllModels:
    """Test get_all_models function."""

    def test_get_all_models_returns_list(self):
        """Test that get_all_models returns a list."""
        # Act
        models = get_all_models()

        # Assert
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_all_models_sorted_by_order(self):
        """Test that models are sorted by display order."""
        # Act
        models = get_all_models()

        # Assert - orders should be ascending
        orders = [model.order for model in models]
        assert orders == sorted(orders)

    def test_get_all_models_returns_all_configs(self):
        """Test that all MODELS are returned."""
        # Act
        models = get_all_models()

        # Assert
        assert len(models) == len(MODELS)

    def test_get_all_models_first_is_lowest_order(self):
        """Test that first model has lowest order number."""
        # Act
        models = get_all_models()

        # Assert
        first_order = models[0].order
        for model in models:
            assert model.order >= first_order


# ===== estimate_cost Tests =====


class TestEstimateCost:
    """Test estimate_cost wrapper function."""

    def test_estimate_cost_basic(self):
        """Test basic cost estimation."""
        # Act: 1000 input, 500 output
        cost = estimate_cost(
            model_id="qwen-plus",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
            thinking_enabled=False,
        )

        # Assert - should be positive number
        assert cost > 0
        assert isinstance(cost, float)

    def test_estimate_cost_with_thinking(self):
        """Test cost estimation with thinking mode."""
        # Act
        cost_with_thinking = estimate_cost(
            model_id="qwen-plus",
            estimated_input_tokens=1000,
            estimated_output_tokens=1000,
            thinking_enabled=True,
        )
        cost_without_thinking = estimate_cost(
            model_id="qwen-plus",
            estimated_input_tokens=1000,
            estimated_output_tokens=1000,
            thinking_enabled=False,
        )

        # Assert - thinking mode should cost more
        assert cost_with_thinking > cost_without_thinking

    def test_estimate_cost_invalid_model_raises_error(self):
        """Test that invalid model ID raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Model 'invalid' not found"):
            estimate_cost(
                model_id="invalid",
                estimated_input_tokens=1000,
                estimated_output_tokens=500,
            )

    def test_estimate_cost_zero_tokens(self):
        """Test estimation with zero tokens."""
        # Act
        cost = estimate_cost(
            model_id="qwen-plus",
            estimated_input_tokens=0,
            estimated_output_tokens=0,
        )

        # Assert
        assert cost == 0.0


# ===== Integration Tests =====


class TestModelConfigIntegration:
    """Test realistic model configuration scenarios."""

    def test_typical_chat_request_cost(self):
        """Test cost for typical chat request."""
        # Arrange: Average chat - 500 input, 200 output
        config = get_model_config("qwen-plus")

        # Act
        cost = calculate_cost_in_credits(
            input_tokens=500,
            output_tokens=200,
            model_config=config,
            thinking_enabled=False,
        )

        # Assert - should be small cost
        assert 0 < cost < 5  # Reasonable range

    def test_large_context_request_cost(self):
        """Test cost for large context request."""
        # Arrange: Large context - 10000 input, 2000 output
        config = get_model_config("qwen3-max")

        # Act
        cost = calculate_cost_in_credits(
            input_tokens=10000,
            output_tokens=2000,
            model_config=config,
            thinking_enabled=False,
        )

        # Assert - should be higher cost
        assert cost > 10  # Premium model, large context

    def test_cost_comparison_between_models(self):
        """Test cost difference between budget and premium models."""
        # Arrange: Same token count
        input_tokens = 1000
        output_tokens = 1000

        # Act
        cost_qwen_plus = calculate_cost_in_credits(
            input_tokens, output_tokens, get_model_config("qwen-plus"), False
        )
        cost_qwen3_max = calculate_cost_in_credits(
            input_tokens, output_tokens, get_model_config("qwen3-max"), False
        )

        # Assert - qwen3-max (premium) should cost more
        assert cost_qwen3_max > cost_qwen_plus

    def test_credit_to_cny_rate_constant(self):
        """Test CREDIT_TO_CNY_RATE constant value."""
        # Assert - 1 credit = 0.001 CNY
        assert CREDIT_TO_CNY_RATE == 0.001
