# Tests Organization

This directory contains three types of tests, organized by scope and dependencies:

## 📁 Structure

```
tests/
├── unit/           # Unit tests (fast, no external deps)
├── integration/    # Integration tests (mock services)
├── e2e/           # End-to-end tests (real services)
└── conftest.py    # Shared fixtures
```

## 🧪 Test Types

### Unit Tests (`tests/unit/`)

**Purpose:** Test individual components in isolation

**Characteristics:**
- ✅ Fast execution (< 1 second total)
- ✅ No external dependencies
- ✅ All HTTP calls mocked
- ✅ In-memory SQLite database
- ✅ Run on every commit in CI/CD

**Run:**
```bash
pytest tests/unit/ -v
```

**Examples:**
- `test_export_json.py` - Export resource with mocked GET requests
- `test_import_json.py` - Import resource with mocked POST requests
- `test_reference_resolver.py` - FK resolution logic

### Integration Tests (`tests/integration/`)

**Purpose:** Test complete workflows with lightweight mock services

**Characteristics:**
- ⚡ Reasonably fast (< 5 seconds total)
- 🔧 Uses MockWaterfallService (in-memory)
- ✅ Tests export → import roundtrips
- ✅ No real external services needed
- ✅ Run in CI/CD

**Run:**
```bash
pytest tests/integration/ -v
```

**Examples:**
- `test_integration_json.py` - Complete export/import workflows
  - Simple data roundtrip
  - Tree structure with FK mapping
  - Enrichment → Resolution workflow

### E2E Tests (`tests/e2e/`)

**Purpose:** Validate against real Waterfall services

**Characteristics:**
- 🐌 Slower execution
- 🐳 Requires Docker services running
- 🔌 Real HTTP calls to Identity API
- ⚠️ Skipped by default in CI/CD
- 🎯 Manual validation before releases

**Run:**
```bash
# Start services first
docker-compose -f docker-compose.test.yml up -d

# Run E2E tests
pytest --run-e2e tests/e2e/ -v

# Cleanup
docker-compose -f docker-compose.test.yml down
```

**Examples:**
- Real organization_units export/import
- Cross-service FK resolution validation

## 🎯 Testing Strategy

### During Development
```bash
# Quick feedback loop
pytest tests/unit/ -v

# Validate integration
pytest tests/integration/ -v
```

### Before Commit
```bash
# Run all unit + integration tests
pytest tests/ -v --ignore=tests/e2e/
```

### CI/CD Pipeline
```bash
# Runs automatically on push
pytest tests/unit/ tests/integration/ -v --cov=app --cov-report=term-missing
```

### Before Release
```bash
# Manual validation with real services
pytest --run-e2e tests/e2e/ -v
```

## 📊 Coverage Goals

| Test Type | Coverage Target | Speed |
|-----------|----------------|-------|
| Unit | 95%+ | < 1s |
| Integration | Workflow validation | < 5s |
| E2E | Critical paths only | Variable |

## 🔧 Common Fixtures

Defined in `conftest.py`:
- `app` - Flask application
- `client` - Test client
- `auth_headers` - JWT authentication
- `mock_service` - Lightweight mock service (integration tests)

## 📝 Writing Tests

### Unit Test Example
```python
@patch("app.resources.export_json.requests.get")
def test_export_success(mock_get, client, auth_headers):
    mock_get.return_value = Mock(json=lambda: [...], status_code=200)
    response = client.get("/export?url=...")
    assert response.status_code == 200
```

### Integration Test Example
```python
def test_roundtrip(client, auth_headers, mock_service):
    # Export from mock service
    export_data = export_from_source()
    
    # Import to mock service
    import_to_target(export_data)
    
    # Verify in mock service storage
    assert len(mock_service.storage) == expected
```

### E2E Test Example
```python
@pytest.mark.e2e
def test_real_service(client, auth_headers):
    # Real HTTP call to Identity API
    response = client.get("/export?url=http://localhost:5001/api/users")
    assert response.status_code == 200
```

## 🚀 Best Practices

1. **Keep unit tests fast** - Mock all I/O operations
2. **Use integration tests for workflows** - Test component interactions
3. **Reserve E2E for critical paths** - Don't duplicate unit test coverage
4. **Mark E2E tests properly** - Use `@pytest.mark.e2e`
5. **Document dependencies** - Note required services in docstrings
