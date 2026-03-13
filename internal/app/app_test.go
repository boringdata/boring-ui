package app

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/boringdata/boring-ui/internal/config"
)

type testModule struct{}

func (testModule) Name() string { return "test" }

func (testModule) RegisterRoutes(router Router) {
	router.Method(http.MethodGet, "/module", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write([]byte("module-ok"))
	}))
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
