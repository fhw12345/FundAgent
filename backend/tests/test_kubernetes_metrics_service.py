"""
Unit tests for KubernetesMetricsService.

Tests Kubernetes metrics collection with mocked k8s API.
"""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from kubernetes.client.exceptions import ApiException

from src.services.kubernetes_metrics_service import KubernetesMetricsService


# ===== Fixtures =====


@pytest.fixture
def k8s_service():
    """Create KubernetesMetricsService with mocked k8s config"""
    with patch("src.services.kubernetes_metrics_service.config") as mock_config:
        mock_config.ConfigException = Exception
        mock_config.load_incluster_config.side_effect = Exception("Not in cluster")
        mock_config.load_kube_config.return_value = None

        with patch("src.services.kubernetes_metrics_service.client") as mock_client:
            mock_client.CoreV1Api.return_value = Mock()
            mock_client.CustomObjectsApi.return_value = Mock()

            service = KubernetesMetricsService(namespace="test-namespace")
            return service


@pytest.fixture
def unavailable_k8s_service():
    """Create KubernetesMetricsService when k8s is unavailable"""
    with patch("src.services.kubernetes_metrics_service.config") as mock_config:
        mock_config.ConfigException = Exception
        mock_config.load_incluster_config.side_effect = Exception("Not in cluster")
        mock_config.load_kube_config.side_effect = Exception("No kubeconfig")

        service = KubernetesMetricsService(namespace="test-namespace")
        return service


@pytest.fixture
def mock_pod_metrics_response():
    """Mock pod metrics from metrics-server API"""
    return {
        "items": [
            {
                "metadata": {"name": "backend-abc123"},
                "containers": [
                    {
                        "name": "backend",
                        "usage": {"cpu": "150m", "memory": "256Mi"},
                    }
                ],
            },
            {
                "metadata": {"name": "frontend-xyz789"},
                "containers": [
                    {
                        "name": "frontend",
                        "usage": {"cpu": "50m", "memory": "128Mi"},
                    }
                ],
            },
        ]
    }


@pytest.fixture
def mock_node_metrics_response():
    """Mock node metrics from metrics-server API"""
    return {
        "items": [
            {
                "metadata": {"name": "aks-userpool-12345-vmss000000"},
                "usage": {"cpu": "1500m", "memory": "4Gi"},
            },
            {
                "metadata": {"name": "aks-systemnodepool-67890-vmss000001"},
                "usage": {"cpu": "500m", "memory": "2Gi"},
            },
        ]
    }


@pytest.fixture
def mock_pods_list():
    """Mock pod list from core API"""
    pod1 = Mock()
    pod1.metadata.name = "backend-abc123"
    pod1.spec.node_name = "aks-userpool-12345-vmss000000"
    container1 = Mock()
    container1.resources = Mock()
    container1.resources.requests = {"cpu": "200m", "memory": "256Mi"}
    container1.resources.limits = {"cpu": "500m", "memory": "512Mi"}
    pod1.spec.containers = [container1]

    pod2 = Mock()
    pod2.metadata.name = "frontend-xyz789"
    pod2.spec.node_name = "aks-userpool-12345-vmss000001"
    container2 = Mock()
    container2.resources = Mock()
    container2.resources.requests = {"cpu": "100m", "memory": "128Mi"}
    container2.resources.limits = {"cpu": "200m", "memory": "256Mi"}
    pod2.spec.containers = [container2]

    pods_list = Mock()
    pods_list.items = [pod1, pod2]
    return pods_list


@pytest.fixture
def mock_nodes_list():
    """Mock node list from core API"""
    node1 = Mock()
    node1.metadata.name = "aks-userpool-12345-vmss000000"
    node1.status.capacity = {"cpu": "4", "memory": "16Gi"}

    node2 = Mock()
    node2.metadata.name = "aks-systemnodepool-67890-vmss000001"
    node2.status.capacity = {"cpu": "2", "memory": "8Gi"}

    nodes_list = Mock()
    nodes_list.items = [node1, node2]
    return nodes_list


# ===== Initialization Tests =====


class TestInitialization:
    """Test KubernetesMetricsService initialization"""

    def test_init_with_incluster_config(self):
        """Test initialization with in-cluster config"""
        with patch("src.services.kubernetes_metrics_service.config") as mock_config:
            mock_config.ConfigException = Exception
            mock_config.load_incluster_config.return_value = None

            with patch("src.services.kubernetes_metrics_service.client"):
                service = KubernetesMetricsService()

                assert service.available is True
                assert service.namespace == "default"
                mock_config.load_incluster_config.assert_called_once()

    def test_init_with_local_kubeconfig(self):
        """Test initialization with local kubeconfig"""
        with patch("src.services.kubernetes_metrics_service.config") as mock_config:
            mock_config.ConfigException = Exception
            mock_config.load_incluster_config.side_effect = Exception("Not in cluster")
            mock_config.load_kube_config.return_value = None

            with patch("src.services.kubernetes_metrics_service.client"):
                service = KubernetesMetricsService(namespace="custom-ns")

                assert service.available is True
                assert service.namespace == "custom-ns"
                mock_config.load_kube_config.assert_called_once()

    def test_init_without_kubernetes(self, unavailable_k8s_service):
        """Test initialization when Kubernetes is unavailable"""
        assert unavailable_k8s_service.available is False
        assert not hasattr(unavailable_k8s_service, "core_api")


# ===== _parse_cpu Tests =====


class TestParseCpu:
    """Test CPU parsing helper"""

    def test_parse_cpu_millicores(self, k8s_service):
        """Test parsing millicores format"""
        assert k8s_service._parse_cpu("150m") == 150
        assert k8s_service._parse_cpu("500m") == 500
        assert k8s_service._parse_cpu("1000m") == 1000

    def test_parse_cpu_cores(self, k8s_service):
        """Test parsing cores format"""
        assert k8s_service._parse_cpu("1") == 1000
        assert k8s_service._parse_cpu("2") == 2000
        assert k8s_service._parse_cpu("0.5") == 500
        assert k8s_service._parse_cpu("1.5") == 1500

    def test_parse_cpu_nanocores(self, k8s_service):
        """Test parsing nanocores format"""
        assert k8s_service._parse_cpu("1000000000n") == 1000  # 1 core
        assert k8s_service._parse_cpu("500000000n") == 500  # 0.5 core

    def test_parse_cpu_whitespace(self, k8s_service):
        """Test parsing with whitespace"""
        assert k8s_service._parse_cpu("  150m  ") == 150
        assert k8s_service._parse_cpu(" 1 ") == 1000


# ===== _parse_memory Tests =====


class TestParseMemory:
    """Test memory parsing helper"""

    def test_parse_memory_binary_units(self, k8s_service):
        """Test parsing binary units (Ki, Mi, Gi)"""
        assert k8s_service._parse_memory("1Ki") == 1024
        assert k8s_service._parse_memory("256Mi") == 256 * 1024 * 1024
        assert k8s_service._parse_memory("1Gi") == 1024 * 1024 * 1024

    def test_parse_memory_decimal_units(self, k8s_service):
        """Test parsing decimal units (k, M, G)"""
        assert k8s_service._parse_memory("1k") == 1000
        assert k8s_service._parse_memory("256M") == 256 * 1000 * 1000
        assert k8s_service._parse_memory("1G") == 1000 * 1000 * 1000

    def test_parse_memory_bytes(self, k8s_service):
        """Test parsing raw bytes"""
        assert k8s_service._parse_memory("1024") == 1024
        assert k8s_service._parse_memory("0") == 0

    def test_parse_memory_whitespace(self, k8s_service):
        """Test parsing with whitespace"""
        assert k8s_service._parse_memory("  256Mi  ") == 256 * 1024 * 1024


# ===== _format_memory Tests =====


class TestFormatMemory:
    """Test memory formatting helper"""

    def test_format_memory_gigabytes(self, k8s_service):
        """Test formatting gigabytes"""
        assert k8s_service._format_memory(1024 * 1024 * 1024) == "1.0Gi"
        assert k8s_service._format_memory(2 * 1024 * 1024 * 1024) == "2.0Gi"

    def test_format_memory_megabytes(self, k8s_service):
        """Test formatting megabytes"""
        assert k8s_service._format_memory(256 * 1024 * 1024) == "256Mi"
        assert k8s_service._format_memory(512 * 1024 * 1024) == "512Mi"

    def test_format_memory_kilobytes(self, k8s_service):
        """Test formatting kilobytes"""
        assert k8s_service._format_memory(512 * 1024) == "512Ki"
        assert k8s_service._format_memory(1024) == "1Ki"

    def test_format_memory_bytes(self, k8s_service):
        """Test formatting bytes"""
        assert k8s_service._format_memory(512) == "512B"
        assert k8s_service._format_memory(0) == "0B"


# ===== get_pod_metrics Tests =====


class TestGetPodMetrics:
    """Test get_pod_metrics method"""

    @pytest.mark.asyncio
    async def test_get_pod_metrics_unavailable(self, unavailable_k8s_service):
        """Test pod metrics when k8s is unavailable"""
        result = await unavailable_k8s_service.get_pod_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pod_metrics_success(
        self, k8s_service, mock_pod_metrics_response, mock_pods_list
    ):
        """Test successful pod metrics retrieval"""
        k8s_service.custom_api.list_namespaced_custom_object.return_value = (
            mock_pod_metrics_response
        )
        k8s_service.core_api.list_namespaced_pod.return_value = mock_pods_list

        result = await k8s_service.get_pod_metrics()

        assert result is not None
        assert len(result) == 2
        assert result[0].name == "backend-abc123"
        assert result[0].cpu_usage == "150m"
        assert result[0].node_pool == "userpool"

    @pytest.mark.asyncio
    async def test_get_pod_metrics_empty_containers(
        self, k8s_service, mock_pods_list
    ):
        """Test pod metrics with empty containers"""
        k8s_service.custom_api.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "empty-pod"},
                    "containers": [],  # No containers
                }
            ]
        }
        k8s_service.core_api.list_namespaced_pod.return_value = mock_pods_list

        result = await k8s_service.get_pod_metrics()

        assert result is not None
        assert len(result) == 0  # Empty pod skipped

    @pytest.mark.asyncio
    async def test_get_pod_metrics_api_exception(self, k8s_service):
        """Test pod metrics with API exception"""
        k8s_service.custom_api.list_namespaced_custom_object.side_effect = (
            ApiException(status=403, reason="Forbidden")
        )

        result = await k8s_service.get_pod_metrics()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_pod_metrics_generic_exception(self, k8s_service):
        """Test pod metrics with generic exception"""
        k8s_service.custom_api.list_namespaced_custom_object.side_effect = Exception(
            "Connection error"
        )

        result = await k8s_service.get_pod_metrics()

        assert result is None


# ===== get_node_metrics Tests =====


class TestGetNodeMetrics:
    """Test get_node_metrics method"""

    @pytest.mark.asyncio
    async def test_get_node_metrics_unavailable(self, unavailable_k8s_service):
        """Test node metrics when k8s is unavailable"""
        result = await unavailable_k8s_service.get_node_metrics()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_metrics_success(
        self, k8s_service, mock_node_metrics_response, mock_nodes_list
    ):
        """Test successful node metrics retrieval"""
        k8s_service.custom_api.list_cluster_custom_object.return_value = (
            mock_node_metrics_response
        )
        k8s_service.core_api.list_node.return_value = mock_nodes_list

        result = await k8s_service.get_node_metrics()

        assert result is not None
        assert len(result) == 2
        assert result[0].name == "aks-userpool-12345-vmss000000"
        assert result[0].cpu_usage == "1500m"
        assert "Gi" in result[0].memory_usage

    @pytest.mark.asyncio
    async def test_get_node_metrics_api_exception(self, k8s_service):
        """Test node metrics with API exception"""
        k8s_service.custom_api.list_cluster_custom_object.side_effect = (
            ApiException(status=500, reason="Internal Server Error")
        )

        result = await k8s_service.get_node_metrics()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_metrics_generic_exception(self, k8s_service):
        """Test node metrics with generic exception"""
        k8s_service.custom_api.list_cluster_custom_object.side_effect = Exception(
            "Timeout"
        )

        result = await k8s_service.get_node_metrics()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_metrics_empty_items(self, k8s_service, mock_nodes_list):
        """Test node metrics with empty items"""
        k8s_service.custom_api.list_cluster_custom_object.return_value = {"items": []}
        k8s_service.core_api.list_node.return_value = mock_nodes_list

        result = await k8s_service.get_node_metrics()

        assert result is not None
        assert len(result) == 0


# ===== Integration Tests =====


class TestEdgeCases:
    """Test edge cases and integration scenarios"""

    @pytest.mark.asyncio
    async def test_pod_without_resource_limits(
        self, k8s_service, mock_pod_metrics_response
    ):
        """Test pod metrics when pod has no resource limits"""
        # Create pod without resource limits
        pod = Mock()
        pod.metadata.name = "backend-abc123"
        pod.spec.node_name = "node-1"
        container = Mock()
        container.resources = None
        pod.spec.containers = [container]

        pods_list = Mock()
        pods_list.items = [pod]

        k8s_service.custom_api.list_namespaced_custom_object.return_value = (
            mock_pod_metrics_response
        )
        k8s_service.core_api.list_namespaced_pod.return_value = pods_list

        result = await k8s_service.get_pod_metrics()

        assert result is not None
        # Should use default limits

    @pytest.mark.asyncio
    async def test_node_without_capacity_info(
        self, k8s_service, mock_node_metrics_response
    ):
        """Test node metrics when node has no capacity info"""
        node = Mock()
        node.metadata.name = "aks-userpool-12345-vmss000000"
        node.status.capacity = None  # No capacity info

        nodes_list = Mock()
        nodes_list.items = [node]

        k8s_service.custom_api.list_cluster_custom_object.return_value = (
            mock_node_metrics_response
        )
        k8s_service.core_api.list_node.return_value = nodes_list

        result = await k8s_service.get_node_metrics()

        assert result is not None
        # Should use default capacity

    def test_parse_cpu_zero(self, k8s_service):
        """Test parsing zero CPU"""
        assert k8s_service._parse_cpu("0") == 0
        assert k8s_service._parse_cpu("0m") == 0

    def test_format_memory_large_values(self, k8s_service):
        """Test formatting very large memory values"""
        # 100Gi
        large_value = 100 * 1024 * 1024 * 1024
        result = k8s_service._format_memory(large_value)
        assert "Gi" in result
