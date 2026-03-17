package app

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
	"github.com/prometheus/client_golang/prometheus"
)

// Module is the unit registered into the Go backend as the surface area grows.
type Module interface {
	Name() string
	RegisterRoutes(router Router)
}

type starter interface {
	Start(context.Context) error
}

type stopper interface {
	Stop(context.Context) error
}

type authStateBridge interface {
	OnAuthenticated(context.Context, auth.User) error
	BuildMePayload(context.Context, auth.AuthContext) (map[string]any, error)
}

type workspaceBoundaryAuthorizer interface {
	AuthorizeWorkspaceBoundary(*http.Request) error
}

type metricsRegistrar interface {
	RegisterMetrics(registry *prometheus.Registry)
}

var workspaceBoundaryIDPattern = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)

// App owns the shared HTTP mux and a registry of mounted modules.
type App struct {
	cfg           config.Config
	router        *chiAdapter
	handler       http.Handler
	logger        *slog.Logger
	metrics       *appMetrics
	modules       []Module
	auth          *auth.SessionManager
	tokenVerifier *auth.TokenVerifier
	provider      *auth.LocalProvider
	authState     authStateBridge
	boundaryAuth  workspaceBoundaryAuthorizer
}

// New builds the base application with health and config-driven defaults.
func New(cfg config.Config) *App {
	if len(cfg.PTYProviders) == 0 {
		cfg.PTYProviders = config.DefaultPTYProviders()
	} else {
		cfg.PTYProviders = config.ClonePTYProviders(cfg.PTYProviders)
	}
	sessionSecret := auth.SessionSecretFromEnv()
	app := &App{
		cfg:     cfg,
		router:  newChiAdapter(),
		logger:  newRedactingLogger(os.Stdout),
		metrics: newAppMetrics(),
		auth: auth.NewSessionManager(auth.SessionConfig{
			CookieName: cfg.Auth.SessionCookie,
			Secret:     sessionSecret,
			TTL:        time.Duration(cfg.Auth.SessionTTL) * time.Second,
		}),
		tokenVerifier: auth.NewTokenVerifier(auth.TokenVerifierConfig{
			SessionSecret: sessionSecret,
			NeonBaseURL:   firstNonEmpty(os.Getenv("NEON_AUTH_BASE_URL"), cfg.Deploy.Neon.AuthURL),
			NeonJWKSURL:   firstNonEmpty(os.Getenv("NEON_AUTH_JWKS_URL"), cfg.Deploy.Neon.JWKSURL),
		}),
		provider: auth.NewLocalProviderFromEnv(),
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
	if registrar, ok := module.(metricsRegistrar); ok {
		registrar.RegisterMetrics(a.metrics.registry)
	}
	if authorizer, ok := module.(workspaceBoundaryAuthorizer); ok && a.boundaryAuth == nil {
		a.boundaryAuth = authorizer
		a.registerWorkspaceBoundaryRoutes()
	}
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

func (a *App) SessionManager() *auth.SessionManager {
	return a.auth
}

func (a *App) SetAuthStateBridge(bridge authStateBridge) {
	a.authState = bridge
}

func (a *App) Start(ctx context.Context) error {
	started := make([]Module, 0, len(a.modules))
	for _, module := range a.modules {
		starterModule, ok := module.(starter)
		if !ok {
			continue
		}
		if err := starterModule.Start(ctx); err != nil {
			for i := len(started) - 1; i >= 0; i-- {
				if stopperModule, ok := started[i].(stopper); ok {
					_ = stopperModule.Stop(ctx)
				}
			}
			return err
		}
		started = append(started, module)
	}
	return nil
}

func (a *App) Stop(ctx context.Context) error {
	for i := len(a.modules) - 1; i >= 0; i-- {
		stopperModule, ok := a.modules[i].(stopper)
		if !ok {
			continue
		}
		if err := stopperModule.Stop(ctx); err != nil {
			return err
		}
	}
	return nil
}

func (a *App) registerCoreRoutes() {
	a.router.Method(http.MethodGet, "/health", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"status":    "ok",
			"workspace": a.workspaceRoot(),
			"features":  a.capabilitiesPayload()["features"],
		})
	}))
	a.router.Method(http.MethodGet, "/metrics", a.metrics.Handler())
	a.router.Method(http.MethodGet, "/api/capabilities", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, a.capabilitiesPayload())
	}))
	a.router.Method(http.MethodGet, "/api/config", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		ptyProviders := make([]string, 0, len(a.cfg.PTYProviders))
		for name := range a.cfg.PTYProviders {
			ptyProviders = append(ptyProviders, name)
		}
		sort.Strings(ptyProviders)
		writeJSON(w, http.StatusOK, map[string]any{
			"workspace_root": a.workspaceRoot(),
			"pty_providers":  ptyProviders,
			"paths": map[string]string{
				"files": ".",
			},
		})
	}))
	a.router.Method(http.MethodGet, "/api/project", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"root": a.workspaceRoot(),
		})
	}))
	a.router.Method(http.MethodGet, "/api/v1/me", http.HandlerFunc(a.handleMe))
	a.router.Method(http.MethodGet, "/auth/callback", http.HandlerFunc(a.handleCallbackRedirect))
	a.router.Method(http.MethodGet, "/auth/login", http.HandlerFunc(a.handleLoginRedirect))
	a.router.Method(http.MethodPost, "/auth/login", http.HandlerFunc(a.handleLoginPOST))
	a.router.Method(http.MethodGet, "/auth/logout", http.HandlerFunc(a.handleLogoutRedirect))
	a.router.Method(http.MethodPost, "/auth/logout", http.HandlerFunc(a.handleLogoutPOST))
	a.router.Method(http.MethodGet, "/auth/session", http.HandlerFunc(a.handleSession))
	a.router.Method(http.MethodPost, "/auth/token-exchange", http.HandlerFunc(a.handleTokenExchange))
}

func (a *App) registerWorkspaceBoundaryRoutes() {
	handler := http.HandlerFunc(a.handleWorkspaceBoundary)
	a.router.Method(http.MethodGet, "/w/{workspaceID}", handler)
	a.router.Method(http.MethodGet, "/w/{workspaceID}/", handler)
	a.router.Method(http.MethodGet, "/w/{workspaceID}/setup", handler)
	for _, method := range []string{
		http.MethodGet,
		http.MethodHead,
		http.MethodPost,
		http.MethodPut,
		http.MethodPatch,
		http.MethodDelete,
		http.MethodOptions,
	} {
		a.router.Method(method, "/w/{workspaceID}/*", handler)
	}
}

func (a *App) handleWorkspaceBoundary(w http.ResponseWriter, req *http.Request) {
	if a.boundaryAuth == nil {
		http.NotFound(w, req)
		return
	}
	workspaceID := strings.TrimSpace(URLParam(req, "workspaceID"))
	if workspaceID == "" {
		writeAPIError(w, req, http.StatusBadRequest, "bad_request", "INVALID_WORKSPACE_ID", "workspace_id is required")
		return
	}
	if !workspaceBoundaryIDPattern.MatchString(workspaceID) {
		writeAPIError(w, req, http.StatusBadRequest, "bad_request", "INVALID_WORKSPACE_ID", "workspace_id is invalid")
		return
	}
	if err := a.boundaryAuth.AuthorizeWorkspaceBoundary(req); err != nil {
		apiErr := APIError{
			Status:  http.StatusInternalServerError,
			Code:    "internal_error",
			Message: "internal server error",
		}
		switch value := err.(type) {
		case APIError:
			apiErr = value
		case *APIError:
			if value != nil {
				apiErr = *value
			}
		default:
			var wrapped *APIError
			if errors.As(err, &wrapped) && wrapped != nil {
				apiErr = *wrapped
			}
		}
		writeAPIError(w, req, apiErr.Status, apiErr.Code, apiErr.Code, apiErr.Message)
		return
	}

	suffix := strings.TrimPrefix(req.URL.Path, "/w/"+workspaceID)
	switch suffix {
	case "", "/":
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":           true,
			"workspace_id": workspaceID,
			"route":        "root",
		})
		return
	case "/setup":
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":           true,
			"workspace_id": workspaceID,
			"route":        "setup",
		})
		return
	}

	targetPath := workspaceBoundaryTarget(suffix)
	if targetPath == "" {
		writeAPIError(w, req, http.StatusNotFound, "not_found", "WORKSPACE_PATH_DENIED", "Workspace path is not allowed")
		return
	}

	cloned := req.Clone(req.Context())
	cloned.URL.Path = targetPath
	cloned.URL.RawPath = targetPath
	cloned.Header = req.Header.Clone()
	cloned.Header.Set("X-Workspace-ID", workspaceID)
	if authCtx, ok := auth.ContextFromRequest(req); ok {
		cloned = cloned.WithContext(auth.ContextWithAuth(cloned.Context(), authCtx))
	}
	a.router.Handler().ServeHTTP(w, cloned)
}

func workspaceBoundaryTarget(suffix string) string {
	switch {
	case strings.HasPrefix(suffix, "/api/capabilities"):
		return suffix
	case strings.HasPrefix(suffix, "/api/v1/me"):
		return suffix
	case strings.HasPrefix(suffix, "/api/v1/files"):
		return suffix
	case strings.HasPrefix(suffix, "/api/v1/git"):
		return suffix
	case strings.HasPrefix(suffix, "/api/v1/ui"):
		return suffix
	case strings.HasPrefix(suffix, "/ws/agent/normal/stream"):
		return suffix
	default:
		return ""
	}
}

func (a *App) workspaceRoot() string {
	if a.cfg.ConfigPath != "" {
		return filepath.Dir(a.cfg.ConfigPath)
	}

	root, err := config.FindProjectRoot()
	if err == nil {
		return root
	}

	dir, err := os.Getwd()
	if err != nil {
		return "."
	}
	return dir
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}
