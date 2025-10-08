# MongoDB Cosmos DB Troubleshooting

> **Platform**: Azure Cosmos DB for MongoDB (v4.2 API)
> **Last Updated**: 2025-10-08

## Overview

Azure Cosmos DB for MongoDB has specific limitations and behaviors that differ from native MongoDB. This guide covers common issues and their solutions.

## Database Throughput vs Collection Throughput

### Issue: Cannot Create Collection-Level Indexes

**Symptom**: Index creation fails with error about throughput requirements

**Root Cause**: Cosmos DB has two throughput modes:

1. **Shared Database Throughput** (our configuration):
   - RU/s allocated at database level
   - Shared across all collections
   - **Cannot create unique indexes on collections**
   - Lower cost for multiple small collections

2. **Collection-Level Throughput**:
   - RU/s allocated per collection
   - Required for unique indexes
   - Higher cost (minimum 400 RU/s per collection)

**Our Configuration** (`v0.4.4`):
```python
# backend/src/database/mongodb.py
def get_database() -> Database:
    """Shared database throughput - no unique indexes allowed"""
    return mongo_client[settings.MONGODB_DATABASE]
```

**Solution**: Use application-level uniqueness validation instead of database indexes for most cases. Only migrate to collection-level throughput if strict database-level uniqueness is required.

## Index Creation Best Practices

### Compound Indexes for Query Performance

**Use Case**: Queries filtering by multiple fields

**Example** (messages collection):
```python
# Efficient query: db.messages.find({"chat_id": "...", "role": "user"})
messages_collection.create_index([("chat_id", 1), ("role", 1)])

# Efficient query: db.chats.find({"user_id": "...", "created_at": -1})
chats_collection.create_index([("user_id", 1), ("created_at", -1)])
```

**Rule**: Index fields in order of query filters (left to right)

### Unique Index Limitations

**Cosmos DB Restriction**: Unique indexes require collection-level throughput

**Workaround**: Application-level validation
```python
async def create_user(email: str):
    # Check uniqueness before insert
    if await users_collection.find_one({"email": email}):
        raise ValueError("Email already exists")

    await users_collection.insert_one({"email": email, ...})
```

**When to Use Collection Throughput**: Critical uniqueness constraints (user emails, API keys) where database-level enforcement is required for data integrity.

## Connection String Parsing

### Issue: Database Name Extraction from Connection String

**Symptom**: Application connects but uses wrong database name

**Root Cause**: Different connection string formats between Azure Cosmos DB and native MongoDB

**Azure Cosmos DB Format**:
```
mongodb://account:key@account.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000
```

**Native MongoDB Format**:
```
mongodb://user:pass@host:port/database?options
```

**Solution** (implemented in `v0.4.4`):
```python
# backend/src/config.py
def _extract_db_from_connection_string(conn_str: str) -> str:
    """Extract database name from MongoDB connection string"""
    if not conn_str:
        return "financial_agent"

    # Azure Cosmos DB: mongodb://account.mongo.cosmos.azure.com/...
    # Extract account name before .mongo.cosmos.azure.com
    if ".mongo.cosmos.azure.com" in conn_str:
        match = re.search(r"mongodb://([^:]+):", conn_str)
        if match:
            return match.group(1)

    # Standard MongoDB: mongodb://host:port/database
    parsed = urlparse(conn_str)
    if parsed.path and len(parsed.path) > 1:
        return parsed.path.lstrip("/").split("?")[0]

    return "financial_agent"  # fallback
```

**Key Logic**:
1. For Azure Cosmos DB: Extract account name from hostname
2. For standard MongoDB: Parse database from path
3. Fallback to default if parsing fails

## RU/s (Request Units) Management

### Understanding Request Units

**What are RU/s?**: Cosmos DB's throughput currency
- 1 RU = Cost of reading 1KB document by ID
- Writes, queries, indexes consume more RUs
- Shared throughput: Total RU/s split across all collections

**Our Configuration**:
- Shared database throughput: 400 RU/s (minimum)
- Suitable for ~10 beta users with moderate usage

### Monitoring and Scaling

**Check Current Usage**:
```bash
az cosmosdb mongodb database throughput show \
  --account-name <account> \
  --resource-group <rg> \
  --name <database>
```

**Scale Up** (if throttling occurs):
```bash
az cosmosdb mongodb database throughput update \
  --account-name <account> \
  --resource-group <rg> \
  --name <database> \
  --throughput 800
```

**Signs of Throttling**:
- 429 "Request rate too large" errors
- Slow query performance
- Application timeouts

**Cost Optimization**:
- Use compound indexes to reduce query RU cost
- Implement caching for frequently accessed data
- Consider autoscale throughput for variable load

## Connection Errors

### SSL/TLS Configuration

**Required for Cosmos DB**: `ssl=true` in connection string

**Error**: `SSL handshake failed`
**Fix**: Ensure connection string includes `?ssl=true`

### Network Connectivity

**Error**: `connection timeout` or `network unreachable`

**Checklist**:
1. Firewall rules: Allow Azure services or specific IPs
2. VNet integration: Check service endpoints/private endpoints
3. DNS resolution: Verify `<account>.mongo.cosmos.azure.com` resolves

**Verify from AKS**:
```bash
# Get shell in backend pod
kubectl exec -it -n klinematrix-test deployment/backend -- sh

# Test DNS resolution
nslookup <account>.mongo.cosmos.azure.com

# Test connectivity
curl -v telnet://<account>.mongo.cosmos.azure.com:10255
```

### Authentication Errors

**Error**: `authentication failed` or `unauthorized`

**Root Causes**:
1. Wrong connection string (keys rotated)
2. Incorrect database name
3. Missing External Secrets sync

**Fix**:
```bash
# Check External Secrets sync
kubectl get externalsecrets -n klinematrix-test
kubectl describe externalsecret mongodb-secret -n klinematrix-test

# Verify secret content (base64 encoded)
kubectl get secret mongodb-secret -n klinematrix-test -o jsonpath='{.data.MONGODB_CONNECTION_STRING}' | base64 -d

# Restart pods to reload secrets
kubectl delete pod -l app=backend -n klinematrix-test
```

## Performance Optimization

### Efficient Queries

**Use Projection**: Only fetch needed fields
```python
# Bad: Fetches all fields
chat = await chats_collection.find_one({"_id": chat_id})

# Good: Only fetches title and created_at
chat = await chats_collection.find_one(
    {"_id": chat_id},
    {"title": 1, "created_at": 1}
)
```

**Use Indexes**: Ensure queries use indexed fields
```python
# Indexed query (fast)
messages = await messages_collection.find({"chat_id": chat_id}).to_list(100)

# Unindexed query (slow, table scan)
messages = await messages_collection.find({"content": {"$regex": "stock"}}).to_list(100)
```

### Pagination

**Use Limit + Skip** (small datasets):
```python
page_size = 20
skip = (page - 1) * page_size
results = await collection.find({}).skip(skip).limit(page_size).to_list(page_size)
```

**Use Cursor-Based** (large datasets, better performance):
```python
# First page
results = await collection.find({}).sort("_id", 1).limit(20).to_list(20)
last_id = results[-1]["_id"]

# Next page
results = await collection.find({"_id": {"$gt": last_id}}).sort("_id", 1).limit(20).to_list(20)
```

## Migration from Native MongoDB

### Compatibility Differences

**Not Supported**:
- Unique indexes on shared throughput databases
- Transactions across multiple collections (limited support)
- Some aggregation operators
- Change streams on shared throughput

**Workarounds**:
- Application-level uniqueness validation
- Single-collection transactions (supported)
- Rewrite aggregations using supported operators
- Use collection-level throughput for change streams

### Migration Checklist

1. **Connection String**: Update format for Cosmos DB
2. **Indexes**: Review unique indexes, migrate to collection throughput if needed
3. **Queries**: Test aggregation pipelines (some operators differ)
4. **Throughput**: Start with 400 RU/s shared, monitor and scale
5. **Code**: Add retry logic for 429 throttling errors

## References

- [Azure Cosmos DB for MongoDB Limits](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/feature-support-42)
- [Request Units in Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/request-units)
- [Indexing in Cosmos DB MongoDB API](https://learn.microsoft.com/en-us/azure/cosmos-db/mongodb/indexing)
- Backend config changes: [v0.4.4 CHANGELOG](../project/versions/backend/CHANGELOG.md)
