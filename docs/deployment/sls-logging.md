# Alibaba Cloud SLS Logging Setup

Configure application log collection for ACK (Alibaba Container Service for Kubernetes) clusters using SLS (Simple Log Service).

## Overview

The ACK cluster uses **Loongcollector** (formerly Logtail) DaemonSet to collect container logs and send them to SLS. By default, only system components like nginx-ingress are configured. Application pods require explicit `AliyunLogConfig` CRD configuration.

## SLS Project Details

| Setting | Value |
|---------|-------|
| **Project** | `k8s-log-ca6728d48310149b9b3e987695c6ee268` |
| **Region** | cn-shanghai |
| **Endpoint** | `cn-shanghai-intranet.log.aliyuncs.com` |
| **Machine Group** | `k8s-group-ca6728d48310149b9b3e987695c6ee268` |

**Console URL**: https://sls.console.aliyun.com/lognext/project/k8s-log-ca6728d48310149b9b3e987695c6ee268/logsearch

## Configured Logstores

| Logstore | Source | Description |
|----------|--------|-------------|
| `nginx-ingress` | nginx-ingress-controller | Ingress access logs (auto-configured) |
| `klinematrix-backend` | app=backend pods | Backend API logs |
| `klinematrix-frontend` | app=frontend pods | Frontend container logs |

## Creating AliyunLogConfig for Applications

### Config Files Location

```
.pipeline/k8s/base/logging/
├── kustomization.yaml
├── backend-log-config.yaml
└── frontend-log-config.yaml
```

### Example: Backend Log Config

```yaml
apiVersion: log.alibabacloud.com/v1alpha1
kind: AliyunLogConfig
metadata:
  name: klinematrix-backend-stdout
  namespace: kube-system  # Must be kube-system
spec:
  logstore: klinematrix-backend
  logtailConfig:
    configName: klinematrix-backend-stdout
    inputType: plugin
    inputDetail:
      plugin:
        inputs:
          - type: service_docker_stdout
            detail:
              IncludeK8sLabel:
                app: backend  # Match pods with app=backend label
              K8sNamespaceRegex: "^klinematrix-prod$"  # Match namespace
              Stdout: true
              Stderr: true
        processors:
          - type: processor_default
            detail:
              KeepSource: true
```

### Key Configuration Notes

1. **Namespace**: AliyunLogConfig CRDs must be created in `kube-system` namespace
2. **K8sNamespaceRegex**: Use this instead of `IncludeEnv` for namespace filtering
3. **IncludeK8sLabel**: Match pods by Kubernetes labels
4. **Status Check**: After applying, verify `status.statusCode: 200` in the CRD

### Apply Configuration

```bash
# Apply log configs
KUBECONFIG=~/.kube/config-ack-prod kubectl apply -f .pipeline/k8s/base/logging/

# Verify status
KUBECONFIG=~/.kube/config-ack-prod kubectl get aliyunlogconfigs -A
```

## Verification

### 1. Check AliyunLogConfig Status

```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl get aliyunlogconfig klinematrix-backend-stdout -n kube-system -o yaml
```

Look for:
```yaml
status:
  status: OK
  statusCode: 200
```

### 2. Find the Correct Loongcollector Pod

Loongcollector runs as a DaemonSet - check the pod on the **same node** as your application:

```bash
# Find which node your app is on
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n klinematrix-prod -o wide

# Find loongcollector on that node
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n kube-system -o wide | grep loong
```

### 3. Verify Container Matching

```bash
# Check go_plugin.LOG on the correct loongcollector pod
KUBECONFIG=~/.kube/config-ack-prod kubectl exec -n kube-system loongcollector-ds-<pod-suffix> -- \
  tail -50 /usr/local/ilogtail/go_plugin.LOG | grep klinematrix
```

Look for:
```
update match list, firstStart: true, new: 1, delete: 0
docker stdout:added source host path:/var/log/pods/klinematrix-prod_backend-...
```

### 4. Search Logs in SLS Console

1. Go to SLS Console → Project → Logstore
2. Select time range (last 15 minutes for recent logs)
3. Query examples:
   ```sql
   -- All backend logs
   *

   -- Error logs only
   * and level: ERROR

   -- Search for specific API
   * and "/api/portfolio"
   ```

## Common Issues

See [Troubleshooting: SLS Logging Issues](../troubleshooting/sls-logging-issues.md)

## References

- [Alibaba Cloud SLS Documentation](https://www.alibabacloud.com/help/en/sls/)
- [AliyunLogConfig CRD Reference](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-aliyunlogconfig-to-collect-container-logs)
