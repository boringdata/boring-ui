package github

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/boringdata/boring-ui/internal/app"
	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
	"github.com/boringdata/boring-ui/internal/db"
	controlplane "github.com/boringdata/boring-ui/internal/modules/controlplane"
)

const modulePrefix = "/api/v1/auth/github"

const pendingStateTTL = 10 * time.Minute

type Module struct {
	cfg     config.Config
	service *appService

	mu            sync.RWMutex
	repo          controlplane.Repository
	pool          *pgxpool.Pool
	pendingStates map[string]pendingState
}

func NewModule(cfg config.Config) (*Module, error) {
	repo, err := newLocalRepositoryFromConfig(cfg)
	if err != nil {
		return nil, err
	}
	service, err := newAppService(appConfig{
		AppID:         strings.TrimSpace(os.Getenv("GITHUB_APP_ID")),
		ClientID:      strings.TrimSpace(os.Getenv("GITHUB_APP_CLIENT_ID")),
		ClientSecret:  strings.TrimSpace(os.Getenv("GITHUB_APP_CLIENT_SECRET")),
		PrivateKeyPEM: strings.TrimSpace(os.Getenv("GITHUB_APP_PRIVATE_KEY")),
		AppSlug:       strings.TrimSpace(os.Getenv("GITHUB_APP_SLUG")),
		BaseURL:       strings.TrimSpace(os.Getenv("GITHUB_BASE_URL")),
		APIBaseURL:    strings.TrimSpace(os.Getenv("GITHUB_API_BASE_URL")),
	})
	if err != nil {
		return nil, err
	}
	return &Module{
		cfg:           cfg,
		repo:          repo,
		service:       service,
		pendingStates: map[string]pendingState{},
	}, nil
}

func (m *Module) Name() string {
	return "github"
}

func (m *Module) Start(ctx context.Context) error {
	dbCfg, err := db.ConfigFromEnv()
	if err != nil {
		if errors.Is(err, db.ErrMissingDatabaseURL) {
			return nil
		}
		return err
	}

	if _, ok := m.currentRepo().(*controlplane.PostgresRepository); ok {
		return nil
	}

	pool, err := db.Open(ctx, dbCfg)
	if err != nil {
		return err
	}
	if err := db.CheckSchema(ctx, pool); err != nil {
		pool.Close()
		return err
	}
	repo, err := controlplane.NewPostgresRepositoryFromEnv(pool)
	if err != nil {
		pool.Close()
		return err
	}
	m.setRepository(repo, pool)
	return nil
}

func (m *Module) Stop(_ context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.pool != nil {
		m.pool.Close()
		m.pool = nil
	}
	repo, err := newLocalRepositoryFromConfig(m.cfg)
	if err == nil {
		m.repo = repo
	}
	return nil
}

func (m *Module) RegisterRoutes(router app.Router) {
	router.Route(modulePrefix, func(r app.Router) {
		r.Method(http.MethodGet, "/status", http.HandlerFunc(m.handleStatus))
		r.Method(http.MethodGet, "/authorize", http.HandlerFunc(m.handleAuthorize))
		r.Method(http.MethodGet, "/callback", http.HandlerFunc(m.handleCallback))
		r.Method(http.MethodPost, "/connect", http.HandlerFunc(m.handleConnect))
		r.Method(http.MethodPost, "/disconnect", http.HandlerFunc(m.handleDisconnect))
		r.Method(http.MethodGet, "/installations", http.HandlerFunc(m.handleInstallations))
		r.Method(http.MethodGet, "/repos", http.HandlerFunc(m.handleRepos))
		r.Method(http.MethodGet, "/git-credentials", http.HandlerFunc(m.handleGitCredentials))
		r.Method(http.MethodPost, "/repo", http.HandlerFunc(m.handleSelectRepo))
	})
}

func (m *Module) handleStatus(w http.ResponseWriter, req *http.Request) {
	authCtx, repo := m.requireSession(req)
	workspaceID := strings.TrimSpace(req.URL.Query().Get("workspace_id"))

	userSettings, err := repo.GetSettings(req.Context(), authCtx.UserID)
	if err != nil {
		panic(err)
	}

	workspaceSettings := map[string]any{}
	if workspaceID != "" {
		if err := requireWorkspaceMember(req.Context(), repo, workspaceID, authCtx.UserID); err != nil {
			panic(err)
		}
		workspaceSettings, err = repo.GetWorkspaceSettings(req.Context(), workspaceID)
		if err != nil {
			panic(err)
		}
	}

	accountLinked := asBool(userSettings["github_account_linked"]) || strings.TrimSpace(asString(userSettings["github_access_token"])) != ""
	defaultInstallationID := installationIDValue(userSettings["github_default_installation_id"])
	installationID := installationIDValue(workspaceSettings["github_installation_id"])
	repoURL := strings.TrimSpace(asString(workspaceSettings["github_repo_url"]))

	writeJSON(w, http.StatusOK, map[string]any{
		"configured":              m.service.configured(),
		"connected":               installationID != nil,
		"account_linked":          accountLinked,
		"default_installation_id": defaultInstallationID,
		"installation_connected":  installationID != nil,
		"installation_id":         installationID,
		"repo_selected":           repoURL != "",
		"repo_url":                nilIfEmpty(repoURL),
	})
}

func (m *Module) handleAuthorize(w http.ResponseWriter, req *http.Request) {
	if !m.service.canAuthorize() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}
	authCtx, _ := m.requireSession(req)
	forceInstall := strings.EqualFold(strings.TrimSpace(req.URL.Query().Get("force_install")), "true")
	pending := pendingState{
		UserID:       authCtx.UserID,
		WorkspaceID:  strings.TrimSpace(req.URL.Query().Get("workspace_id")),
		ForceInstall: forceInstall,
		CreatedAt:    time.Now(),
	}
	state, err := m.newPendingState(pending)
	if err != nil {
		panic(err)
	}
	location, err := m.service.authorizeURL(callbackURL(req), state, forceInstall)
	if err != nil {
		panic(err)
	}
	writeRedirect(w, location, http.StatusTemporaryRedirect)
}

func (m *Module) handleCallback(w http.ResponseWriter, req *http.Request) {
	if !m.service.canAuthorize() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}

	state := strings.TrimSpace(req.URL.Query().Get("state"))
	code := strings.TrimSpace(req.URL.Query().Get("code"))
	installationID, installationErr := parseInstallationID(req.URL.Query().Get("installation_id"))
	if code == "" && installationErr != nil {
		writeHTML(w, http.StatusOK, `<!doctype html><html><body><p>Missing code or installation_id</p><p>Redirecting...</p><script>window.location.href=window.location.origin</script></body></html>`)
		return
	}

	authCtx, repo := m.requireSession(req)
	pending, err := m.consumePendingState(state, authCtx.UserID)
	if err != nil {
		panic(err)
	}

	if code != "" {
		accessToken, err := m.service.exchangeCode(req.Context(), code)
		if err != nil {
			panic(err)
		}
		installations, err := m.service.userInstallations(req.Context(), accessToken)
		if err != nil {
			panic(err)
		}

		settingsPatch := map[string]any{
			"github_account_linked": true,
			"github_access_token":   accessToken,
		}
		if len(installations) > 0 {
			if installationID, err := parseInstallationID(installations[0]["id"]); err == nil {
				settingsPatch["github_default_installation_id"] = strconv.FormatInt(installationID, 10)
				if pending.WorkspaceID != "" {
					if err := requireWorkspaceMember(req.Context(), repo, pending.WorkspaceID, authCtx.UserID); err != nil {
						panic(err)
					}
					if _, err := repo.SaveWorkspaceSettings(req.Context(), pending.WorkspaceID, map[string]any{
						"github_installation_id": strconv.FormatInt(installationID, 10),
					}); err != nil {
						panic(err)
					}
				}
			}
		}
		if _, err := repo.SaveSettings(req.Context(), authCtx.UserID, authCtx.Email, settingsPatch); err != nil {
			panic(err)
		}
		writeHTML(w, http.StatusOK, `<!doctype html><html><body><p>Connected successfully!</p><script>if(window.opener){window.opener.postMessage({type:"github-callback",success:true},window.location.origin)}window.close()</script></body></html>`)
		return
	}

	settingsPatch := map[string]any{
		"github_account_linked":          true,
		"github_default_installation_id": strconv.FormatInt(installationID, 10),
	}
	if _, err := repo.SaveSettings(req.Context(), authCtx.UserID, authCtx.Email, settingsPatch); err != nil {
		panic(err)
	}
	if pending.WorkspaceID != "" {
		if err := requireWorkspaceMember(req.Context(), repo, pending.WorkspaceID, authCtx.UserID); err != nil {
			panic(err)
		}
		if _, err := repo.SaveWorkspaceSettings(req.Context(), pending.WorkspaceID, map[string]any{
			"github_installation_id": strconv.FormatInt(installationID, 10),
		}); err != nil {
			panic(err)
		}
	}

	writeHTML(w, http.StatusOK, `<!doctype html><html><body><p>Connected successfully!</p><script>if(window.opener){window.opener.postMessage({type:"github-callback",success:true},window.location.origin)}window.close()</script></body></html>`)
}

func (m *Module) handleConnect(w http.ResponseWriter, req *http.Request) {
	authCtx, repo := m.requireSession(req)
	if !m.service.configured() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}

	var body map[string]any
	if err := decodeJSON(req, &body); err != nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_json", Message: err.Error()})
	}

	workspaceID := strings.TrimSpace(asString(body["workspace_id"]))
	if workspaceID == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_workspace_id", Message: "workspace_id is required"})
	}
	installationID, err := parseInstallationID(body["installation_id"])
	if err != nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_installation_id", Message: "installation_id is required"})
	}

	if err := requireWorkspaceMember(req.Context(), repo, workspaceID, authCtx.UserID); err != nil {
		panic(err)
	}
	if err := m.ensureUserCanAccessInstallation(req.Context(), repo, authCtx.UserID, installationID); err != nil {
		panic(err)
	}

	settings, err := repo.SaveWorkspaceSettings(req.Context(), workspaceID, map[string]any{
		"github_installation_id": strconv.FormatInt(installationID, 10),
	})
	if err != nil {
		panic(err)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"connected":       true,
		"installation_id": installationID,
		"settings":        settings,
	})
}

func (m *Module) handleDisconnect(w http.ResponseWriter, req *http.Request) {
	authCtx, repo := m.requireSession(req)

	var body map[string]any
	if err := decodeJSON(req, &body); err != nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_json", Message: err.Error()})
	}
	workspaceID := strings.TrimSpace(asString(body["workspace_id"]))
	if workspaceID == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_workspace_id", Message: "workspace_id is required"})
	}
	if err := requireWorkspaceMember(req.Context(), repo, workspaceID, authCtx.UserID); err != nil {
		panic(err)
	}

	settings, err := repo.SaveWorkspaceSettings(req.Context(), workspaceID, map[string]any{
		"github_installation_id": nil,
		"github_repo_url":        nil,
	})
	if err != nil {
		panic(err)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":        true,
		"connected": false,
		"settings":  settings,
	})
}

func (m *Module) handleInstallations(w http.ResponseWriter, req *http.Request) {
	if !m.service.configured() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}
	installations, err := m.service.listInstallations(req.Context())
	if err != nil {
		panic(err)
	}

	items := make([]map[string]any, 0, len(installations))
	for _, installation := range installations {
		accountLogin := ""
		accountType := ""
		if raw, ok := installation["account"].(map[string]any); ok {
			accountLogin = asString(raw["login"])
			accountType = asString(raw["type"])
		}
		items = append(items, map[string]any{
			"id":           installationIDValue(installation["id"]),
			"account":      accountLogin,
			"account_type": accountType,
		})
	}
	writeJSON(w, http.StatusOK, map[string]any{"installations": items})
}

func (m *Module) handleRepos(w http.ResponseWriter, req *http.Request) {
	if !m.service.configured() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}
	authCtx, repo := m.requireSession(req)

	installationID, err := parseInstallationID(req.URL.Query().Get("installation_id"))
	if err != nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_installation_id", Message: "installation_id is required"})
	}
	if err := m.ensureUserCanAccessInstallation(req.Context(), repo, authCtx.UserID, installationID); err != nil {
		panic(err)
	}
	repos, err := m.service.repositories(req.Context(), installationID)
	if err != nil {
		panic(err)
	}
	writeJSON(w, http.StatusOK, map[string]any{"repos": repos})
}

func (m *Module) handleGitCredentials(w http.ResponseWriter, req *http.Request) {
	if !m.service.configured() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}
	authCtx, repo := m.requireSession(req)

	workspaceID := strings.TrimSpace(req.URL.Query().Get("workspace_id"))
	if workspaceID == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_workspace_id", Message: "workspace_id is required"})
	}
	if err := requireWorkspaceMember(req.Context(), repo, workspaceID, authCtx.UserID); err != nil {
		panic(err)
	}
	settings, err := repo.GetWorkspaceSettings(req.Context(), workspaceID)
	if err != nil {
		panic(err)
	}
	installationID := installationIDValue(settings["github_installation_id"])
	if installationID == nil {
		panic(app.APIError{Status: http.StatusNotFound, Code: "not_connected", Message: "Workspace not connected to GitHub"})
	}
	credentials, err := m.service.gitCredentials(req.Context(), *installationID)
	if err != nil {
		panic(err)
	}
	w.Header().Set("Cache-Control", "no-store")
	writeJSON(w, http.StatusOK, credentials)
}

func (m *Module) handleSelectRepo(w http.ResponseWriter, req *http.Request) {
	authCtx, repo := m.requireSession(req)

	var body map[string]any
	if err := decodeJSON(req, &body); err != nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_json", Message: err.Error()})
	}
	workspaceID := strings.TrimSpace(asString(body["workspace_id"]))
	if workspaceID == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_workspace_id", Message: "workspace_id is required"})
	}
	repoURL := normalizeRepoURL(asString(body["repo_url"]))
	if repoURL == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_repo_url", Message: "repo_url is required"})
	}
	if err := requireWorkspaceMember(req.Context(), repo, workspaceID, authCtx.UserID); err != nil {
		panic(err)
	}

	workspaceSettings, err := repo.GetWorkspaceSettings(req.Context(), workspaceID)
	if err != nil {
		panic(err)
	}
	installationID := installationIDValue(workspaceSettings["github_installation_id"])
	if installationID == nil {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "not_connected", Message: "Workspace must be connected to GitHub first"})
	}
	if !m.service.configured() {
		panic(app.APIError{Status: http.StatusServiceUnavailable, Code: "github_not_configured", Message: "GitHub App not configured"})
	}
	repos, err := m.service.repositories(req.Context(), *installationID)
	if err != nil {
		panic(err)
	}
	canonicalRepoURL := ""
	for _, candidate := range repos {
		if normalizeRepoURL(asString(candidate["clone_url"])) == repoURL || normalizeRepoURL(asString(candidate["ssh_url"])) == repoURL {
			canonicalRepoURL = normalizeRepoURL(asString(candidate["clone_url"]))
			if canonicalRepoURL == "" {
				canonicalRepoURL = repoURL
			}
			break
		}
	}
	if canonicalRepoURL == "" {
		panic(app.APIError{Status: http.StatusBadRequest, Code: "invalid_repo_url", Message: "repo_url is not available to this installation"})
	}

	settings, err := repo.SaveWorkspaceSettings(req.Context(), workspaceID, map[string]any{
		"github_repo_url": canonicalRepoURL,
	})
	if err != nil {
		panic(err)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":       true,
		"repo_url": canonicalRepoURL,
		"settings": settings,
	})
}

func (m *Module) requireSession(req *http.Request) (auth.AuthContext, controlplane.Repository) {
	authCtx, ok := auth.ContextFromRequest(req)
	if !ok || strings.TrimSpace(authCtx.UserID) == "" {
		panic(app.APIError{Status: http.StatusUnauthorized, Code: "unauthorized", Message: "authentication required"})
	}
	repo := m.currentRepo()
	if repo == nil {
		panic(fmt.Errorf("control plane repository is unavailable"))
	}
	return authCtx, repo
}

func (m *Module) userAccessToken(ctx context.Context, repo controlplane.Repository, userID string) (string, error) {
	settings, err := repo.GetSettings(ctx, userID)
	if err != nil {
		return "", err
	}
	token := strings.TrimSpace(asString(settings["github_access_token"]))
	if token == "" {
		return "", app.APIError{Status: http.StatusUnauthorized, Code: "github_account_not_linked", Message: "GitHub account is not linked"}
	}
	return token, nil
}

func (m *Module) ensureUserCanAccessInstallation(ctx context.Context, repo controlplane.Repository, userID string, installationID int64) error {
	accessToken, err := m.userAccessToken(ctx, repo, userID)
	if err != nil {
		return err
	}
	installations, err := m.service.userInstallations(ctx, accessToken)
	if err != nil {
		return err
	}
	for _, installation := range installations {
		current := installationIDValue(installation["id"])
		if current != nil && *current == installationID {
			return nil
		}
	}
	return app.APIError{Status: http.StatusForbidden, Code: "installation_forbidden", Message: "GitHub installation is not accessible to this user"}
}

func (m *Module) currentRepo() controlplane.Repository {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.repo
}

func (m *Module) setRepository(repo controlplane.Repository, pool *pgxpool.Pool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.pool != nil && m.pool != pool {
		m.pool.Close()
	}
	m.repo = repo
	m.pool = pool
}

type pendingState struct {
	UserID       string
	WorkspaceID  string
	ForceInstall bool
	CreatedAt    time.Time
}

func (m *Module) newPendingState(state pendingState) (string, error) {
	var raw [16]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return "", err
	}
	key := fmt.Sprintf("%x", raw[:])
	m.mu.Lock()
	m.cleanupExpiredPendingStatesLocked(m.clock())
	m.pendingStates[key] = state
	m.mu.Unlock()
	return key, nil
}

func (m *Module) consumePendingState(state, userID string) (pendingState, error) {
	if strings.TrimSpace(state) == "" {
		return pendingState{}, app.APIError{Status: http.StatusBadRequest, Code: "invalid_state", Message: "state is required"}
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	m.cleanupExpiredPendingStatesLocked(m.clock())
	pending, ok := m.pendingStates[state]
	delete(m.pendingStates, state)
	if !ok {
		return pendingState{}, app.APIError{Status: http.StatusBadRequest, Code: "invalid_state", Message: "state is invalid or expired"}
	}
	if m.clock().Sub(pending.CreatedAt) > pendingStateTTL {
		return pendingState{}, app.APIError{Status: http.StatusBadRequest, Code: "invalid_state", Message: "state is invalid or expired"}
	}
	if strings.TrimSpace(pending.UserID) != strings.TrimSpace(userID) {
		return pendingState{}, app.APIError{Status: http.StatusBadRequest, Code: "invalid_state", Message: "state is invalid or expired"}
	}
	return pending, nil
}

func (m *Module) cleanupExpiredPendingStatesLocked(now time.Time) {
	for key, pending := range m.pendingStates {
		if now.Sub(pending.CreatedAt) > pendingStateTTL {
			delete(m.pendingStates, key)
		}
	}
}

func (m *Module) clock() time.Time {
	if m.service != nil && m.service.now != nil {
		return m.service.now()
	}
	return time.Now()
}

func newLocalRepositoryFromConfig(cfg config.Config) (controlplane.Repository, error) {
	workspaceRoot := "."
	if cfg.ConfigPath != "" {
		workspaceRoot = filepath.Dir(cfg.ConfigPath)
	}
	return controlplane.NewLocalRepository(workspaceRoot)
}

func callbackURL(req *http.Request) string {
	scheme := "http"
	if req.TLS != nil {
		scheme = "https"
	}
	if forwarded := strings.TrimSpace(req.Header.Get("X-Forwarded-Proto")); forwarded != "" {
		scheme = forwarded
	}
	host := req.Host
	if forwardedHost := strings.TrimSpace(req.Header.Get("X-Forwarded-Host")); forwardedHost != "" {
		host = forwardedHost
	}
	return fmt.Sprintf("%s://%s%s/callback", scheme, host, modulePrefix)
}

func normalizeRepoURL(value string) string {
	trimmed := strings.TrimSpace(value)
	trimmed = strings.TrimSuffix(trimmed, ".git")
	trimmed = strings.TrimRight(trimmed, "/")
	return strings.ToLower(trimmed)
}

func installationIDValue(value any) *int64 {
	id, err := parseInstallationID(value)
	if err != nil || id == 0 {
		return nil
	}
	return &id
}

func asString(value any) string {
	switch typed := value.(type) {
	case string:
		return typed
	case json.Number:
		return typed.String()
	default:
		if typed == nil {
			return ""
		}
		return fmt.Sprintf("%v", typed)
	}
}

func asBool(value any) bool {
	switch typed := value.(type) {
	case bool:
		return typed
	case string:
		return strings.EqualFold(strings.TrimSpace(typed), "true")
	default:
		return false
	}
}

func nilIfEmpty(value string) any {
	if strings.TrimSpace(value) == "" {
		return nil
	}
	return value
}

func requireWorkspaceMember(ctx context.Context, repo controlplane.Repository, workspaceID, userID string) error {
	if _, err := repo.GetWorkspace(ctx, workspaceID); err != nil {
		if errors.Is(err, controlplane.ErrNotFound) {
			return app.APIError{Status: http.StatusNotFound, Code: "not_found", Message: "Workspace not found"}
		}
		return err
	}
	members, err := repo.ListMembers(ctx, workspaceID)
	if err != nil {
		return err
	}
	for _, member := range members {
		if strings.TrimSpace(asString(member["user_id"])) == strings.TrimSpace(userID) &&
			strings.TrimSpace(asString(member["status"])) == "active" &&
			asString(member["deleted_at"]) == "" {
			return nil
		}
	}
	return app.APIError{Status: http.StatusNotFound, Code: "not_found", Message: "Workspace not found"}
}

func decodeJSON(req *http.Request, target any) error {
	defer req.Body.Close()
	decoder := json.NewDecoder(io.LimitReader(req.Body, 1<<20))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("request body must contain a single JSON object")
	}
	return nil
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeHTML(w http.ResponseWriter, status int, payload string) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(status)
	_, _ = io.WriteString(w, payload)
}

func writeRedirect(w http.ResponseWriter, location string, status int) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Location", location)
	w.WriteHeader(status)
}
