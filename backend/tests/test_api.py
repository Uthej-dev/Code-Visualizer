from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_samples_endpoint():
    samples = client.get("/api/samples").json()
    assert len(samples) == 10
    assert {"id", "title", "description", "concepts", "code"} <= set(samples[0])


def test_trace_endpoint_ok():
    res = client.post("/api/trace", json={"code": "x = 1\nprint(x)\n"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok" and body["output"] == "1\n"
    assert body["steps"][0]["stack"][0]["locals"][0]["name"] == "x"


def test_trace_endpoint_runtime_error():
    body = client.post("/api/trace", json={"code": "[][0]\n"}).json()
    assert body["status"] == "error" and body["error"]["type"] == "IndexError"


def test_trace_endpoint_rejects_bad_input():
    assert client.post("/api/trace", json={}).status_code == 422
    assert client.post("/api/trace", json={"code": "x" * 20_001}).status_code == 422
    assert client.post("/api/trace", json={"code": 5}).status_code == 422
    body = client.post("/api/trace", json={"code": "   "}).json()
    assert body["error"]["phase"] == "input"
