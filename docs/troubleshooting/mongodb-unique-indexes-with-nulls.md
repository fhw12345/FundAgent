# MongoDB Unique Indexes with NULL Values

## Problem Statement

When implementing a multi-auth system (email, phone, WeChat) where users can sign up with any ONE method, we need:
- Each auth method to be unique (no duplicate emails/phones/WeChat IDs)
- Support for NULL values in unused auth fields
- **Multiple users with NULL in the same field**

## The Issue: Sparse Indexes Don't Allow Multiple NULLs

### What We Tried (Broken)
```python
# ❌ THIS FAILS - Only allows ONE NULL value per field
await users.create_index("phone_number", unique=True, sparse=True)
await users.create_index("email", unique=True, sparse=True)
await users.create_index("wechat_openid", unique=True, sparse=True)
```

### Why It Failed
```javascript
// User 1: Email-only signup ✅
{
  user_id: "user_001",
  email: "alice@163.com",
  phone_number: null,
  wechat_openid: null
}

// User 2: Phone-only signup ❌ FAILS!
{
  user_id: "user_002",
  email: null,              // ← Duplicate NULL error!
  phone_number: "+86123456",
  wechat_openid: null       // ← Duplicate NULL error!
}
```

**Error Message:**
```
E11000 duplicate key error collection: financial_agent.users
index: idx_phone_number dup key: { phone_number: null }
```

### Root Cause
**Sparse indexes in MongoDB 7.0+ still enforce uniqueness on NULL values.**

MongoDB treats NULL as a value in sparse indexes and only allows ONE document with NULL for that field. This breaks our multi-auth system where most users will have NULL in 2 out of 3 auth fields.

## The Solution: Partial Indexes with Type Filtering

### Working Implementation
```python
# ✅ THIS WORKS - Allows unlimited NULLs, enforces uniqueness on strings
await users.create_index(
    "phone_number",
    unique=True,
    partialFilterExpression={"phone_number": {"$type": "string"}},
    name="idx_phone_number"
)

await users.create_index(
    "email",
    unique=True,
    partialFilterExpression={"email": {"$type": "string"}},
    name="idx_email"
)

await users.create_index(
    "wechat_openid",
    unique=True,
    partialFilterExpression={"wechat_openid": {"$type": "string"}},
    name="idx_wechat_openid"
)
```

### How It Works
The `partialFilterExpression: {"field": {"$type": "string"}}` means:
- **Only index documents where the field is a STRING**
- NULL values are **completely ignored** (not in the index at all)
- Uniqueness is **only enforced on actual string values**

### Example Behavior
```javascript
// ✅ All three users work perfectly
// User 1: Email-only
{
  email: "alice@163.com",    // ← Indexed
  phone_number: null,         // ← Not indexed (ignored)
  wechat_openid: null         // ← Not indexed (ignored)
}

// User 2: Phone-only
{
  email: null,                // ← Not indexed (ignored)
  phone_number: "+86123456",  // ← Indexed
  wechat_openid: null         // ← Not indexed (ignored)
}

// User 3: WeChat-only
{
  email: null,                // ← Not indexed (ignored)
  phone_number: null,         // ← Not indexed (ignored)
  wechat_openid: "wx_12345"   // ← Indexed
}

// ❌ Duplicate email is properly blocked
{
  email: "alice@163.com",     // ← ERROR: Duplicate key!
  phone_number: null,
  wechat_openid: null
}
```

## Migration Steps

### 1. Drop Existing Sparse Indexes
```python
# Connect to MongoDB
client = AsyncIOMotorClient("mongodb://mongodb:27017")
db = client["financial_agent"]
users = db["users"]

# Drop broken sparse indexes
await users.drop_index("idx_email")
await users.drop_index("idx_phone_number")
await users.drop_index("idx_wechat_openid")
```

### 2. Create Partial Indexes
```python
# Create working partial indexes
await users.create_index(
    "email",
    unique=True,
    partialFilterExpression={"email": {"$type": "string"}},
    name="idx_email"
)

await users.create_index(
    "phone_number",
    unique=True,
    partialFilterExpression={"phone_number": {"$type": "string"}},
    name="idx_phone_number"
)

await users.create_index(
    "wechat_openid",
    unique=True,
    partialFilterExpression={"wechat_openid": {"$type": "string"}},
    name="idx_wechat_openid"
)
```

### 3. Verify Indexes
```bash
# Check indexes are correct
docker-compose exec mongodb mongosh financial_agent --eval "db.users.getIndexes()"
```

Expected output should include:
```json
{
  "v": 2,
  "key": {"email": 1},
  "name": "idx_email",
  "unique": true,
  "partialFilterExpression": {"email": {"$type": "string"}}
}
```

## Testing

### Test Multiple NULLs (Should Succeed)
```bash
# Create 3 users, all with NULL in different fields
curl -X POST http://localhost:8000/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type":"email","identifier":"user1@163.com"}'

curl -X POST http://localhost:8000/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type":"email","identifier":"user2@163.com"}'

curl -X POST http://localhost:8000/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type":"email","identifier":"user3@163.com"}'

# All should succeed ✅
```

### Test Duplicate Detection (Should Fail)
```bash
# Try to create duplicate email
curl -X POST http://localhost:8000/api/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"auth_type":"email","identifier":"user1@163.com"}'

# Should fail with duplicate key error ❌
```

## Key Takeaways

1. **Sparse ≠ Allowing Multiple NULLs**: Despite the name, sparse indexes still enforce uniqueness on NULL in MongoDB 7.0+

2. **Use Partial Indexes for Optional Unique Fields**: When you need a field to be unique when present, but allow multiple documents without it, use partial indexes with type filtering

3. **Type Filter is Key**: `partialFilterExpression: {"field": {"$type": "string"}}` completely excludes NULL from the index

4. **Migration Required**: If you already have sparse indexes, you MUST drop and recreate them as partial indexes

## Related Files

- `/Users/allenpan/Desktop/repos/projects/financial_agent/backend/scripts/init_indexes.py` - Index creation script
- `/Users/allenpan/Desktop/repos/projects/financial_agent/backend/src/models/user.py` - User model with optional auth fields
- `/Users/allenpan/Desktop/repos/projects/financial_agent/backend/src/database/repositories/user_repository.py` - User repository

## References

- [MongoDB Partial Indexes Documentation](https://www.mongodb.com/docs/manual/core/index-partial/)
- [MongoDB Sparse Indexes Documentation](https://www.mongodb.com/docs/manual/core/index-sparse/)
- MongoDB Version: 7.0+ (behavior may differ in older versions)
