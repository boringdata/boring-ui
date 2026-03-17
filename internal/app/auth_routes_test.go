package app

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
	"github.com/golang-jwt/jwt/v5"
)

func TestCapabilitiesEndpointListsModulesWithoutAuth(t *testing.T) {
	app := New(config.Config{})
	app.AddModule(testModule{})

	req := httptest.NewRequest(http.MethodGet, "/api/capabilities", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"routers":[`) {
		t.Fatalf("expected routers metadata, got %s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"features":{"`) {
		t.Fatalf("expected python-style features payload, got %s", rec.Body.String())
	}
}

func TestConfigEndpointReturnsWorkspaceRootWithoutAuth(t *testing.T) {
	dir := t.TempDir()
	app := New(config.Config{ConfigPath: filepath.Join(dir, config.ConfigFile)})

	req := httptest.NewRequest(http.MethodGet, "/api/config", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), dir) {
		t.Fatalf("expected workspace root %q in response, got %s", dir, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"pty_providers":["claude","shell"]`) {
		t.Fatalf("expected default PTY providers in response, got %s", rec.Body.String())
	}
}

func TestHealthAndProjectEndpointsReturnPythonShape(t *testing.T) {
	dir := t.TempDir()
	app := New(config.Config{ConfigPath: filepath.Join(dir, config.ConfigFile)})

	healthReq := httptest.NewRequest(http.MethodGet, "/health", nil)
	healthRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(healthRec, healthReq)
	if healthRec.Code != http.StatusOK {
		t.Fatalf("expected health 200, got %d", healthRec.Code)
	}
	if !strings.Contains(healthRec.Body.String(), `"workspace":"`+dir+`"`) || !strings.Contains(healthRec.Body.String(), `"features":{`) {
		t.Fatalf("expected python-style health payload, got %s", healthRec.Body.String())
	}

	projectReq := httptest.NewRequest(http.MethodGet, "/api/project", nil)
	projectRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(projectRec, projectReq)
	if projectRec.Code != http.StatusOK {
		t.Fatalf("expected project 200, got %d", projectRec.Code)
	}
	if !strings.Contains(projectRec.Body.String(), `"root":"`+dir+`"`) {
		t.Fatalf("expected project root payload, got %s", projectRec.Body.String())
	}
}

func TestMeEndpointRequiresCookieAndReturnsSessionUser(t *testing.T) {
	app := New(config.Config{})

	unauthorizedReq := httptest.NewRequest(http.MethodGet, "/api/v1/me", nil)
	unauthorizedRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(unauthorizedRec, unauthorizedReq)
	if unauthorizedRec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without cookie, got %d", unauthorizedRec.Code)
	}

	token, err := app.auth.Create(auth.User{
		ID:      "user-123",
		Email:   "user@example.com",
		IsOwner: true,
	})
	if err != nil {
		t.Fatalf("create token: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/v1/me", nil)
	req.AddCookie(&http.Cookie{Name: app.auth.CookieName(), Value: token})
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"user_id":"user-123"`) {
		t.Fatalf("expected user id in payload, got %s", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"email":"user@example.com"`) {
		t.Fatalf("expected email in payload, got %s", rec.Body.String())
	}
}

func TestAuthLoginSessionAndLogoutLifecycle(t *testing.T) {
	t.Setenv("DEV_AUTOLOGIN", "1")
	t.Setenv("BORING_UI_SESSION_SECRET", "test-secret")
	t.Setenv("BORING_SESSION_SECRET", "test-secret")

	app := New(config.Config{})

	loginReq := httptest.NewRequest(http.MethodGet, "/auth/login?user_id=dev-user-1&email=Dev@Example.com&redirect_uri=/workspace", nil)
	loginRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(loginRec, loginReq)

	if loginRec.Code != http.StatusFound {
		t.Fatalf("expected 302 from login, got %d", loginRec.Code)
	}
	if loginRec.Header().Get("Location") != "/workspace" {
		t.Fatalf("expected redirect to /workspace, got %q", loginRec.Header().Get("Location"))
	}
	if loginRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store on login redirect, got %q", loginRec.Header().Get("Cache-Control"))
	}
	if loginRec.Body.Len() != 0 {
		t.Fatalf("expected empty redirect body, got %q", loginRec.Body.String())
	}
	if loginRec.Header().Get("Content-Type") != "" {
		t.Fatalf("expected redirect without content type, got %q", loginRec.Header().Get("Content-Type"))
	}
	cookieHeader := loginRec.Header().Get("Set-Cookie")
	if !strings.Contains(cookieHeader, "boring_session=") {
		t.Fatalf("expected session cookie, got %q", cookieHeader)
	}
	if !strings.Contains(cookieHeader, "HttpOnly") || !strings.Contains(cookieHeader, "SameSite=Lax") {
		t.Fatalf("expected session cookie flags, got %q", cookieHeader)
	}

	callbackReq := httptest.NewRequest(http.MethodGet, "/auth/callback?user_id=dev-user-1&email=Dev@Example.com&redirect_uri=/callback", nil)
	callbackRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(callbackRec, callbackReq)
	if callbackRec.Code != http.StatusFound || callbackRec.Header().Get("Location") != "/callback" {
		t.Fatalf("expected callback redirect, got status=%d location=%q", callbackRec.Code, callbackRec.Header().Get("Location"))
	}
	if callbackRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store on callback redirect, got %q", callbackRec.Header().Get("Cache-Control"))
	}
	if callbackRec.Body.Len() != 0 {
		t.Fatalf("expected empty callback redirect body, got %q", callbackRec.Body.String())
	}
	if callbackRec.Header().Get("Content-Type") != "" {
		t.Fatalf("expected callback redirect without content type, got %q", callbackRec.Header().Get("Content-Type"))
	}

	sessionReq := httptest.NewRequest(http.MethodGet, "/auth/session", nil)
	sessionReq.Header.Set("Cookie", cookieHeader)
	sessionRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(sessionRec, sessionReq)

	if sessionRec.Code != http.StatusOK {
		t.Fatalf("expected 200 from session, got %d", sessionRec.Code)
	}
	if !strings.Contains(sessionRec.Body.String(), `"authenticated":true`) {
		t.Fatalf("expected authenticated response, got %s", sessionRec.Body.String())
	}
	if !strings.Contains(sessionRec.Body.String(), `"user_id":"dev-user-1"`) {
		t.Fatalf("expected dev user in session payload, got %s", sessionRec.Body.String())
	}

	logoutReq := httptest.NewRequest(http.MethodGet, "/auth/logout", nil)
	logoutReq.Header.Set("Cookie", cookieHeader)
	logoutRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(logoutRec, logoutReq)

	if logoutRec.Code != http.StatusFound {
		t.Fatalf("expected 302 from logout, got %d", logoutRec.Code)
	}
	if logoutRec.Header().Get("Location") != "/auth/login" {
		t.Fatalf("expected redirect to /auth/login, got %q", logoutRec.Header().Get("Location"))
	}
	if logoutRec.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("expected no-store on logout redirect, got %q", logoutRec.Header().Get("Cache-Control"))
	}
	if logoutRec.Body.Len() != 0 {
		t.Fatalf("expected empty logout redirect body, got %q", logoutRec.Body.String())
	}
	if logoutRec.Header().Get("Content-Type") != "" {
		t.Fatalf("expected logout redirect without content type, got %q", logoutRec.Header().Get("Content-Type"))
	}
	if !strings.Contains(logoutRec.Header().Get("Set-Cookie"), "Max-Age=0") && !strings.Contains(logoutRec.Header().Get("Set-Cookie"), "Max-Age=-1") {
		t.Fatalf("expected cookie clearing header, got %q", logoutRec.Header().Get("Set-Cookie"))
	}
}

func TestAuthLoginGetRequiresIdentityQueryParams(t *testing.T) {
	t.Setenv("DEV_AUTOLOGIN", "1")
	app := New(config.Config{})

	req := httptest.NewRequest(http.MethodGet, "/auth/login?redirect_uri=/", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for missing login identity, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"code":"LOGIN_IDENTITY_REQUIRED"`) {
		t.Fatalf("expected identity-required error, got %s", rec.Body.String())
	}
}

func TestAuthLoginGetRequiresDevAutologin(t *testing.T) {
	app := New(config.Config{})

	req := httptest.NewRequest(http.MethodGet, "/auth/login?user_id=dev-user-1&email=dev@example.com&redirect_uri=/", nil)
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("expected 501 when DEV_AUTOLOGIN is disabled, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"code":"LOGIN_NOT_CONFIGURED"`) {
		t.Fatalf("expected login-not-configured error, got %s", rec.Body.String())
	}
}

func TestAuthPostLoginAndPostLogoutLifecycle(t *testing.T) {
	t.Setenv("DEV_AUTOLOGIN", "1")
	t.Setenv("AUTH_DEV_USER_ID", "dev-user-2")
	t.Setenv("AUTH_DEV_EMAIL", "owner@example.com")
	t.Setenv("BORING_UI_SESSION_SECRET", "test-secret")
	t.Setenv("BORING_SESSION_SECRET", "test-secret")

	app := New(config.Config{})

	loginReq := httptest.NewRequest(http.MethodPost, "/auth/login", bytes.NewBufferString(`{"redirect_uri":"/"}`))
	loginRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(loginRec, loginReq)

	if loginRec.Code != http.StatusOK {
		t.Fatalf("expected 200 from post login, got %d", loginRec.Code)
	}
	if !strings.Contains(loginRec.Header().Get("Set-Cookie"), "boring_session=") {
		t.Fatalf("expected session cookie header, got %q", loginRec.Header().Get("Set-Cookie"))
	}
	if !strings.Contains(loginRec.Body.String(), `"authenticated":true`) {
		t.Fatalf("expected authenticated JSON payload, got %s", loginRec.Body.String())
	}

	logoutReq := httptest.NewRequest(http.MethodPost, "/auth/logout", nil)
	logoutRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(logoutRec, logoutReq)

	if logoutRec.Code != http.StatusOK {
		t.Fatalf("expected 200 from post logout, got %d", logoutRec.Code)
	}
	if !strings.Contains(logoutRec.Body.String(), `"ok":true`) {
		t.Fatalf("expected ok payload, got %s", logoutRec.Body.String())
	}
	if !strings.Contains(logoutRec.Header().Get("Set-Cookie"), "boring_session=") {
		t.Fatalf("expected cookie clearing header, got %q", logoutRec.Header().Get("Set-Cookie"))
	}
}

func TestAuthTokenExchangeSetsSessionCookieFromNeonJWT(t *testing.T) {
	t.Setenv("BORING_UI_SESSION_SECRET", "test-secret")

	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("generate Ed25519 keypair: %v", err)
	}
	jwksServer := newRouteTestJWKS(t, "kid-route-1", publicKey)
	defer jwksServer.Close()

	now := time.Date(2026, 3, 16, 9, 0, 0, 0, time.UTC)
	app := New(config.Config{
		Deploy: config.Deploy{
			Neon: config.NeonConfig{
				AuthURL: "https://example.neonauth.test/neondb/auth",
				JWKSURL: jwksServer.URL,
			},
		},
	})
	app.tokenVerifier = auth.NewTokenVerifier(auth.TokenVerifierConfig{
		SessionSecret: "test-secret",
		NeonBaseURL:   "https://example.neonauth.test/neondb/auth",
		NeonJWKSURL:   jwksServer.URL,
		Now:           func() time.Time { return now },
	})

	token := signRouteTestEdDSAToken(t, privateKey, "kid-route-1", "https://example.neonauth.test", now.Add(time.Hour))
	req := httptest.NewRequest(http.MethodPost, "/auth/token-exchange", bytes.NewBufferString(`{"access_token":"`+token+`","redirect_uri":"/w/demo"}`))
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Header().Get("Set-Cookie"), "boring_session=") {
		t.Fatalf("expected session cookie on token exchange, got %q", rec.Header().Get("Set-Cookie"))
	}
	if !strings.Contains(rec.Body.String(), `"redirect_uri":"/w/demo"`) {
		t.Fatalf("expected redirect uri in response, got %s", rec.Body.String())
	}

	sessionReq := httptest.NewRequest(http.MethodGet, "/auth/session", nil)
	sessionReq.Header.Set("Cookie", rec.Header().Get("Set-Cookie"))
	sessionRec := httptest.NewRecorder()
	app.Handler().ServeHTTP(sessionRec, sessionReq)

	if sessionRec.Code != http.StatusOK {
		t.Fatalf("expected 200 from session, got %d: %s", sessionRec.Code, sessionRec.Body.String())
	}
	if !strings.Contains(sessionRec.Body.String(), `"user_id":"user-route-1"`) {
		t.Fatalf("expected exchanged user id in session payload, got %s", sessionRec.Body.String())
	}
	if !strings.Contains(sessionRec.Body.String(), `"email":"owner@example.com"`) {
		t.Fatalf("expected exchanged user email in session payload, got %s", sessionRec.Body.String())
	}
}

func TestAuthTokenExchangeRejectsMissingAccessToken(t *testing.T) {
	app := New(config.Config{})

	req := httptest.NewRequest(http.MethodPost, "/auth/token-exchange", bytes.NewBufferString(`{"redirect_uri":"/"}`))
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusBadRequest {
		t.Fatalf("expected 400, got %d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"code":"MISSING_ACCESS_TOKEN"`) {
		t.Fatalf("expected missing token error code, got %s", rec.Body.String())
	}
}

func TestAuthTokenExchangeRejectsInvalidSignature(t *testing.T) {
	t.Setenv("BORING_UI_SESSION_SECRET", "test-secret")

	publicKey, _, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("generate Ed25519 keypair: %v", err)
	}
	_, wrongPrivateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("generate wrong Ed25519 keypair: %v", err)
	}
	jwksServer := newRouteTestJWKS(t, "kid-route-2", publicKey)
	defer jwksServer.Close()

	now := time.Date(2026, 3, 16, 9, 15, 0, 0, time.UTC)
	app := New(config.Config{
		Deploy: config.Deploy{
			Neon: config.NeonConfig{
				AuthURL: "https://example.neonauth.test/neondb/auth",
				JWKSURL: jwksServer.URL,
			},
		},
	})
	app.tokenVerifier = auth.NewTokenVerifier(auth.TokenVerifierConfig{
		SessionSecret: "test-secret",
		NeonBaseURL:   "https://example.neonauth.test/neondb/auth",
		NeonJWKSURL:   jwksServer.URL,
		Now:           func() time.Time { return now },
	})

	token := signRouteTestEdDSAToken(t, wrongPrivateKey, "kid-route-2", "https://example.neonauth.test", now.Add(time.Hour))
	req := httptest.NewRequest(http.MethodPost, "/auth/token-exchange", bytes.NewBufferString(`{"access_token":"`+token+`","redirect_uri":"/"}`))
	rec := httptest.NewRecorder()
	app.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d: %s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"code":"INVALID_ACCESS_TOKEN"`) {
		t.Fatalf("expected invalid token code, got %s", rec.Body.String())
	}
}

func newRouteTestJWKS(t *testing.T, kid string, publicKey ed25519.PublicKey) *httptest.Server {
	t.Helper()

	var hits int32
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		atomic.AddInt32(&hits, 1)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"keys": []map[string]string{
				{
					"kty": "OKP",
					"crv": "Ed25519",
					"alg": "EdDSA",
					"kid": kid,
					"x":   base64.RawURLEncoding.EncodeToString(publicKey),
				},
			},
		})
	}))
}

func signRouteTestEdDSAToken(t *testing.T, privateKey ed25519.PrivateKey, kid, audience string, expiresAt time.Time) string {
	t.Helper()

	token := jwt.NewWithClaims(jwt.SigningMethodEdDSA, jwt.MapClaims{
		"sub":   "user-route-1",
		"email": "owner@example.com",
		"aud":   audience,
		"exp":   expiresAt.Unix(),
	})
	token.Header["kid"] = kid

	raw, err := token.SignedString(privateKey)
	if err != nil {
		t.Fatalf("sign EdDSA token: %v", err)
	}
	return raw
}
