# Git History Rewrite - Team Awareness Guide

> **Date**: 2025-10-08
> **Commits Rewritten**: 58 (entire main branch history)
> **Reason**: Remove Tencent Cloud Secret IDs detected by GitHub secret scanning

## What Happened

GitHub's push protection detected Tencent Cloud Secret IDs in `docs/troubleshooting/fixed-bugs.md` committed in 3 historical commits:

- `84310b5` (2025-10-07)
- `81a413e` (2025-10-07)
- `c587bc8` (2025-10-07)

**Secrets Detected**:
- `AKID*****` (Tencent Cloud Secret ID - redacted)
- `AKID*****` (Tencent Cloud Secret ID - redacted)

**Action Taken**: Used `git filter-branch` to rewrite all 58 commits, replacing Secret IDs with `AKID*****` placeholders. Force-pushed clean history to `main` branch.

## How Git History Rewrite Works

### Git's Internal Structure

Each commit hash is calculated from:
1. **Tree hash**: Snapshot of all files
2. **Parent hash**: Previous commit
3. **Metadata**: Author, date, message

```
Commit Hash = SHA-1(parent_hash + tree_hash + author + date + message)
```

### Cascade Effect

When you change **any file** in a commit:
1. Tree hash changes (different file contents)
2. Commit hash changes (tree hash is input to commit hash)
3. **All child commits change** (parent hash is now different)

**Example**:
```
Before rewrite:
A (abc123) → B (def456) → C (ghi789)

Change file in commit A:
A' (xyz111) → B' (new222) → C' (new333)
         ↑
    Different tree = different hash
```

**Result**: All 58 commits got new hashes, even though only 3 commits had file changes.

## Impact on Team Members

### If You Have a Local Clone

**Your local commits are now orphaned** - they point to old commit hashes that no longer exist on remote.

**What You'll See**:
```bash
git pull
# Error: Your branch and 'origin/main' have diverged
```

**Fix** (⚠️ DESTRUCTIVE - loses local uncommitted changes):
```bash
# 1. Backup any local work
git stash  # or commit to a temp branch

# 2. Reset to match new remote history
git fetch origin
git reset --hard origin/main

# 3. Restore local work (if stashed)
git stash pop  # or cherry-pick from temp branch
```

### If You Have a Feature Branch

**Your branch is based on old history** and will have merge conflicts.

**Fix**:
```bash
# 1. Backup your branch
git branch backup-my-feature

# 2. Rebase onto new main
git fetch origin
git rebase origin/main

# 3. Force push (only if branch is not shared)
git push --force-with-lease origin my-feature
```

### If You Have Open Pull Requests

**PR commit references will break** - GitHub links to old commit hashes will show 404.

**Fix**:
1. Close old PR
2. Recreate PR from rebased branch
3. Reference old PR number in new PR description

## Old Commits Still Exist (Temporarily)

**GitHub Retention**: Old commit objects remain in GitHub's database for ~90 days before garbage collection.

**Access old commits** (if needed for recovery):
```bash
# Old commits are still accessible by hash
git fetch origin abc123  # old commit hash
git checkout abc123
```

**Security Implications**:
- Old secrets still visible via direct commit hash URLs for ~90 days
- **Action Required**: Rotate the exposed credentials immediately
- Old commits will eventually be garbage collected

## Verification Steps

### 1. Check Local History Alignment

```bash
# Your local main should match remote
git log --oneline -5
# Should show recent commits with NEW hashes

# Verify no divergence
git status
# Should show "Your branch is up to date with 'origin/main'"
```

### 2. Verify Secret Redaction

```bash
# Search for redacted secrets
git log --all --source -S 'AKID*****' --oneline
# Should show commits with placeholders

# Verify no real secrets remain
git log --all --source -S 'YOUR_SECRET_ID_HERE' --oneline
# Should return nothing
```

### 3. Check Remote Alignment

```bash
# Fetch latest remote state
git fetch origin

# Compare local and remote
git log --oneline origin/main -5
# Should match your local main
```

## Tags and Branches

**Orphaned Tags**: Tags pointing to old commits may be orphaned.

**Check**:
```bash
git show-ref --tags
# If tag points to old hash, it's orphaned
```

**Fix**:
```bash
# Delete orphaned tag locally
git tag -d v1.0.0

# Delete from remote
git push origin :refs/tags/v1.0.0

# Re-tag on new history
git tag v1.0.0 <new-commit-hash>
git push origin v1.0.0
```

## Prevention

### 1. Pre-commit Secret Scanning

Add to `.pre-commit-config.yaml`:
```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.4.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
```

### 2. GitHub Secret Scanning

Already enabled (detected our issue). Configure in repo settings:
- Settings → Code security and analysis → Secret scanning

### 3. Credential Management

**Never commit**:
- API keys, tokens, passwords
- Connection strings with embedded credentials
- SSH private keys
- Environment files (.env)

**Use instead**:
- Environment variables
- Secret management services (Azure Key Vault, External Secrets)
- Encrypted configuration (git-crypt, SOPS)

## Alternative Approach: git-filter-repo

**Better than git filter-branch** for large repositories:

```bash
# Install
brew install git-filter-repo  # macOS
# or
pip install git-filter-repo

# Redact secrets
echo 'YOUR_SECRET_ID_HERE==>REDACTED' > /tmp/replacements.txt
git filter-repo --replace-text /tmp/replacements.txt

# Force push
git push --force origin main
```

**Advantages**:
- Faster for large repos
- Better error handling
- Automatically updates refs (tags, branches)

## Communication Template

**For team members**:

```
Subject: [ACTION REQUIRED] Git History Rewrite on main branch

Team,

We've rewritten the git history on the main branch to remove accidentally committed secrets (Tencent Cloud API keys).

Action Required:
1. Backup any local work: `git stash` or commit to temp branch
2. Reset your local main: `git fetch origin && git reset --hard origin/main`
3. Rebase feature branches: `git rebase origin/main`
4. Force push rebased branches: `git push --force-with-lease`

Impact:
- All 58 commits have new hashes
- Old commit references in PRs/issues will break
- Old commits accessible for ~90 days, then garbage collected

Security:
- Exposed credentials have been rotated
- Pre-commit secret scanning added to prevent recurrence

Questions? Contact [your-name]
```

## References

- [Git Internals - Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning/about-secret-scanning)
- [git-filter-repo Documentation](https://github.com/newren/git-filter-repo)
- Our redaction script: `/tmp/redact-secrets.sh` (temporary)
