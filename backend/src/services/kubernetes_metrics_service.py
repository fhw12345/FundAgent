"""
Kubernetes metrics collection service.
"""

import structlog
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from ..api.schemas.admin_models import NodeMetrics, PodMetrics

logger = structlog.get_logger()


class KubernetesMetricsService:
    """Service for collecting Kubernetes pod and node metrics."""

    def __init__(self, namespace: str = "klinematrix-test") -> None:
        """
        Initialize Kubernetes metrics service.

        Args:
            namespace: Kubernetes namespace to query (default: klinematrix-test)
        """
        self.namespace = namespace
        self.available = False

        try:
            # Try in-cluster config first (production)
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
            self.available = True
        except config.ConfigException:
            try:
                # Fall back to local kubeconfig (development)
                config.load_kube_config()
                logger.info("Loaded local kubeconfig")
                self.available = True
            except Exception as e:
                logger.warning(
                    "Kubernetes config not available", error=str(e), available=False
                )
                self.available = False

        if self.available:
            self.core_api = client.CoreV1Api()
            self.custom_api = client.CustomObjectsApi()

    async def get_pod_metrics(self) -> list[PodMetrics] | None:
        """
        Get resource metrics for all pods in the namespace.

        Returns:
            List of PodMetrics objects, or None if metrics unavailable
        """
        if not self.available:
            return None

        try:
            # Get pod metrics from metrics-server API
            metrics = self.custom_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=self.namespace,
                plural="pods",
            )

            pod_metrics = []
            for item in metrics.get("items", []):
                pod_name = item["metadata"]["name"]
                containers = item.get("containers", [])

                if not containers:
                    continue

                # Aggregate metrics across all containers in the pod
                total_cpu = 0
                total_memory = 0

                for container in containers:
                    cpu_str = container["usage"].get("cpu", "0")
                    memory_str = container["usage"].get("memory", "0")

                    # Parse CPU (e.g., "150m" -> 150 millicores)
                    cpu_millicores = self._parse_cpu(cpu_str)
                    total_cpu += cpu_millicores

                    # Parse memory (e.g., "256Mi" -> bytes)
                    memory_bytes = self._parse_memory(memory_str)
                    total_memory += memory_bytes

                # Get pod resource requests/limits and node info
                pods = self.core_api.list_namespaced_pod(namespace=self.namespace)
                cpu_limit = 1000  # Default 1 CPU core = 1000m
                memory_limit = 512 * 1024 * 1024  # Default 512Mi
                node_name = None
                node_pool = None
                cpu_request_str = None
                cpu_limit_str = None
                memory_request_str = None
                memory_limit_str = None

                for pod in pods.items:
                    if pod.metadata.name == pod_name:
                        # Get node information
                        node_name = pod.spec.node_name
                        if node_name and node_name.startswith("aks-"):
                            # Extract node pool from pattern: aks-<poolname>-<id>-vmss<instance>
                            parts = node_name.split("-")
                            if len(parts) >= 2:
                                node_pool = parts[1]

                        # Aggregate resource requests/limits across all containers
                        cpu_request_total = 0
                        cpu_limit_total = 0
                        memory_request_total = 0
                        memory_limit_total = 0

                        for container in pod.spec.containers:
                            if container.resources:
                                if container.resources.requests:
                                    if "cpu" in container.resources.requests:
                                        cpu_request_total += self._parse_cpu(
                                            container.resources.requests["cpu"]
                                        )
                                    if "memory" in container.resources.requests:
                                        memory_request_total += self._parse_memory(
                                            container.resources.requests["memory"]
                                        )

                                if container.resources.limits:
                                    if "cpu" in container.resources.limits:
                                        cpu_limit_total += self._parse_cpu(
                                            container.resources.limits["cpu"]
                                        )
                                    if "memory" in container.resources.limits:
                                        memory_limit_total += self._parse_memory(
                                            container.resources.limits["memory"]
                                        )

                        # Format resource strings for display
                        if cpu_request_total > 0:
                            cpu_request_str = f"{cpu_request_total}m" if cpu_request_total < 1000 else f"{cpu_request_total / 1000:.1f}"
                        if cpu_limit_total > 0:
                            cpu_limit_str = f"{cpu_limit_total}m" if cpu_limit_total < 1000 else f"{cpu_limit_total / 1000:.1f}"
                            cpu_limit = cpu_limit_total
                        if memory_request_total > 0:
                            memory_request_str = self._format_memory(memory_request_total)
                        if memory_limit_total > 0:
                            memory_limit_str = self._format_memory(memory_limit_total)
                            memory_limit = memory_limit_total

                cpu_percentage = int((total_cpu / cpu_limit) * 100) if cpu_limit else 0
                memory_percentage = (
                    int((total_memory / memory_limit) * 100) if memory_limit else 0
                )

                pod_metrics.append(
                    PodMetrics(
                        name=pod_name,
                        cpu_usage=f"{total_cpu}m",
                        memory_usage=self._format_memory(total_memory),
                        cpu_percentage=cpu_percentage,
                        memory_percentage=memory_percentage,
                        node_name=node_name,
                        node_pool=node_pool,
                        cpu_request=cpu_request_str,
                        cpu_limit=cpu_limit_str,
                        memory_request=memory_request_str,
                        memory_limit=memory_limit_str,
                    )
                )

            logger.info("Collected pod metrics", pod_count=len(pod_metrics))
            return pod_metrics

        except ApiException as e:
            logger.error(
                "Failed to get pod metrics",
                error=str(e),
                status=e.status,
                reason=e.reason,
            )
            return None
        except Exception as e:
            logger.error("Unexpected error getting pod metrics", error=str(e))
            return None

    async def get_node_metrics(self) -> list[NodeMetrics] | None:
        """
        Get resource metrics for all nodes in the cluster.

        Returns:
            List of NodeMetrics objects, or None if metrics unavailable
        """
        if not self.available:
            return None

        try:
            # Get node metrics from metrics-server API
            metrics = self.custom_api.list_cluster_custom_object(
                group="metrics.k8s.io", version="v1beta1", plural="nodes"
            )

            # Get node capacity information
            nodes = self.core_api.list_node()

            node_metrics = []
            for item in metrics.get("items", []):
                node_name = item["metadata"]["name"]
                cpu_str = item["usage"].get("cpu", "0")
                memory_str = item["usage"].get("memory", "0")

                cpu_usage = self._parse_cpu(cpu_str)
                memory_usage = self._parse_memory(memory_str)

                # Find matching node for capacity info
                cpu_capacity = 4000  # Default 4 cores
                memory_capacity = 8 * 1024 * 1024 * 1024  # Default 8Gi

                for node in nodes.items:
                    if node.metadata.name == node_name:
                        if node.status.capacity:
                            if "cpu" in node.status.capacity:
                                cpu_capacity = self._parse_cpu(
                                    node.status.capacity["cpu"]
                                )
                            if "memory" in node.status.capacity:
                                memory_capacity = self._parse_memory(
                                    node.status.capacity["memory"]
                                )

                cpu_percentage = int((cpu_usage / cpu_capacity) * 100)
                memory_percentage = int((memory_usage / memory_capacity) * 100)

                node_metrics.append(
                    NodeMetrics(
                        name=node_name,
                        cpu_usage=f"{cpu_usage}m",
                        memory_usage=self._format_memory(memory_usage),
                        cpu_capacity=f"{cpu_capacity}m",
                        memory_capacity=self._format_memory(memory_capacity),
                        cpu_percentage=cpu_percentage,
                        memory_percentage=memory_percentage,
                    )
                )

            logger.info("Collected node metrics", node_count=len(node_metrics))
            return node_metrics

        except ApiException as e:
            logger.error(
                "Failed to get node metrics",
                error=str(e),
                status=e.status,
                reason=e.reason,
            )
            return None
        except Exception as e:
            logger.error("Unexpected error getting node metrics", error=str(e))
            return None

    def _parse_cpu(self, cpu_str: str) -> int:
        """
        Parse CPU string to millicores.

        Examples:
            "150m" -> 150
            "1" -> 1000
            "1.5" -> 1500
        """
        cpu_str = cpu_str.strip()
        if cpu_str.endswith("m"):
            return int(cpu_str[:-1])
        elif cpu_str.endswith("n"):
            # Nanocores to millicores
            return int(cpu_str[:-1]) // 1_000_000
        else:
            # Cores to millicores
            return int(float(cpu_str) * 1000)

    def _parse_memory(self, memory_str: str) -> int:
        """
        Parse memory string to bytes.

        Examples:
            "256Mi" -> 268435456
            "1Gi" -> 1073741824
            "512Ki" -> 524288
        """
        memory_str = memory_str.strip()

        # Binary units (Ki, Mi, Gi)
        if memory_str.endswith("Ki"):
            return int(memory_str[:-2]) * 1024
        elif memory_str.endswith("Mi"):
            return int(memory_str[:-2]) * 1024 * 1024
        elif memory_str.endswith("Gi"):
            return int(memory_str[:-2]) * 1024 * 1024 * 1024

        # Decimal units (k, M, G)
        elif memory_str.endswith("k"):
            return int(memory_str[:-1]) * 1000
        elif memory_str.endswith("M"):
            return int(memory_str[:-1]) * 1000 * 1000
        elif memory_str.endswith("G"):
            return int(memory_str[:-1]) * 1000 * 1000 * 1000

        # Bytes
        else:
            return int(memory_str)

    def _format_memory(self, bytes_val: int) -> str:
        """
        Format bytes to human-readable string.

        Examples:
            268435456 -> "256Mi"
            1073741824 -> "1.0Gi"
        """
        if bytes_val >= 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024 * 1024):.1f}Gi"
        elif bytes_val >= 1024 * 1024:
            return f"{bytes_val // (1024 * 1024)}Mi"
        elif bytes_val >= 1024:
            return f"{bytes_val // 1024}Ki"
        else:
            return f"{bytes_val}B"
