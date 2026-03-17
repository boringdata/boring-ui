package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestRunDetectsShapeDiff(t *testing.T) {
	base := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"backend": "python",
				"modules": []any{
					map[string]any{"name": "files"},
				},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer base.Close()

	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"backend": "go",
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--paths", "/health,/api/capabilities",
	}, &stdout, &stderr)

	if exitCode != 1 {
		t.Fatalf("expected exit code 1, got %d", exitCode)
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
	output := stdout.String()
	if !strings.Contains(output, "/api/capabilities") {
		t.Fatalf("expected diff output to mention path, got %q", output)
	}
	if !strings.Contains(output, "$.modules missing in target") {
		t.Fatalf("expected diff output to mention missing field, got %q", output)
	}
}

func TestRunSupportsIgnoreAndJSONFormat(t *testing.T) {
	base := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"request_id": "abc",
				"features":   map[string]any{"files": true},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer base.Close()

	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"request_id": 123,
				"features":   map[string]any{"files": true},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--paths", "/health,/api/capabilities",
		"--ignore", "request_id",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}

	var rep report
	if err := json.Unmarshal(stdout.Bytes(), &rep); err != nil {
		t.Fatalf("failed to decode JSON report: %v", err)
	}
	if !rep.OK {
		t.Fatalf("expected OK report, got %+v", rep)
	}
	if len(rep.MatchedPaths) != 2 {
		t.Fatalf("expected both paths to match, got %+v", rep.MatchedPaths)
	}
}

func TestRunAllDiscoversOpenAPIPaths(t *testing.T) {
	base := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/openapi.json":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"paths": map[string]any{
					"/health":                 map[string]any{"get": map[string]any{}},
					"/api/capabilities":       map[string]any{"get": map[string]any{}},
					"/api/v1/workspaces/{id}": map[string]any{"get": map[string]any{}},
				},
			})
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{"backend": "python"})
		default:
			http.NotFound(w, r)
		}
	}))
	defer base.Close()

	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/openapi.json":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"paths": map[string]any{
					"/health":           map[string]any{"get": map[string]any{}},
					"/api/capabilities": map[string]any{"get": map[string]any{}},
				},
			})
		case "/health":
			writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
		case "/api/capabilities":
			writeJSON(t, w, http.StatusOK, map[string]any{"backend": "go"})
		default:
			http.NotFound(w, r)
		}
	}))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--all",
		"--ignore", "backend",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}

	var rep report
	if err := json.Unmarshal(stdout.Bytes(), &rep); err != nil {
		t.Fatalf("failed to decode JSON report: %v", err)
	}
	if len(rep.ComparedPaths) != 2 {
		t.Fatalf("expected only non-parameterized GET paths, got %+v", rep.ComparedPaths)
	}
	if rep.ComparedPaths[0] != "/api/capabilities" || rep.ComparedPaths[1] != "/health" {
		t.Fatalf("unexpected compared paths: %+v", rep.ComparedPaths)
	}
}

func TestRunExpandsGlobPathsFromOpenAPI(t *testing.T) {
	base := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/openapi.json":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"paths": map[string]any{
					"/api/v1/git/status":  map[string]any{"get": map[string]any{}},
					"/api/v1/git/remotes": map[string]any{"get": map[string]any{}},
					"/api/v1/git/diff": map[string]any{
						"get": map[string]any{
							"parameters": []map[string]any{{
								"name":     "path",
								"in":       "query",
								"required": true,
							}},
						},
					},
					"/api/v1/files/list":   map[string]any{"get": map[string]any{}},
					"/api/v1/git/checkout": map[string]any{"post": map[string]any{}},
				},
			})
		case "/api/v1/git/status":
			writeJSON(t, w, http.StatusOK, map[string]any{"available": true, "files": []any{}})
		case "/api/v1/git/remotes":
			writeJSON(t, w, http.StatusOK, map[string]any{"remotes": []any{}})
		default:
			http.NotFound(w, r)
		}
	}))
	defer base.Close()

	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/openapi.json":
			writeJSON(t, w, http.StatusOK, map[string]any{
				"paths": map[string]any{
					"/api/v1/git/status":  map[string]any{"get": map[string]any{}},
					"/api/v1/git/remotes": map[string]any{"get": map[string]any{}},
					"/api/v1/git/diff": map[string]any{
						"get": map[string]any{
							"parameters": []map[string]any{{
								"name":     "path",
								"in":       "query",
								"required": true,
							}},
						},
					},
				},
			})
		case "/api/v1/git/status":
			writeJSON(t, w, http.StatusOK, map[string]any{"available": true, "files": []any{}})
		case "/api/v1/git/remotes":
			writeJSON(t, w, http.StatusOK, map[string]any{"remotes": []any{}})
		default:
			http.NotFound(w, r)
		}
	}))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--paths", "/api/v1/git/*",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}

	var rep report
	if err := json.Unmarshal(stdout.Bytes(), &rep); err != nil {
		t.Fatalf("failed to decode JSON report: %v", err)
	}
	want := []string{"/api/v1/git/remotes", "/api/v1/git/status"}
	if fmt.Sprint(rep.ComparedPaths) != fmt.Sprint(want) {
		t.Fatalf("unexpected compared paths: got %+v want %+v", rep.ComparedPaths, want)
	}
}

func TestRunLoginPathEstablishesSession(t *testing.T) {
	var baseLoginCalls atomic.Int32
	var targetLoginCalls atomic.Int32
	newServer := func(loginCalls *atomic.Int32) *httptest.Server {
		return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch r.URL.Path {
			case "/auth/login":
				loginCalls.Add(1)
				http.SetCookie(w, &http.Cookie{Name: "session", Value: "ok", Path: "/"})
				writeJSON(t, w, http.StatusOK, map[string]any{"logged_in": true})
			case "/api/v1/git/status":
				cookie, err := r.Cookie("session")
				if err != nil || cookie.Value != "ok" {
					writeJSON(t, w, http.StatusUnauthorized, map[string]any{"error": "missing session"})
					return
				}
				writeJSON(t, w, http.StatusOK, map[string]any{"available": true, "files": []any{}})
			default:
				http.NotFound(w, r)
			}
		}))
	}

	base := newServer(&baseLoginCalls)
	defer base.Close()
	target := newServer(&targetLoginCalls)
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--login-path", "/auth/login",
		"--paths", "/api/v1/git/status",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}
	if baseLoginCalls.Load() != 1 || targetLoginCalls.Load() != 1 {
		t.Fatalf("expected one login call per server, got base=%d target=%d", baseLoginCalls.Load(), targetLoginCalls.Load())
	}
}

func TestRunLoginPathKeepsBackendSessionsSeparate(t *testing.T) {
	newServer := func(expectedCookie string) *httptest.Server {
		return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch r.URL.Path {
			case "/auth/login":
				http.SetCookie(w, &http.Cookie{Name: "session", Value: expectedCookie, Path: "/"})
				writeJSON(t, w, http.StatusOK, map[string]any{"logged_in": true})
			case "/api/v1/git/status":
				cookie, err := r.Cookie("session")
				if err != nil || cookie.Value != expectedCookie {
					writeJSON(t, w, http.StatusUnauthorized, map[string]any{"error": "wrong session"})
					return
				}
				writeJSON(t, w, http.StatusOK, map[string]any{"available": true, "files": []any{}})
			default:
				http.NotFound(w, r)
			}
		}))
	}

	base := newServer("base-session")
	defer base.Close()
	target := newServer("target-session")
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--login-path", "/auth/login",
		"--paths", "/api/v1/git/status",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}
}

func TestRunLoginPathSupportsRedirectingBootstrap(t *testing.T) {
	newServer := func() *httptest.Server {
		return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			switch r.URL.Path {
			case "/auth/login":
				http.SetCookie(w, &http.Cookie{Name: "session", Value: "ok", Path: "/"})
				http.Redirect(w, r, "/health", http.StatusFound)
			case "/api/v1/git/status":
				cookie, err := r.Cookie("session")
				if err != nil || cookie.Value != "ok" {
					writeJSON(t, w, http.StatusUnauthorized, map[string]any{"error": "missing session"})
					return
				}
				writeJSON(t, w, http.StatusOK, map[string]any{"available": true, "files": []any{}})
			case "/health":
				writeJSON(t, w, http.StatusOK, map[string]any{"status": "ok"})
			default:
				http.NotFound(w, r)
			}
		}))
	}

	base := newServer()
	defer base.Close()
	target := newServer()
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--login-path", "/auth/login",
		"--paths", "/api/v1/git/status",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected exit code 0, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}
}

func TestRunDoesNotFollowRedirectsDuringComparison(t *testing.T) {
	redirectBody := func(path string) http.HandlerFunc {
		return func(w http.ResponseWriter, r *http.Request) {
			switch r.URL.Path {
			case "/auth/logout":
				http.Redirect(w, r, "/post-logout", http.StatusFound)
			case "/post-logout":
				_, _ = w.Write([]byte(path))
			default:
				http.NotFound(w, r)
			}
		}
	}

	base := httptest.NewServer(redirectBody("base"))
	defer base.Close()
	target := httptest.NewServer(redirectBody("target"))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--paths", "/auth/logout",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected redirect endpoints to match without following, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}
}

func TestRunSkipsHTMLBodyComparison(t *testing.T) {
	base := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/auth/github/callback" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("<html><body>base</body></html>"))
	}))
	defer base.Close()

	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/auth/github/callback" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("<html><body>target</body></html>"))
	}))
	defer target.Close()

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	exitCode := run([]string{
		"--base", base.URL,
		"--target", target.URL,
		"--paths", "/api/v1/auth/github/callback",
		"--format", "json",
	}, &stdout, &stderr)

	if exitCode != 0 {
		t.Fatalf("expected host-specific html pages to match on shape, got %d (stderr=%q stdout=%q)", exitCode, stderr.String(), stdout.String())
	}
}

func writeJSON(t *testing.T, w http.ResponseWriter, status int, payload any) {
	t.Helper()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(payload); err != nil {
		t.Fatalf("encode response: %v", err)
	}
}
