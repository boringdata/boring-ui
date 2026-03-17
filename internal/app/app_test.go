package app

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"

	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
)

type testModule struct{}

func (testModule) Name() string { return "test" }

func (testModule) RegisterRoutes(router Router) {
	router.Method(http.MethodGet, "/module", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("module-ok"))
	}))
}

type lifecycleModule struct {
	name    string
	calls   *[]string
	stopErr error
}

type boundaryTestModule struct {
	authErr error
}

func (m lifecycleModule) Name() string { return m.name }

func (m lifecycleModule) RegisterRoutes(Router) {}

func (m lifecycleModule) Start(context.Context) error {
	*m.calls = append(*m.calls, "start:"+m.name)
	return nil
}

func (m lifecycleModule) Stop(context.Context) error {
	*m.calls = append(*m.calls, "stop:"+m.name)
	return m.stopErr
}

func (boundaryTestModule) Name() string { return "boundary-test" }

func (m boundaryTestModule) RegisterRoutes(router Router) {
	router.Method(http.MethodGet, "/api/v1/files/ping", http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		authCtx, ok := auth.ContextFromRequest(req)
		if !ok {
			http.Error(w, "missing auth context", http.StatusUnauthorized)
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{
			"user_id":      authCtx.UserID,
			"workspace_id": req.Header.Get("X-Workspace-ID"),
		})
	}))
}

func (m boundaryTestModule) AuthorizeWorkspaceBoundary(*http.Request) error {
	return m.authErr
}

func TestAddModuleRegistersRoutesAndKeepsCopy(t *testing.T) {
	app := New(config.Config{})
	app.AddModule(testModule{})
	app.AddModule(testModule{})

	req := httptest.NewRequest(http.MethodGet, "/module", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", rec.Code)
	}

	body, err := io.ReadAll(rec.Body)
	if err != nil {
		t.Fatalf("read response body: %v", err)
	}
	if string(body) != "module-ok" {
		t.Fatalf("expected module response, got %q", body)
	}

	modules := app.Modules()
	if len(modules) != 1 {
		t.Fatalf("expected 1 module, got %d", len(modules))
	}

	modules[0] = nil
	if app.Modules()[0] == nil {
		t.Fatal("expected Modules to return a defensive copy")
	}
}

func TestAppStartStopLifecycleCallsModulesInOrder(t *testing.T) {
	var calls []string
	app := New(config.Config{})
	app.AddModule(lifecycleModule{name: "alpha", calls: &calls})
	app.AddModule(lifecycleModule{name: "beta", calls: &calls})

	if err := app.Start(context.Background()); err != nil {
		t.Fatalf("start app: %v", err)
	}
	if err := app.Stop(context.Background()); err != nil {
		t.Fatalf("stop app: %v", err)
	}

	want := []string{"start:alpha", "start:beta", "stop:beta", "stop:alpha"}
	if !reflect.DeepEqual(calls, want) {
		t.Fatalf("unexpected lifecycle order: got %v want %v", calls, want)
	}
}

func TestAppStopReturnsModuleError(t *testing.T) {
	expectedErr := errors.New("stop failed")
	app := New(config.Config{})
	app.AddModule(lifecycleModule{name: "alpha", calls: new([]string), stopErr: expectedErr})

	err := app.Stop(context.Background())
	if !errors.Is(err, expectedErr) {
		t.Fatalf("expected stop error %v, got %v", expectedErr, err)
	}
}

func TestWorkspaceBoundaryForwardsAuthAndWorkspaceHeader(t *testing.T) {
	app := New(config.Config{})
	app.AddModule(boundaryTestModule{})

	token, err := app.SessionManager().Create(auth.User{
		ID:      "user-123",
		Email:   "user@example.com",
		IsOwner: true,
	})
	if err != nil {
		t.Fatalf("create session token: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/w/ws-123/api/v1/files/ping", nil)
	req.AddCookie(&http.Cookie{Name: app.SessionManager().CookieName(), Value: token})
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d body=%s", rec.Code, rec.Body.String())
	}

	var payload map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("decode boundary payload: %v", err)
	}
	if payload["user_id"] != "user-123" {
		t.Fatalf("expected forwarded auth context, got %q", payload["user_id"])
	}
	if payload["workspace_id"] != "ws-123" {
		t.Fatalf("expected forwarded workspace header, got %q", payload["workspace_id"])
	}
}

func TestWorkspaceBoundaryReturnsAuthorizerStatus(t *testing.T) {
	app := New(config.Config{})
	app.AddModule(boundaryTestModule{
		authErr: APIError{
			Status:  http.StatusForbidden,
			Code:    "WORKSPACE_MEMBERSHIP_REQUIRED",
			Message: "Workspace membership required",
		},
	})

	token, err := app.SessionManager().Create(auth.User{
		ID:      "user-123",
		Email:   "user@example.com",
		IsOwner: true,
	})
	if err != nil {
		t.Fatalf("create session token: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/w/ws-123/api/v1/files/ping", nil)
	req.AddCookie(&http.Cookie{Name: app.SessionManager().CookieName(), Value: token})
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusForbidden {
		t.Fatalf("expected status 403, got %d body=%s", rec.Code, rec.Body.String())
	}
	if body := rec.Body.String(); !strings.Contains(body, `"detail":"Workspace membership required"`) {
		t.Fatalf("expected detail in forbidden payload, got %s", body)
	}
}

func TestWorkspaceBoundaryRejectsInvalidWorkspaceID(t *testing.T) {
	app := New(config.Config{})
	app.AddModule(boundaryTestModule{})

	token, err := app.SessionManager().Create(auth.User{
		ID:      "user-123",
		Email:   "user@example.com",
		IsOwner: true,
	})
	if err != nil {
		t.Fatalf("create session token: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/w/ws-123%0a/api/v1/files/ping", nil)
	req.AddCookie(&http.Cookie{Name: app.SessionManager().CookieName(), Value: token})
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected status 400, got %d body=%s", rec.Code, rec.Body.String())
	}
}
