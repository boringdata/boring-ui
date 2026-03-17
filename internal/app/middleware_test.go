package app

import (
	"bytes"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/boringdata/boring-ui/internal/config"
)

func TestMiddlewareOrder(t *testing.T) {
	app := New(config.Config{})
	stack := app.middlewareStack()
	names := make([]string, 0, len(stack))
	for _, item := range stack {
		names = append(names, item.name)
	}

	expected := []string{"requestID", "cors", "prometheus", "slog", "error", "auth"}
	if len(names) != len(expected) {
		t.Fatalf("expected %d middlewares, got %d", len(expected), len(names))
	}
	for i := range expected {
		if names[i] != expected[i] {
			t.Fatalf("expected middleware %d to be %q, got %q", i, expected[i], names[i])
		}
	}
}

func TestPanicMiddlewareReturnsJSONErrorWithRequestID(t *testing.T) {
	app := New(config.Config{})
	app.router.Method(http.MethodGet, "/panic", http.HandlerFunc(func(http.ResponseWriter, *http.Request) {
		panic("boom")
	}))

	req := httptest.NewRequest(http.MethodGet, "/panic", nil)
	req.Header.Set(requestIDHeader, "req-test")
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d", rec.Code)
	}
	if rec.Header().Get(requestIDHeader) != "req-test" {
		t.Fatalf("expected response request ID header to be preserved")
	}

	var payload map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode json: %v", err)
	}
	if payload["code"] != "internal_error" {
		t.Fatalf("expected internal_error code, got %q", payload["code"])
	}
	if payload["detail"] != "internal server error" {
		t.Fatalf("unexpected detail: %q", payload["detail"])
	}
	if payload["message"] != "internal server error" {
		t.Fatalf("unexpected message: %q", payload["message"])
	}
	if payload["request_id"] != "req-test" {
		t.Fatalf("expected request_id req-test, got %q", payload["request_id"])
	}
}

func TestRequestIDGeneratedWhenMissing(t *testing.T) {
	app := New(config.Config{})

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	requestID := rec.Header().Get(requestIDHeader)
	if requestID == "" {
		t.Fatal("expected generated request ID header")
	}
	if !strings.HasPrefix(requestID, "req-") {
		t.Fatalf("expected generated request ID prefix, got %q", requestID)
	}
}

func TestCORSAllowsConfiguredOrigins(t *testing.T) {
	app := New(config.Config{
		CORSOrigins: []string{"https://allowed.example"},
	})

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	req.Header.Set("Origin", "https://allowed.example")
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "https://allowed.example" {
		t.Fatalf("expected allowed origin header, got %q", got)
	}
	if got := rec.Header().Get("Access-Control-Allow-Credentials"); got != "true" {
		t.Fatalf("expected credentials header, got %q", got)
	}
}

func TestMetricsEndpointExposesHTTPMetrics(t *testing.T) {
	app := New(config.Config{})
	healthReq := httptest.NewRequest(http.MethodGet, "/health", nil)
	healthRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(healthRec, healthReq)

	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	body := rec.Body.String()
	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if !strings.Contains(body, "http_request_duration_seconds") {
		t.Fatal("expected histogram metric in metrics output")
	}
	if !strings.Contains(body, "http_requests_total") {
		t.Fatal("expected counter metric in metrics output")
	}
}

func TestRedactingHandlerScrubsCredentialCorpus(t *testing.T) {
	var buffer bytes.Buffer
	logger := slog.New(newRedactingHandler(slog.NewTextHandler(&buffer, nil)))

	corpus := []string{
		"https://user:pass@github.com/boringdata/boring-ui.git",
		"Bearer abc123secret",
		"ghp_1234567890abcdefghijklmnop",
		"ghs_1234567890abcdefghijklmnop",
		"sk-live-1234567890",
		"xoxb-123456-abcdef",
		"Authorization: Basic YWxhZGRpbjpvcGVuc2VzYW1l",
		"password=hunter2",
		"passwd=hunter2",
		"token=abcd",
		"secret=qwerty",
		"api_key=abc",
		"api-key=abc",
		"access_token=abc",
		"refresh_token=abc",
		"https://alice:supersecret@example.com/path?token=123",
		"Bearer zyx.abc.def",
		"password=topsecret&foo=bar",
		"secret=hide-me",
		"token=qwertyuiop",
	}

	for _, item := range corpus {
		logger.Info(item, "credential", item)
	}

	output := buffer.String()
	for _, forbidden := range []string{
		"user:pass",
		"abc123secret",
		"ghp_1234567890abcdefghijklmnop",
		"ghs_1234567890abcdefghijklmnop",
		"sk-live-1234567890",
		"xoxb-123456-abcdef",
		"YWxhZGRpbjpvcGVuc2VzYW1l",
		"hunter2",
		"qwerty",
		"supersecret",
		"qwertyuiop",
	} {
		if strings.Contains(output, forbidden) {
			t.Fatalf("expected log output to redact %q, got:\n%s", forbidden, output)
		}
	}
	if !strings.Contains(output, "[REDACTED]") {
		t.Fatalf("expected redacted marker in output, got:\n%s", output)
	}
}
