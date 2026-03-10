# 10. Testing

[< Back to Index](README.md) | [Prev: Build & Packaging](09-build-packaging.md) | [Next: Checklist >](11-checklist.md)

---

## 10.1 Backend Tests

```python
# tests/test_app.py
import pytest
from fastapi.testclient import TestClient


def test_capabilities():
    from backend.app import create_app
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert data["features"]["my_domain"] is True


def test_domain_items():
    from backend.app import create_app
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/my-domain/items")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total" in data


def test_domain_item_not_found():
    from backend.app import create_app
    app = create_app()
    client = TestClient(app)
    resp = client.get("/api/v1/my-domain/items/nonexistent")
    assert resp.status_code in (200, 404)
```

Run with:
```bash
cd src/web
PYTHONPATH="../../interface/boring-ui/src/back:." pytest tests/ -v
```

## 10.2 Frontend Tests

```javascript
// frontend/panels/MyDomainPanel.test.jsx
import { render, screen } from '@testing-library/react'
import MyDomainPanel from './MyDomainPanel'

test('renders panel', () => {
  render(<MyDomainPanel />)
  expect(screen.getByText('My Domain')).toBeTruthy()
})
```

Run with:
```bash
cd src/web
npx vitest run
```

## 10.3 Integration / Smoke Tests

See [Build & Packaging](09-build-packaging.md#93-smoke-tests) for the smoke test script.

## 10.4 Test Environment

Set up a `conftest.py` for backend tests:

```python
# tests/conftest.py
import os
import pytest

@pytest.fixture(autouse=True)
def env_setup(tmp_path):
    """Ensure tests use isolated workspace."""
    os.environ["MY_APP_WORKSPACE_ROOT"] = str(tmp_path)
    os.environ["CONTROL_PLANE_ENABLED"] = "false"
    yield
    os.environ.pop("MY_APP_WORKSPACE_ROOT", None)
    os.environ.pop("CONTROL_PLANE_ENABLED", None)
```
