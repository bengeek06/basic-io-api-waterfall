# Troubleshooting: Missing Content-Disposition Header & Authentication Issues

## Problems

### 1. Missing Content-Disposition Header
The `Content-Disposition` header is correctly set by the Basic I/O service but may not reach the client when accessed through an API gateway/proxy (e.g., Next.js on port 3000).

### 2. 401 Authentication Errors Through Proxy
The proxy may not forward authentication cookies to the Basic I/O service, causing "Missing or invalid JWT token" errors even when the client has valid cookies.

## Verification

### 1. Test Direct Service (Port 5004)

```bash
# Test JSON export directly
curl -I "http://localhost:5004/export?url=http://identity_service:5000/customers&type=json" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"

# Expected header:
# Content-Disposition: attachment; filename="customers_export.json"
```

### 2. Test Through Gateway (Port 3000)

```bash
# Test JSON export through Next.js gateway
curl -I "http://localhost:3000/api/basic-io/export?url=http://identity_service:5000/users&type=json" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"

# If Content-Disposition is missing -> proxy issue
```

## Root Cause

If the header is present in direct calls (port 5004) but missing through the gateway (port 3000), the issue is in the **Next.js API route proxy configuration**.

### Issue 1: Missing Content-Disposition Header
The proxy returns data but doesn't forward response headers.

### Issue 2: 401 Authentication Errors
The proxy doesn't forward the `Cookie` header from client to backend service.

**Evidence from logs**:
```
web_service: Request headers: {"accept":"*/*", ..., "user-agent":"..."}
                             ^^^ NO Cookie header!

basic_io_service: "GET /export?url=... HTTP/1.1" 401
                                                  ^^^ Authentication failed
```

## Solution for Next.js Proxy

### Location

Find the Next.js API route handler, likely in:
- `app/api/basic-io/export/route.ts`
- `pages/api/basic-io/export.ts`

### Current (Incorrect) Implementation

```typescript
// ❌ PROBLEM 1: Doesn't forward cookies -> causes 401 errors
// ❌ PROBLEM 2: Strips response headers -> missing Content-Disposition
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = url.searchParams;
  
  const response = await fetch(
    `http://basic_io_service:5000/export?${params}`,
    {
      headers: {
        // Missing Cookie header! Backend will reject with 401
      }
    }
  );
  
  const data = await response.text();
  
  // Only returns data, loses headers
  return new Response(data, {
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json'
      // Missing Content-Disposition!
    }
  });
}
```

### Fixed Implementation

```typescript
// ✅ CORRECT: Forwards cookies AND preserves headers
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = url.searchParams;
  
  const response = await fetch(
    `http://basic_io_service:5000/export?${params}`,
    {
      headers: {
        // Forward authentication cookie from client
        'Cookie': request.headers.get('cookie') || '',
        'Accept': request.headers.get('accept') || '*/*'
      }
    }
  );
  
  const data = await response.text();
  
  // Forward critical response headers back to client
  return new Response(data, {
    status: response.status,
    headers: {
      'Content-Type': response.headers.get('content-type') || 'application/json',
      'Content-Disposition': response.headers.get('content-disposition') || '',
      'Cache-Control': response.headers.get('cache-control') || 'no-cache'
    }
  });
}
```

### Alternative: Forward All Headers

```typescript
// Copy all response headers
const headers = new Headers();
response.headers.forEach((value, key) => {
  // Skip hop-by-hop headers
  if (!['connection', 'keep-alive', 'transfer-encoding'].includes(key.toLowerCase())) {
    headers.set(key, value);
  }
});

return new Response(data, {
  status: response.status,
  headers: headers
});
```

## Testing After Fix

### Test 1: Authentication Should Work
```bash
# Should now return 200 (not 401) through gateway
curl -i "http://localhost:3000/api/basic-io/export?url=http%3A%2F%2Fidentity_service%3A5000%2Fusers&type=json" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"

# Expected: HTTP 200 OK (not 401)
```

### Test 2: Content-Disposition Should Be Present
```bash
# Should now show Content-Disposition through gateway
curl -I "http://localhost:3000/api/basic-io/export?url=http%3A%2F%2Fidentity_service%3A5000%2Fusers&type=json" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN" \
  | grep -i content-disposition

# Expected output:
# Content-Disposition: attachment; filename="users_export.json"
```

## Current Status

- ✅ **Basic I/O Service (Port 5004)**: Everything works correctly
  - Content-Disposition header is set
  - Authentication with JWT cookies works
  - JSON/CSV/Mermaid exports all functional

- ❌ **API Gateway (Port 3000)**: Two issues in Next.js proxy
  - **Issue 1**: Doesn't forward `Cookie` header → causes 401 errors
  - **Issue 2**: Doesn't forward `Content-Disposition` header → missing filename
  - **Fix required**: Update Next.js API route handler (see solutions above)

## Common Symptoms

### Symptom 1: "Missing or invalid JWT token" (401)
**Cause**: Proxy not forwarding cookies OR client not sending cookies  
**Evidence in logs**: 
- If `web_service` shows NO `cookie` in "Request headers" → **Client problem**
- If `web_service` shows `cookie` in request but not forwarded → **Proxy problem**

**Debugging**:
```bash
# Check what headers client is sending
# Look for "Request headers received from client:" in web_service logs
docker compose logs web_service | grep "Request headers"

# If no 'cookie' field → client needs to authenticate first
# If 'cookie' present but not forwarded → proxy needs fixing
```

**Fix for client issue** (Python requests):
```python
# ❌ WRONG - Fresh session without login
session = requests.Session()
response = session.get("/api/basic-io/export")  # 401 - No cookies!

# ✅ CORRECT - Login first to get cookies
session = requests.Session()
session.post("/api/auth/login", json={
    "email": "user@example.com",
    "password": "password"
})  # Sets access_token cookie
response = session.get("/api/basic-io/export")  # 200 - Cookies sent
```

**Fix for proxy issue**: Add `'Cookie': request.headers.get('cookie')` to fetch headers

### Symptom 2: Downloaded file has generic name
**Cause**: Proxy not forwarding Content-Disposition  
**Evidence**: Browser saves as "export" or "download" instead of "users_export.json"  
**Fix**: Add `'Content-Disposition': response.headers.get('content-disposition')` to response headers

## Reference

- **Bug Report**: See project issue tracker
- **Service Code**: 
  - `app/resources/export_json.py` (lines 164-168)
  - `app/resources/export_csv.py` (lines 192-196)
  - `app/resources/export_mermaid.py` (lines 435-442)
- **HTTP Spec**: [RFC 6266 - Content-Disposition](https://tools.ietf.org/html/rfc6266)

## Client-Side Issue: Not Sending Cookies

If logs show **NO `cookie` in request headers**, the problem is the **client not authenticating**.

### Common Causes

1. **Fresh session without login**
   ```python
   session = requests.Session()  # No cookies
   session.get("/api/basic-io/export")  # 401
   ```

2. **Expired cookies**
   - Login was 24 hours ago, JWT expired
   - Solution: Re-authenticate

3. **Different session between tests**
   ```python
   session1.post("/api/auth/login")  # Sets cookies
   session2.get("/api/basic-io/export")  # Different session, no cookies!
   ```

4. **Cookies not persisting**
   - Check cookie domain/path
   - Verify `session.cookies` after login

### Client Fix Example

```python
class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self._authenticated = False
    
    def ensure_authenticated(self):
        """Ensure session has valid authentication cookies"""
        if not self._authenticated or 'access_token' not in self.session.cookies:
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json={"email": "user@example.com", "password": "password"}
            )
            if response.status_code != 200:
                raise Exception("Login failed")
            self._authenticated = True
    
    def get(self, path, **kwargs):
        self.ensure_authenticated()
        return self.session.get(f"{self.base_url}{path}", **kwargs)

# Usage
api = APIClient("http://localhost:3000")
response = api.get("/api/basic-io/export?url=...&type=json")  # Auto-authenticates
```
