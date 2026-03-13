package app

import (
	"net/http"
	"net/http/httptest"
	"os/exec"
	"strings"
	"testing"
)

func TestRouterMethodAndRoute(t *testing.T) {
	router := newChiAdapter()
	router.Route("/api", func(r Router) {
		r.Method(http.MethodGet, "/ping", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("pong"))
		}))
	})

	req := httptest.NewRequest(http.MethodGet, "/api/ping", nil)
	rec := httptest.NewRecorder()
	router.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}
	if body := rec.Body.String(); body != "pong" {
		t.Fatalf("expected pong body, got %q", body)
	}
}

func TestRouterWithMiddleware(t *testing.T) {
	authMiddleware := func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			if req.Header.Get("X-Auth") == "" {
				http.Error(w, "missing auth", http.StatusUnauthorized)
				return
			}
			next.ServeHTTP(w, req)
		})
	}

	router := newChiAdapter()
	router.With(authMiddleware).Method(http.MethodGet, "/private", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))

	req := httptest.NewRequest(http.MethodGet, "/private", nil)
	rec := httptest.NewRecorder()
	router.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected status 401 without auth, got %d", rec.Code)
	}

	req = httptest.NewRequest(http.MethodGet, "/private", nil)
	req.Header.Set("X-Auth", "present")
	rec = httptest.NewRecorder()
	router.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200 with auth, got %d", rec.Code)
	}
}

func TestOnlyRouterAdapterImportsChi(t *testing.T) {
	cmd := exec.Command("rg", "-n", "github.com/go-chi/chi", "internal", "--glob", "*.go", "-g", "!internal/app/router.go", "-g", "!internal/app/router_test.go")
	cmd.Dir = "../.."
	output, err := cmd.CombinedOutput()
	if err == nil && strings.TrimSpace(string(output)) != "" {
		t.Fatalf("expected no direct chi imports outside router adapter, got:\n%s", output)
	}
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok && exitErr.ExitCode() == 1 {
			return
		}
		t.Fatalf("run rg: %v\n%s", err, output)
	}
}
