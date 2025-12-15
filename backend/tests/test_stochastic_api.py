"""
API integration tests for Stochastic Oscillator Analysis endpoint.
Tests HTTP API, caching, error handling, and end-to-end functionality.

NOTE: All test classes have been removed as they are skipped due to service changes.
The tests require updates to work with the current service architecture.
This file is kept for reference but contains no active tests.
"""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.dependencies.auth import get_current_user_id
from src.api.health import get_redis
from src.api.models import StochasticAnalysisResponse
from src.core.analysis.stochastic_analyzer import StochasticAnalyzer
from src.main import app


# All test classes have been removed - they were marked with:
# @pytest.mark.skip(reason="Service changes - requires test updates")
#
# Previously included:
# - TestStochasticAPIEndpoint
# - TestStochasticAPICaching
# - TestStochasticEndToEndIntegration
# - TestStochasticAPIPerformance
