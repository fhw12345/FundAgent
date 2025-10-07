#!/bin/bash
# Test the complete authentication flow
# 1. Register a new user: Email → Code → Username + Password
# 2. Login with username/password

set -e

API_URL="https://klinematrix.com/api"
TEST_EMAIL="test_$(date +%s)@example.com"
TEST_USERNAME="test_user_$(date +%s)"
TEST_PASSWORD="TestPass123!"

echo "🧪 Testing Authentication Flow"
echo "================================"
echo ""

# Step 1: Send verification code to email
echo "📧 Step 1: Sending verification code to $TEST_EMAIL"
SEND_CODE_RESPONSE=$(curl -s -X POST "$API_URL/auth/send-code" \
  -H "Content-Type: application/json" \
  -d "{\"auth_type\":\"email\",\"identifier\":\"$TEST_EMAIL\"}")

echo "Response: $SEND_CODE_RESPONSE"
echo ""

# Extract code (for dev/testing - in production, user would get this from email)
# Note: The API doesn't return the code in production, but we can use dev bypass
# For now, we'll use the dev bypass code from .env.base
DEV_CODE="888888"

echo "📝 Using dev bypass code: $DEV_CODE"
echo ""

# Step 2: Register user with code
echo "👤 Step 2: Registering user with username '$TEST_USERNAME'"
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\":\"$TEST_EMAIL\",
    \"code\":\"$DEV_CODE\",
    \"username\":\"$TEST_USERNAME\",
    \"password\":\"$TEST_PASSWORD\"
  }")

echo "Response: $REGISTER_RESPONSE"

# Check if registration was successful
if echo "$REGISTER_RESPONSE" | grep -q "access_token"; then
  echo "✅ Registration successful!"
  ACCESS_TOKEN=$(echo "$REGISTER_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
  echo "   Token: ${ACCESS_TOKEN:0:20}..."
else
  echo "❌ Registration failed!"
  exit 1
fi
echo ""

# Step 3: Login with username and password
echo "🔐 Step 3: Logging in with username and password"
LOGIN_RESPONSE=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\":\"$TEST_USERNAME\",
    \"password\":\"$TEST_PASSWORD\"
  }")

echo "Response: $LOGIN_RESPONSE"

# Check if login was successful
if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
  echo "✅ Login successful!"
  LOGIN_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
  echo "   Token: ${LOGIN_TOKEN:0:20}..."
else
  echo "❌ Login failed!"
  exit 1
fi
echo ""

# Step 4: Get current user with token
echo "👤 Step 4: Getting current user info"
USER_RESPONSE=$(curl -s "$API_URL/auth/me?token=$LOGIN_TOKEN")

echo "Response: $USER_RESPONSE"

if echo "$USER_RESPONSE" | grep -q "user_id"; then
  echo "✅ User info retrieved successfully!"
else
  echo "❌ Failed to get user info!"
  exit 1
fi
echo ""

# Step 5: Test invalid login
echo "❌ Step 5: Testing invalid login (wrong password)"
INVALID_LOGIN=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\":\"$TEST_USERNAME\",
    \"password\":\"WrongPassword123!\"
  }")

echo "Response: $INVALID_LOGIN"

if echo "$INVALID_LOGIN" | grep -q "detail"; then
  echo "✅ Invalid login correctly rejected!"
else
  echo "❌ Invalid login should have been rejected!"
  exit 1
fi
echo ""

echo "================================"
echo "✨ All authentication tests passed!"
echo "================================"
