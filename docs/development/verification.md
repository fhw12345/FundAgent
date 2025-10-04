# Walking Skeleton Verification Guide

This guide will help you verify that the Financial Agent platform's walking skeleton is working correctly on your local machine.

## Prerequisites

Before starting, ensure you have:

- ✅ Docker Desktop installed and running
- ✅ Python 3.9+ for testing scripts
- ✅ Web browser (Chrome, Firefox, Safari, etc.)
- ✅ Terminal/Command prompt access

## Step 1: Start the Platform

### 1.1 Navigate to Project Directory
```bash
cd /Users/allenpan/Desktop/repos/projects/financial_agent
```

### 1.2 Start All Services
```bash
# Start the entire platform
make dev

# Alternative: Direct Docker Compose command
docker-compose up -d
```

**Expected Output:**
```
✅ Services should be ready!
Frontend: http://localhost:3000
Backend API: http://localhost:8000
Backend Docs: http://localhost:8000/docs
```

### 1.3 Verify Services Are Running
```bash
docker-compose ps
```

**Expected Output:**
```
NAME                         STATUS
financial_agent-backend-1    Up (healthy)
financial_agent-frontend-1   Up
financial_agent-mongodb-1    Up
financial_agent-redis-1      Up
```

**What to Look For:**
- All 4 services should show "Up" status
- Backend should show "(healthy)" indicator

## Step 2: Test Backend Health Endpoint

### 2.1 Test Using Python Script
```bash
python3 -c "
import requests
import json
try:
    response = requests.get('http://localhost:8000/api/health', timeout=10)
    print('✅ Backend Health Check')
    print('Status Code:', response.status_code)
    health_data = response.json()
    print('Overall Status:', health_data['status'])
    print('MongoDB Connected:', '✅' if health_data['dependencies']['mongodb']['connected'] else '❌')
    print('Redis Connected:', '✅' if health_data['dependencies']['redis']['connected'] else '❌')
    print('Environment:', health_data['environment'])
    print('Version:', health_data['version'])
except Exception as e:
    print('❌ Error:', str(e))
"
```

**Expected Output:**
```
✅ Backend Health Check
Status Code: 200
Overall Status: ok
MongoDB Connected: ✅
Redis Connected: ✅
Environment: development
Version: 0.1.0
```

### 2.2 Test Using Browser
Open your browser and go to: **http://localhost:8000/api/health**

**Expected Result:**
- You should see a JSON response with `"status": "ok"`
- Both MongoDB and Redis should show `"connected": true`

## Step 3: Test Frontend Interface

### 3.1 Open Frontend in Browser
Navigate to: **http://localhost:3000**

**Expected Result:**
- ✅ Page loads successfully
- ✅ You see "Financial Agent" header
- ✅ Two tabs: "Health Status" and "Chat Interface"
- ✅ Modern, clean UI with TailwindCSS styling

### 3.2 Test Health Status Tab
1. Click on **"Health Status"** tab (should be active by default)
2. Wait for the health check to load

**Expected Result:**
- ✅ Green badge showing "Healthy" status
- ✅ MongoDB section shows ✅ with version number
- ✅ Redis section shows ✅ with version number
- ✅ Configuration shows correct environment and database name
- ✅ Green success message: "Walking Skeleton Verified!"

### 3.3 Test Chat Interface Tab
1. Click on **"Chat Interface"** tab
2. You should see a chat interface with:
   - Welcome message from the AI assistant
   - Quick action buttons (Fibonacci AAPL, Macro Sentiment, etc.)
   - Message input field and send button

### 3.4 Test Mock Chat Functionality
1. Type a test message like "Hello" in the input field
2. Click the **Send** button or press Enter

**Expected Result:**
- ✅ Your message appears in the chat
- ✅ After ~1.5 seconds, you get a mock response
- ✅ The response mentions it's a mock and explains the chat endpoint will be implemented later

## Step 4: Test API Documentation

### 4.1 Access API Docs
Open your browser and go to: **http://localhost:8000/docs**

**Expected Result:**
- ✅ Interactive Swagger/OpenAPI documentation loads
- ✅ You see endpoints listed:
  - `GET /` - Root endpoint
  - `GET /api/health` - Health check
  - `GET /api/health/mongodb` - MongoDB health
  - `GET /api/health/redis` - Redis health
  - `GET /api/health/ready` - Readiness probe
  - `GET /api/health/live` - Liveness probe

### 4.2 Test Endpoints in API Docs
1. Click on `GET /api/health`
2. Click **"Try it out"**
3. Click **"Execute"**

**Expected Result:**
- ✅ Response code: 200
- ✅ Response body shows healthy status with database connections

## Step 5: Advanced Verification Tests

### 5.1 Complete Integration Test
Run this comprehensive test script:

```bash
python3 -c "
import requests
import time

print('🧪 COMPREHENSIVE WALKING SKELETON TEST')
print('=' * 50)

tests_passed = 0
total_tests = 6

# Test 1: Backend Root Endpoint
try:
    response = requests.get('http://localhost:8000/', timeout=5)
    if response.status_code == 200 and 'Financial Agent API' in response.json()['message']:
        print('✅ Test 1: Backend Root Endpoint - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 1: Backend Root Endpoint - FAILED')
except Exception as e:
    print('❌ Test 1: Backend Root Endpoint - ERROR:', str(e))

# Test 2: Health Check Endpoint
try:
    response = requests.get('http://localhost:8000/api/health', timeout=5)
    health_data = response.json()
    if (response.status_code == 200 and
        health_data['status'] == 'ok' and
        health_data['dependencies']['mongodb']['connected'] and
        health_data['dependencies']['redis']['connected']):
        print('✅ Test 2: Health Check - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 2: Health Check - FAILED')
except Exception as e:
    print('❌ Test 2: Health Check - ERROR:', str(e))

# Test 3: MongoDB Health
try:
    response = requests.get('http://localhost:8000/api/health/mongodb', timeout=5)
    if response.status_code == 200 and response.json()['connected']:
        print('✅ Test 3: MongoDB Health - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 3: MongoDB Health - FAILED')
except Exception as e:
    print('❌ Test 3: MongoDB Health - ERROR:', str(e))

# Test 4: Redis Health
try:
    response = requests.get('http://localhost:8000/api/health/redis', timeout=5)
    if response.status_code == 200 and response.json()['connected']:
        print('✅ Test 4: Redis Health - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 4: Redis Health - FAILED')
except Exception as e:
    print('❌ Test 4: Redis Health - ERROR:', str(e))

# Test 5: Frontend Accessibility
try:
    response = requests.get('http://localhost:3000', timeout=5)
    if response.status_code == 200 and len(response.text) > 500:
        print('✅ Test 5: Frontend Accessibility - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 5: Frontend Accessibility - FAILED')
except Exception as e:
    print('❌ Test 5: Frontend Accessibility - ERROR:', str(e))

# Test 6: API Documentation
try:
    response = requests.get('http://localhost:8000/docs', timeout=5)
    if response.status_code == 200:
        print('✅ Test 6: API Documentation - PASSED')
        tests_passed += 1
    else:
        print('❌ Test 6: API Documentation - FAILED')
except Exception as e:
    print('❌ Test 6: API Documentation - ERROR:', str(e))

print('=' * 50)
print(f'🎯 RESULTS: {tests_passed}/{total_tests} tests passed')

if tests_passed == total_tests:
    print('🎉 ALL TESTS PASSED - Walking Skeleton is FULLY OPERATIONAL!')
    print('')
    print('🌐 Access Points:')
    print('   • Frontend: http://localhost:3000')
    print('   • Backend API: http://localhost:8000')
    print('   • API Docs: http://localhost:8000/docs')
    print('   • Health Check: http://localhost:8000/api/health')
else:
    print('⚠️  Some tests failed. Check the errors above.')
"
```

## Step 6: Development Commands

Test the development workflow commands:

### 6.1 View Logs
```bash
# View all service logs
make logs

# View specific service logs
docker-compose logs backend
docker-compose logs frontend
```

### 6.2 Check Service Status
```bash
# Check if all services are healthy
make health

# Alternative manual check
docker-compose ps
```

### 6.3 Stop Services
```bash
# Stop all services
make down

# Alternative
docker-compose down
```

## Troubleshooting Common Issues

### Issue 1: Services Won't Start
**Symptoms:** `docker-compose up` fails or services show "Exited" status

**Solutions:**
```bash
# Clean up and restart
make clean
make dev

# Check for port conflicts
lsof -i :3000  # Frontend port
lsof -i :8000  # Backend port
lsof -i :27017 # MongoDB port
lsof -i :6379  # Redis port
```

### Issue 2: Backend Shows "unhealthy"
**Symptoms:** Backend container shows "Up (unhealthy)" status

**Solutions:**
```bash
# Check backend logs
docker-compose logs backend

# Restart backend service
docker-compose restart backend

# Check if MongoDB/Redis are accessible
docker-compose logs mongodb
docker-compose logs redis
```

### Issue 3: Frontend Not Loading
**Symptoms:** Browser shows connection error at localhost:3000

**Solutions:**
```bash
# Check frontend logs
docker-compose logs frontend

# Verify frontend container is running
docker-compose ps frontend

# Restart frontend
docker-compose restart frontend
```

### Issue 4: Database Connection Errors
**Symptoms:** Health check shows MongoDB or Redis as disconnected

**Solutions:**
```bash
# Check database logs
docker-compose logs mongodb
docker-compose logs redis

# Restart database services
docker-compose restart mongodb redis backend
```

## Success Criteria

Your walking skeleton is working correctly if:

- ✅ All 4 Docker containers are running
- ✅ Backend health endpoint returns `"status": "ok"`
- ✅ Both MongoDB and Redis show as connected
- ✅ Frontend loads at localhost:3000
- ✅ Health Status tab shows all green indicators
- ✅ Chat interface is accessible and functional
- ✅ API documentation is available at localhost:8000/docs
- ✅ All verification tests pass

## Next Steps

Once your walking skeleton is verified and working:

1. **Explore the Interface** - Try the chat interface and health monitoring
2. **Review the Code** - Check out the backend and frontend source code
3. **Run Development Commands** - Try `make fmt`, `make lint`, `make test`
4. **Ready for Phase 2** - Your foundation is solid for implementing financial analysis features!

**Congratulations!** You have successfully verified the Financial Agent platform's walking skeleton. The foundation is ready for building the full AI-enhanced financial analysis features!
