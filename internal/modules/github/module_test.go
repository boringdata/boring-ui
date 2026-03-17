package github

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strconv"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	apppkg "github.com/boringdata/boring-ui/internal/app"
	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
	controlplane "github.com/boringdata/boring-ui/internal/modules/controlplane"
)

func TestGitHubModuleAuthorizeCallbackConnectAndCredentialsFlow(t *testing.T) {
	baseURL, apiURL, _ := newGitHubAPIServer(t)
	cfg := newGitHubTestConfig(t)

	t.Setenv("GITHUB_APP_ID", "12345")
	t.Setenv("GITHUB_APP_CLIENT_ID", "client-123")
	t.Setenv("GITHUB_APP_CLIENT_SECRET", "secret-456")
	t.Setenv("GITHUB_APP_PRIVATE_KEY", newRSAPrivateKeyPEM(t))
	t.Setenv("GITHUB_APP_SLUG", "boring-ui-app")
	t.Setenv("GITHUB_BASE_URL", baseURL)
	t.Setenv("GITHUB_API_BASE_URL", apiURL)

	instance := newGitHubApp(t, cfg)
	cookie := issueSession(t, instance, "user-1", "owner@example.com")

	createWorkspaceReq := httptest.NewRequest(http.MethodPost, "/api/v1/workspaces", strings.NewReader(`{"name":"GitHub"}`))
	createWorkspaceReq.Header.Set("Cookie", cookie)
	createWorkspaceRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(createWorkspaceRec, createWorkspaceReq)
	if createWorkspaceRec.Code != http.StatusCreated {
		t.Fatalf("create workspace: %d %s", createWorkspaceRec.Code, createWorkspaceRec.Body.String())
	}
	workspaceID := extractJSONField(t, createWorkspaceRec.Body.String(), `"id":"`, `"`)

	authorizeReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/authorize?workspace_id="+workspaceID, nil)
	authorizeReq.Header.Set("Cookie", cookie)
	authorizeRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(authorizeRec, authorizeReq)
	if authorizeRec.Code != http.StatusTemporaryRedirect {
		t.Fatalf("authorize: %d %s", authorizeRec.Code, authorizeRec.Body.String())
	}
	if authorizeRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store on authorize redirect, got %q", authorizeRec.Header().Get("Cache-Control"))
	}
	if authorizeRec.Body.Len() != 0 {
		t.Fatalf("expected empty authorize redirect body, got %q", authorizeRec.Body.String())
	}
	if authorizeRec.Header().Get("Content-Type") != "" {
		t.Fatalf("expected authorize redirect without content type, got %q", authorizeRec.Header().Get("Content-Type"))
	}
	if location := authorizeRec.Header().Get("Location"); !strings.Contains(location, "/login/oauth/authorize") {
		t.Fatalf("expected oauth authorize redirect, got %q", location)
	}
	callbackState := extractQueryParam(t, authorizeRec.Header().Get("Location"), "state")

	callbackReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/callback?code=test-code&state="+url.QueryEscape(callbackState), nil)
	callbackReq.Header.Set("Cookie", cookie)
	callbackRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(callbackRec, callbackReq)
	if callbackRec.Code != http.StatusOK {
		t.Fatalf("callback: %d %s", callbackRec.Code, callbackRec.Body.String())
	}
	if !strings.Contains(callbackRec.Body.String(), "Connected successfully!") {
		t.Fatalf("expected callback success html, got %s", callbackRec.Body.String())
	}

	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/status?workspace_id="+workspaceID, nil)
	statusReq.Header.Set("Cookie", cookie)
	statusRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(statusRec, statusReq)
	if statusRec.Code != http.StatusOK {
		t.Fatalf("status: %d %s", statusRec.Code, statusRec.Body.String())
	}
	if !strings.Contains(statusRec.Body.String(), `"account_linked":true`) {
		t.Fatalf("expected linked account in status, got %s", statusRec.Body.String())
	}
	if !strings.Contains(statusRec.Body.String(), `"default_installation_id":99`) {
		t.Fatalf("expected default installation id in status, got %s", statusRec.Body.String())
	}

	connectReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/github/connect", strings.NewReader(`{"workspace_id":"`+workspaceID+`","installation_id":99}`))
	connectReq.Header.Set("Cookie", cookie)
	connectReq.Header.Set("Content-Type", "application/json")
	connectRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(connectRec, connectReq)
	if connectRec.Code != http.StatusOK {
		t.Fatalf("connect: %d %s", connectRec.Code, connectRec.Body.String())
	}

	installationsReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/installations", nil)
	installationsReq.Header.Set("Cookie", cookie)
	installationsRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(installationsRec, installationsReq)
	if installationsRec.Code != http.StatusOK {
		t.Fatalf("installations: %d %s", installationsRec.Code, installationsRec.Body.String())
	}
	if !strings.Contains(installationsRec.Body.String(), `"id":99`) {
		t.Fatalf("expected installation listing, got %s", installationsRec.Body.String())
	}

	reposReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/repos?installation_id=99", nil)
	reposReq.Header.Set("Cookie", cookie)
	reposRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(reposRec, reposReq)
	if reposRec.Code != http.StatusOK {
		t.Fatalf("repos: %d %s", reposRec.Code, reposRec.Body.String())
	}
	if !strings.Contains(reposRec.Body.String(), `"full_name":"boringdata/boring-ui"`) {
		t.Fatalf("expected repos list, got %s", reposRec.Body.String())
	}

	selectRepoReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/github/repo", strings.NewReader(`{"workspace_id":"`+workspaceID+`","repo_url":"https://github.com/boringdata/boring-ui.git"}`))
	selectRepoReq.Header.Set("Cookie", cookie)
	selectRepoReq.Header.Set("Content-Type", "application/json")
	selectRepoRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(selectRepoRec, selectRepoReq)
	if selectRepoRec.Code != http.StatusOK {
		t.Fatalf("select repo: %d %s", selectRepoRec.Code, selectRepoRec.Body.String())
	}

	credentialsReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/git-credentials?workspace_id="+workspaceID, nil)
	credentialsReq.Header.Set("Cookie", cookie)
	credentialsRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(credentialsRec, credentialsReq)
	if credentialsRec.Code != http.StatusOK {
		t.Fatalf("credentials: %d %s", credentialsRec.Code, credentialsRec.Body.String())
	}
	if credentialsRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store credentials response, got %q", credentialsRec.Header().Get("Cache-Control"))
	}
	if !strings.Contains(credentialsRec.Body.String(), `"username":"x-access-token"`) || !strings.Contains(credentialsRec.Body.String(), `"password":"inst-token-`) {
		t.Fatalf("expected credentials payload, got %s", credentialsRec.Body.String())
	}

	disconnectReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/github/disconnect", strings.NewReader(`{"workspace_id":"`+workspaceID+`"}`))
	disconnectReq.Header.Set("Cookie", cookie)
	disconnectReq.Header.Set("Content-Type", "application/json")
	disconnectRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(disconnectRec, disconnectReq)
	if disconnectRec.Code != http.StatusOK {
		t.Fatalf("disconnect: %d %s", disconnectRec.Code, disconnectRec.Body.String())
	}
}

func TestInstallationTokenCacheRefreshesAfterTTL(t *testing.T) {
	baseURL, apiURL, accessTokenCalls := newGitHubAPIServer(t)
	service, err := newAppService(appConfig{
		AppID:         "12345",
		ClientID:      "client-123",
		ClientSecret:  "secret-456",
		PrivateKeyPEM: newRSAPrivateKeyPEM(t),
		AppSlug:       "boring-ui-app",
		BaseURL:       baseURL,
		APIBaseURL:    apiURL,
	})
	if err != nil {
		t.Fatalf("new service: %v", err)
	}

	now := time.Date(2026, 3, 16, 9, 0, 0, 0, time.UTC)
	service.now = func() time.Time { return now }

	tokenOne, err := service.installationToken(context.Background(), 99)
	if err != nil {
		t.Fatalf("first token: %v", err)
	}
	if tokenOne != "inst-token-1" {
		t.Fatalf("expected first token, got %q", tokenOne)
	}

	tokenTwo, err := service.installationToken(context.Background(), 99)
	if err != nil {
		t.Fatalf("second token: %v", err)
	}
	if tokenTwo != tokenOne {
		t.Fatalf("expected cached token, got %q vs %q", tokenTwo, tokenOne)
	}

	now = now.Add(11 * time.Minute)
	tokenThree, err := service.installationToken(context.Background(), 99)
	if err != nil {
		t.Fatalf("third token: %v", err)
	}
	if tokenThree == tokenOne {
		t.Fatalf("expected refreshed token after ttl, got %q", tokenThree)
	}
	if got := atomic.LoadInt32(accessTokenCalls); got != 2 {
		t.Fatalf("expected 2 installation token fetches, got %d", got)
	}
}

func TestGitHubCallbackWithoutParamsReturnsHTML(t *testing.T) {
	baseURL, apiURL, _ := newGitHubAPIServer(t)
	cfg := newGitHubTestConfig(t)

	t.Setenv("GITHUB_APP_ID", "12345")
	t.Setenv("GITHUB_APP_CLIENT_ID", "client-123")
	t.Setenv("GITHUB_APP_CLIENT_SECRET", "secret-456")
	t.Setenv("GITHUB_APP_PRIVATE_KEY", newRSAPrivateKeyPEM(t))
	t.Setenv("GITHUB_BASE_URL", baseURL)
	t.Setenv("GITHUB_API_BASE_URL", apiURL)

	instance := newGitHubApp(t, cfg)
	cookie := issueSession(t, instance, "user-1", "owner@example.com")
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/callback", nil)
	req.Header.Set("Cookie", cookie)
	rec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected html callback placeholder, got %d %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Header().Get("Content-Type"), "text/html") {
		t.Fatalf("expected text/html callback response, got %q", rec.Header().Get("Content-Type"))
	}
	if !strings.Contains(rec.Body.String(), "Missing code or installation_id") {
		t.Fatalf("expected missing callback placeholder, got %s", rec.Body.String())
	}
}

func TestGitHubInstallationsDoesNotRequireLinkedAccount(t *testing.T) {
	baseURL, apiURL, _ := newGitHubAPIServer(t)
	cfg := newGitHubTestConfig(t)

	t.Setenv("GITHUB_APP_ID", "12345")
	t.Setenv("GITHUB_APP_CLIENT_ID", "client-123")
	t.Setenv("GITHUB_APP_CLIENT_SECRET", "secret-456")
	t.Setenv("GITHUB_APP_PRIVATE_KEY", newRSAPrivateKeyPEM(t))
	t.Setenv("GITHUB_BASE_URL", baseURL)
	t.Setenv("GITHUB_API_BASE_URL", apiURL)

	instance := newGitHubApp(t, cfg)
	cookie := issueSession(t, instance, "user-1", "owner@example.com")
	req := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/installations", nil)
	req.Header.Set("Cookie", cookie)
	rec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected installations 200 for an authenticated user without a linked account, got %d %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"id":99`) {
		t.Fatalf("expected installation listing, got %s", rec.Body.String())
	}
}

func TestGitHubWorkspaceRoutesHideWorkspaceFromNonMembers(t *testing.T) {
	baseURL, apiURL, _ := newGitHubAPIServer(t)
	cfg := newGitHubTestConfig(t)

	t.Setenv("GITHUB_APP_ID", "12345")
	t.Setenv("GITHUB_APP_CLIENT_ID", "client-123")
	t.Setenv("GITHUB_APP_CLIENT_SECRET", "secret-456")
	t.Setenv("GITHUB_APP_PRIVATE_KEY", newRSAPrivateKeyPEM(t))
	t.Setenv("GITHUB_BASE_URL", baseURL)
	t.Setenv("GITHUB_API_BASE_URL", apiURL)

	instance := newGitHubApp(t, cfg)
	ownerCookie := issueSession(t, instance, "user-owner", "owner@example.com")
	outsiderCookie := issueSession(t, instance, "user-outsider", "outsider@example.com")

	createWorkspaceReq := httptest.NewRequest(http.MethodPost, "/api/v1/workspaces", strings.NewReader(`{"name":"GitHub"}`))
	createWorkspaceReq.Header.Set("Cookie", ownerCookie)
	createWorkspaceRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(createWorkspaceRec, createWorkspaceReq)
	if createWorkspaceRec.Code != http.StatusCreated {
		t.Fatalf("create workspace: %d %s", createWorkspaceRec.Code, createWorkspaceRec.Body.String())
	}
	workspaceID := extractJSONField(t, createWorkspaceRec.Body.String(), `"id":"`, `"`)

	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/status?workspace_id="+workspaceID, nil)
	statusReq.Header.Set("Cookie", outsiderCookie)
	statusRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(statusRec, statusReq)
	if statusRec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for outsider status, got %d: %s", statusRec.Code, statusRec.Body.String())
	}

	connectReq := httptest.NewRequest(http.MethodPost, "/api/v1/auth/github/connect", strings.NewReader(`{"workspace_id":"`+workspaceID+`","installation_id":99}`))
	connectReq.Header.Set("Cookie", outsiderCookie)
	connectReq.Header.Set("Content-Type", "application/json")
	connectRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(connectRec, connectReq)
	if connectRec.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for outsider connect, got %d: %s", connectRec.Code, connectRec.Body.String())
	}
}

func TestGitHubCallbackRejectsInvalidStateAndHandlesInstallFlow(t *testing.T) {
	baseURL, apiURL, _ := newGitHubAPIServer(t)
	cfg := newGitHubTestConfig(t)

	t.Setenv("GITHUB_APP_ID", "12345")
	t.Setenv("GITHUB_APP_CLIENT_ID", "client-123")
	t.Setenv("GITHUB_APP_CLIENT_SECRET", "secret-456")
	t.Setenv("GITHUB_APP_PRIVATE_KEY", newRSAPrivateKeyPEM(t))
	t.Setenv("GITHUB_APP_SLUG", "boring-ui-app")
	t.Setenv("GITHUB_BASE_URL", baseURL)
	t.Setenv("GITHUB_API_BASE_URL", apiURL)

	instance := newGitHubApp(t, cfg)
	cookie := issueSession(t, instance, "user-1", "owner@example.com")

	createWorkspaceReq := httptest.NewRequest(http.MethodPost, "/api/v1/workspaces", strings.NewReader(`{"name":"GitHub"}`))
	createWorkspaceReq.Header.Set("Cookie", cookie)
	createWorkspaceRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(createWorkspaceRec, createWorkspaceReq)
	workspaceID := extractJSONField(t, createWorkspaceRec.Body.String(), `"id":"`, `"`)

	invalidStateReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/callback?code=test-code&state=bad-state", nil)
	invalidStateReq.Header.Set("Cookie", cookie)
	invalidStateRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(invalidStateRec, invalidStateReq)
	if invalidStateRec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for invalid state, got %d: %s", invalidStateRec.Code, invalidStateRec.Body.String())
	}

	authorizeReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/authorize?workspace_id="+workspaceID+"&force_install=true", nil)
	authorizeReq.Header.Set("Cookie", cookie)
	authorizeRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(authorizeRec, authorizeReq)
	if authorizeRec.Code != http.StatusTemporaryRedirect && authorizeRec.Code != http.StatusFound {
		t.Fatalf("force install authorize: %d %s", authorizeRec.Code, authorizeRec.Body.String())
	}
	if authorizeRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store on force-install redirect, got %q", authorizeRec.Header().Get("Cache-Control"))
	}
	if authorizeRec.Body.Len() != 0 {
		t.Fatalf("expected empty force-install authorize redirect body, got %q", authorizeRec.Body.String())
	}
	if authorizeRec.Header().Get("Content-Type") != "" {
		t.Fatalf("expected force-install authorize redirect without content type, got %q", authorizeRec.Header().Get("Content-Type"))
	}
	if location := authorizeRec.Header().Get("Location"); !strings.Contains(location, "/apps/boring-ui-app/installations/new") {
		t.Fatalf("expected install redirect, got %q", location)
	}
	installState := extractQueryParam(t, authorizeRec.Header().Get("Location"), "state")

	installCallbackReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/callback?installation_id=99&state="+url.QueryEscape(installState), nil)
	installCallbackReq.Header.Set("Cookie", cookie)
	installCallbackRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(installCallbackRec, installCallbackReq)
	if installCallbackRec.Code != http.StatusOK {
		t.Fatalf("install callback: %d %s", installCallbackRec.Code, installCallbackRec.Body.String())
	}

	statusReq := httptest.NewRequest(http.MethodGet, "/api/v1/auth/github/status?workspace_id="+workspaceID, nil)
	statusReq.Header.Set("Cookie", cookie)
	statusRec := httptest.NewRecorder()
	instance.Handler().ServeHTTP(statusRec, statusReq)
	if statusRec.Code != http.StatusOK {
		t.Fatalf("status after install callback: %d %s", statusRec.Code, statusRec.Body.String())
	}
	if !strings.Contains(statusRec.Body.String(), `"installation_id":99`) {
		t.Fatalf("expected installation id in status after install callback, got %s", statusRec.Body.String())
	}
}

func TestGitHubPendingStateInsertPrunesExpiredEntries(t *testing.T) {
	module := &Module{
		pendingStates: map[string]pendingState{
			"expired": {UserID: "user-1", CreatedAt: time.Date(2026, 3, 16, 10, 0, 0, 0, time.UTC)},
		},
	}
	module.service = &appService{now: func() time.Time { return time.Date(2026, 3, 16, 10, 11, 0, 0, time.UTC) }}

	key, err := module.newPendingState(pendingState{UserID: "user-1", CreatedAt: module.service.now()})
	if err != nil {
		t.Fatalf("new pending state: %v", err)
	}
	if _, ok := module.pendingStates["expired"]; ok {
		t.Fatalf("expected expired pending state to be pruned")
	}
	if _, ok := module.pendingStates[key]; !ok {
		t.Fatalf("expected new pending state %q to be recorded", key)
	}
}

func newGitHubApp(t *testing.T, cfg config.Config) *apppkg.App {
	t.Helper()
	t.Setenv("DATABASE_URL", "")
	t.Setenv("BORING_SETTINGS_KEY", "")

	instance := apppkg.New(cfg)
	controlPlaneModule, err := controlplane.NewModule(cfg)
	if err != nil {
		t.Fatalf("new control-plane module: %v", err)
	}
	instance.SetAuthStateBridge(controlPlaneModule)
	instance.AddModule(controlPlaneModule)

	githubModule, err := NewModule(cfg)
	if err != nil {
		t.Fatalf("new github module: %v", err)
	}
	instance.AddModule(githubModule)
	if err := instance.Start(context.Background()); err != nil {
		t.Fatalf("start modules: %v", err)
	}
	t.Cleanup(func() {
		_ = instance.Stop(context.Background())
	})
	return instance
}

func newGitHubTestConfig(t *testing.T) config.Config {
	t.Helper()
	root := t.TempDir()
	return config.Config{ConfigPath: filepath.Join(root, config.ConfigFile)}
}

func issueSession(t *testing.T, instance *apppkg.App, userID, email string) string {
	t.Helper()
	token, err := instance.SessionManager().Create(auth.User{
		ID:      userID,
		Email:   email,
		IsOwner: true,
	})
	if err != nil {
		t.Fatalf("create session: %v", err)
	}
	return "boring_session=" + token
}

func extractJSONField(t *testing.T, body, prefix, suffix string) string {
	t.Helper()
	start := strings.Index(body, prefix)
	if start == -1 {
		t.Fatalf("prefix %q not found in %s", prefix, body)
	}
	start += len(prefix)
	end := strings.Index(body[start:], suffix)
	if end == -1 {
		t.Fatalf("suffix %q not found in %s", suffix, body)
	}
	return body[start : start+end]
}

func extractQueryParam(t *testing.T, rawURL, key string) string {
	t.Helper()
	parsed, err := url.Parse(rawURL)
	if err != nil {
		t.Fatalf("parse url %q: %v", rawURL, err)
	}
	value := strings.TrimSpace(parsed.Query().Get(key))
	if value == "" {
		t.Fatalf("query param %q missing from %q", key, rawURL)
	}
	return value
}

func newGitHubAPIServer(t *testing.T) (string, string, *int32) {
	t.Helper()
	var accessTokenCalls int32

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		switch {
		case req.Method == http.MethodPost && req.URL.Path == "/login/oauth/access_token":
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `{"access_token":"user-token-1"}`)
		case req.Method == http.MethodGet && req.URL.Path == "/app/installations":
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `[{"id":99,"account":{"login":"boringdata","type":"Organization"}}]`)
		case req.Method == http.MethodGet && req.URL.Path == "/user/installations":
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `{"installations":[{"id":99,"account":{"login":"boringdata","type":"Organization"}}]}`)
		case req.Method == http.MethodPost && req.URL.Path == "/app/installations/99/access_tokens":
			call := atomic.AddInt32(&accessTokenCalls, 1)
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `{"token":"inst-token-`+strconv.Itoa(int(call))+`","expires_at":"2030-03-16T10:30:00Z"}`)
		case req.Method == http.MethodGet && req.URL.Path == "/installation/repositories":
			w.Header().Set("Content-Type", "application/json")
			_, _ = io.WriteString(w, `{"repositories":[{"full_name":"boringdata/boring-ui","clone_url":"https://github.com/boringdata/boring-ui.git","private":true}]}`)
		default:
			http.NotFound(w, req)
		}
	}))
	t.Cleanup(server.Close)
	return server.URL, server.URL, &accessTokenCalls
}

func newRSAPrivateKeyPEM(t *testing.T) string {
	t.Helper()
	privateKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("generate rsa key: %v", err)
	}
	return string(pem.EncodeToMemory(&pem.Block{
		Type:  "RSA PRIVATE KEY",
		Bytes: x509.MarshalPKCS1PrivateKey(privateKey),
	}))
}
