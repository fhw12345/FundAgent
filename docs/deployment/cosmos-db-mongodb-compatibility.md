# Cosmos DB MongoDB API Compatibility Guide

## Overview

Azure Cosmos DB for MongoDB API has stricter indexing requirements than regular MongoDB. This document captures the specific limitations and how we handle them in the codebase.

## Key Limitations

### 1. Sorting with Compound Filters

**Problem**: Cosmos DB MongoDB API **does NOT support sorting by `_id`** when you have compound filter queries, even with compound indexes.

**Example of what FAILS**:
```python
# This works in MongoDB but FAILS in Cosmos DB
collection.find({"user_id": "123", "is_archived": False}).sort("_id", -1)

# Error: "The index path corresponding to the specified order-by item is excluded"
```

**Solution**: Use explicit timestamp fields (`created_at`, `updated_at`, `timestamp`) for sorting instead of `_id`.

```python
# This works in both MongoDB and Cosmos DB
collection.find({"user_id": "123", "is_archived": False}).sort("updated_at", -1)
```

### 2. Required Indexes

For Cosmos DB MongoDB API, you MUST create compound indexes that include:
1. All filter fields
2. The sort field (as the last field in the index)

**Example**:
```bash
# For query: find({"user_id": "...", "is_archived": False}).sort("updated_at", -1)
# Required index:
az cosmosdb mongodb collection update \
  --account-name financialagent-mongodb \
  --database-name klinematrix_test \
  --name chats \
  --resource-group FinancialAgent \
  --idx '[
    {"key": {"keys": ["_id"]}},
    {"key": {"keys": ["user_id", "is_archived", "updated_at"]}}
  ]'
```

## Codebase Implementations

### Chats Collection (`chat_repository.py`)

**Query Pattern**:
```python
# Filter by user_id and is_archived, sort by updated_at
query = {"user_id": user_id, "is_archived": False}
cursor = collection.find(query).sort("updated_at", -1)
```

**Required Index**: `["user_id", "is_archived", "updated_at"]`

**Status**: ✅ Implemented (as of v0.5.5)

### Messages Collection (`message_repository.py`)

**Query Pattern**:
```python
# Filter by chat_id, sort by timestamp
cursor = collection.find({"chat_id": chat_id}).sort("timestamp", 1)
```

**Required Index**: `["chat_id", "timestamp"]`

**Status**: ✅ Already compatible (never used `_id` for sorting)

## Migration from MongoDB to Cosmos DB

If migrating from regular MongoDB to Cosmos DB MongoDB API:

1. **Audit all queries** that use `.sort("_id", ...)` with filters
2. **Replace** `_id` sorting with explicit timestamp fields
3. **Create compound indexes** for all filtered + sorted queries
4. **Test thoroughly** - Cosmos DB errors appear at runtime, not at schema definition time

## Why This Matters

- **Local Dev**: Uses regular MongoDB (works with `_id` sorting)
- **Test/Prod**: Uses Cosmos DB MongoDB API (requires timestamp sorting)

**Without this fix**, queries that work locally will **fail in production** with cryptic indexing errors.

## References

- [Cosmos DB MongoDB API Limitations](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/feature-support-42)
- Fixed Issue: Backend v0.5.5 - Changed chat list query from `_id` to `updated_at` sorting
