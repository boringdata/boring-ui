package app

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"os"

	"github.com/boringdata/boring-ui/internal/config"
)

// Module is the unit registered into the Go backend as the surface area grows.
type Module interface {
	Name() string
	RegisterRoutes(router Router)
}

// App owns the shared HTTP mux and a registry of mounted modules.
type App struct {
	cfg     config.Config
	router  *chiAdapter
	handler http.Handler
	logger  *slog.Logger
	metrics *appMetrics
	modules []Module
}

// New builds the base application with health and config-driven defaults.
func New(cfg config.Config) *App {
	app := &App{
		cfg:     cfg,
		router:  newChiAdapter(),
		logger:  newRedactingLogger(os.Stdout),
		metrics: newAppMetrics(),
	}
	app.registerCoreRoutes()
	app.handler = app.wrapMiddlewares(app.router.Handler())
	return app
}

// AddModule mounts a module exactly once and tracks it for capabilities/inspection.
func (a *App) AddModule(module Module) {
	if module == nil {
		return
	}
	for _, existing := range a.modules {
		if existing.Name() == module.Name() {
			return
		}
	}
	a.modules = append(a.modules, module)
	module.RegisterRoutes(a.router)
}

// Modules returns a copy so callers cannot mutate the internal registry.
func (a *App) Modules() []Module {
	out := make([]Module, len(a.modules))
	copy(out, a.modules)
	return out
}

// Handler exposes the root mux for http.Server wiring and tests.
func (a *App) Handler() http.Handler {
	return a.handler
}

func (a *App) registerCoreRoutes() {
	a.router.Method(http.MethodGet, "/health", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	}))
	a.router.Method(http.MethodGet, "/metrics", a.metrics.Handler())
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
