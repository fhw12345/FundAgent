# SLS Logging Troubleshooting

Common issues with Alibaba Cloud SLS (Simple Log Service) log collection in ACK clusters.

## Issue: Application Logs Not Appearing in SLS

### Symptoms
- SLS logstore query returns empty results
- Only nginx-ingress logs visible, not application logs
- `kubectl logs` shows output but SLS doesn't

### Root Cause
AliyunLogConfig CRD not created for application pods. By default, only nginx-ingress is configured by the ACK logging component.

### Diagnosis

```bash
# Check existing log configs
KUBECONFIG=~/.kube/config-ack-prod kubectl get aliyunlogconfigs -A

# Expected: Should see your app's config
NAMESPACE     NAME                          AGE
kube-system   k8s-nginx-ingress             17d
kube-system   klinematrix-backend-stdout    1h    # Should exist
kube-system   klinematrix-frontend-stdout   1h    # Should exist
```

### Solution

1. Create AliyunLogConfig CRD for your application:

```yaml
apiVersion: log.alibabacloud.com/v1alpha1
kind: AliyunLogConfig
metadata:
  name: my-app-stdout
  namespace: kube-system  # Must be kube-system!
spec:
  logstore: my-app-logs
  logtailConfig:
    configName: my-app-stdout
    inputType: plugin
    inputDetail:
      plugin:
        inputs:
          - type: service_docker_stdout
            detail:
              IncludeK8sLabel:
                app: my-app  # Your pod label
              K8sNamespaceRegex: "^klinematrix-prod$"
              Stdout: true
              Stderr: true
```

2. Apply the config:
```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl apply -f my-log-config.yaml
```

3. Verify status shows OK:
```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl get aliyunlogconfig my-app-stdout -n kube-system -o yaml | grep -A2 status
```

### Prevention
Always create AliyunLogConfig CRDs when deploying new applications to ACK. Include log configs in your Kustomize base.

---

## Issue: Loongcollector Shows "new: 0" When Matching Containers

### Symptoms
- AliyunLogConfig status shows OK
- Loongcollector go_plugin.LOG shows: `update match list, firstStart: true, new: 0, delete: 0`
- Containers not being collected

### Root Cause
1. **Wrong loongcollector pod checked** - Loongcollector is a DaemonSet; each node has its own pod
2. **Incorrect filter** - Using `IncludeEnv` instead of `K8sNamespaceRegex`

### Diagnosis

```bash
# Step 1: Find your app's node
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n klinematrix-prod -o wide
# Output: backend-xxx  ...  cn-shanghai.172.22.192.247

# Step 2: Find loongcollector on that node
KUBECONFIG=~/.kube/config-ack-prod kubectl get pods -n kube-system -o wide | grep loong
# Match the node IP to find correct loongcollector pod

# Step 3: Check THAT pod's logs (not a random one!)
KUBECONFIG=~/.kube/config-ack-prod kubectl exec -n kube-system loongcollector-ds-<correct-suffix> -- \
  tail -50 /usr/local/ilogtail/go_plugin.LOG | grep -i "match\|klinematrix"
```

### Solution

1. **Use K8sNamespaceRegex instead of IncludeEnv**:

```yaml
# WRONG - IncludeEnv expects env var in container
detail:
  IncludeEnv:
    ALICLOUD_LOG_K8S_NAMESPACE: klinematrix-prod  # Doesn't exist in pod!

# CORRECT - K8sNamespaceRegex matches namespace
detail:
  K8sNamespaceRegex: "^klinematrix-prod$"
  IncludeK8sLabel:
    app: backend
```

2. **Re-apply the fixed config**:
```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl apply -f fixed-log-config.yaml
```

3. **Verify on the correct loongcollector pod**:
```bash
# Should now show: new: 1
kubectl exec -n kube-system loongcollector-ds-<correct-suffix> -- \
  tail -30 /usr/local/ilogtail/go_plugin.LOG | grep "new:"
```

### Prevention
- Always use `K8sNamespaceRegex` for namespace filtering (not `IncludeEnv`)
- When debugging, always find the loongcollector pod on the same node as your application

---

## Issue: How to Find SLS Project Name

### Symptoms
- Don't know which SLS project contains K8s logs
- Multiple SLS projects in account

### Solution

The SLS project is stored in a ConfigMap:

```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl get configmap alibaba-log-configuration -n kube-system -o yaml
```

Output:
```yaml
data:
  log-project: k8s-log-ca6728d48310149b9b3e987695c6ee268
  log-endpoint: cn-shanghai-intranet.log.aliyuncs.com
  log-machine-group: k8s-group-ca6728d48310149b9b3e987695c6ee268
```

---

## Issue: Logs Delayed or Missing Recent Entries

### Symptoms
- Logs appear in SLS but with delay (> 5 minutes)
- Very recent logs not showing

### Root Cause
SLS has ingestion latency. Logs are batched and sent periodically.

### Solution
1. Wait 2-5 minutes for recent logs to appear
2. Use time range that includes buffer (e.g., "last 15 minutes" instead of "last 1 minute")
3. Check loongcollector self-metrics for send errors:

```bash
KUBECONFIG=~/.kube/config-ack-prod kubectl exec -n kube-system loongcollector-ds-<pod> -- \
  tail -100 /usr/local/ilogtail/self_metrics/self_metrics.log | grep -i error
```

---

## Quick Reference

| Check | Command |
|-------|---------|
| List log configs | `kubectl get aliyunlogconfigs -A` |
| Find SLS project | `kubectl get cm alibaba-log-configuration -n kube-system -o yaml` |
| Check config status | `kubectl get aliyunlogconfig <name> -n kube-system -o yaml \| grep -A2 status` |
| Find app's node | `kubectl get pods -n <ns> -o wide` |
| Find loongcollector | `kubectl get pods -n kube-system -o wide \| grep loong` |
| Check go_plugin logs | `kubectl exec -n kube-system loongcollector-ds-<pod> -- tail -50 /usr/local/ilogtail/go_plugin.LOG` |

## See Also

- [SLS Logging Setup](../deployment/sls-logging.md) - Configuration guide
- [ACK Architecture](../deployment/ack-architecture.md) - Production cluster overview
