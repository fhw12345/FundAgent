# Kubernetes Security Hardening

> **Version**: Implemented in backend v0.4.5, frontend v0.6.1
> **Date**: 2025-10-08

## Overview

All Kubernetes deployments now enforce comprehensive security contexts following least-privilege principles:

- **Non-root execution**: All containers run as non-root users
- **Read-only filesystems**: Root filesystems are read-only with explicit writable mounts
- **Dropped capabilities**: All Linux capabilities dropped (capabilities.drop: ALL)
- **No privilege escalation**: allowPrivilegeEscalation: false

## Security Contexts by Service

### Backend (Python FastAPI)

**User/Group**: 1000/1000

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
  containers:
  - name: backend
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 1000
      capabilities:
        drop:
          - ALL
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: cache
      mountPath: /app/.cache
    - name: home-cache
      mountPath: /home/app/.cache
  volumes:
  - name: tmp
    emptyDir: {}
  - name: cache
    emptyDir: {}
  - name: home-cache
    emptyDir: {}
```

**Writable Mounts**:
- `/tmp` - Temporary file operations
- `/app/.cache` - Application cache
- `/home/app/.cache` - User-level cache (pip, etc.)

### Frontend (Nginx)

**User/Group**: 101/101 (nginx user)

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 101  # nginx user
    fsGroup: 101
  containers:
  - name: frontend
    ports:
    - containerPort: 8080  # Non-privileged port
      name: http
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 101
      capabilities:
        drop:
          - ALL
    volumeMounts:
    - name: tmp
      mountPath: /tmp
    - name: var-cache
      mountPath: /var/cache/nginx
    - name: var-run
      mountPath: /var/run
  volumes:
  - name: tmp
    emptyDir: {}
  - name: var-cache
    emptyDir: {}
  - name: var-run
    emptyDir: {}
```

**Writable Mounts**:
- `/tmp` - Temporary files
- `/var/cache/nginx` - Nginx cache directory
- `/var/run` - Runtime files (PID, sockets)

**Port Change**: Nginx listens on port 8080 (non-privileged) instead of 80. Service still exposes port 80 externally.

### Redis

**User/Group**: 999/999 (redis user)

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 999  # redis user
    fsGroup: 999
  containers:
  - name: redis
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      runAsNonRoot: true
      runAsUser: 999
      capabilities:
        drop:
          - ALL
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    emptyDir: {}
```

**Writable Mounts**:
- `/data` - Redis persistence and runtime files

## Validation

### Pre-commit Hooks

Kubernetes manifests are validated on every commit:

```yaml
# .pre-commit-config.yaml
- id: kube-linter
  entry: bash -c 'kubectl kustomize .pipeline/k8s/base > /tmp/k8s-manifests.yaml && docker run --rm -v "/tmp:/tmp" stackrox/kube-linter:latest lint /tmp/k8s-manifests.yaml'

- id: kubeconform
  entry: bash -c 'kubectl kustomize .pipeline/k8s/base > /tmp/k8s-manifests.yaml && docker run --rm -v "/tmp:/tmp" ghcr.io/yannh/kubeconform:latest -strict -summary -skip ClusterIssuer /tmp/k8s-manifests.yaml'
```

### Runtime Verification

```bash
# Check pod security contexts
kubectl get pods -n klinematrix-test -o json | jq '.items[].spec.securityContext'

# Verify container security contexts
kubectl get pods -n klinematrix-test -o json | jq '.items[].spec.containers[].securityContext'

# Check all pods are running
kubectl get pods -n klinematrix-test
```

Expected output: All pods `1/1 Running` with no restarts.

## Impact and Benefits

### Security Improvements

1. **Attack Surface Reduction**: Read-only root filesystems prevent malicious code from persisting
2. **Privilege Isolation**: Non-root execution limits impact of container breakout
3. **Capability Minimization**: Dropped capabilities prevent system-level exploits
4. **Compliance**: Meets CIS Kubernetes Benchmark requirements

### Operational Considerations

- **Volume Mounts**: EmptyDir volumes are ephemeral - data lost on pod restart
- **File Permissions**: New files inherit fsGroup ownership automatically
- **Port Binding**: Non-root users cannot bind to privileged ports (<1024)
- **Debugging**: Read-only filesystem prevents installing debug tools at runtime

## Troubleshooting

### Pod Fails to Start

**Symptom**: CrashLoopBackOff or permission denied errors

**Check**:
```bash
kubectl logs -n klinematrix-test <pod-name>
kubectl describe pod -n klinematrix-test <pod-name>
```

**Common Issues**:
- Missing writable volume mount for required path
- Incorrect user/group ID
- Application trying to write to read-only path

**Fix**: Add emptyDir volume mount for the required writable path

### Frontend 403 Forbidden

**Symptom**: Nginx returns 403 errors

**Root Cause**: Nginx user (101) cannot read static files

**Fix**: Ensure `fsGroup: 101` in pod security context (already configured)

### Performance Degradation

**Symptom**: Slower response times after security hardening

**Root Cause**: EmptyDir volumes use node's disk instead of tmpfs

**Fix** (if needed): Configure emptyDir with memory medium:
```yaml
volumes:
- name: tmp
  emptyDir:
    medium: Memory
    sizeLimit: 100Mi
```

## References

- [Kubernetes Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [kube-linter Documentation](https://docs.kubelinter.io/)
- Backend CHANGELOG: [v0.4.5](../project/versions/backend/CHANGELOG.md)
- Frontend CHANGELOG: [v0.6.1](../project/versions/frontend/CHANGELOG.md)
