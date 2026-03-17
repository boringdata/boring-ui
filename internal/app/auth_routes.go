package app

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"

	"github.com/boringdata/boring-ui/internal/auth"
)

type loginRequest struct {
	Email       string `json:"email"`
	Password    string `json:"password"`
	RedirectURI string `json:"redirect_uri"`
}

func (a *App) handleCallbackRedirect(w http.ResponseWriter, req *http.Request) {
	a.handleSessionRedirect(w, req)
}

func (a *App) handleMe(w http.ResponseWriter, req *http.Request) {
	authCtx, ok := auth.ContextFromRequest(req)
	if !ok {
		writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", "SESSION_REQUIRED", "No active session")
		return
	}

	if a.authState != nil {
		payload, err := a.authState.BuildMePayload(req.Context(), authCtx)
		if err != nil {
			writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "ME_LOOKUP_FAILED", "Unable to load current user")
			return
		}
		writeJSON(w, http.StatusOK, payload)
		return
	}

	payload := map[string]any{
		"user_id":      authCtx.UserID,
		"email":        authCtx.Email,
		"display_name": "",
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":           true,
		"user":         payload,
		"me":           payload,
		"data":         payload,
		"user_id":      payload["user_id"],
		"email":        payload["email"],
		"display_name": payload["display_name"],
	})
}

func (a *App) handleLoginRedirect(w http.ResponseWriter, req *http.Request) {
	a.handleSessionRedirect(w, req)
}

func (a *App) handleSessionRedirect(w http.ResponseWriter, req *http.Request) {
	userID := strings.TrimSpace(req.URL.Query().Get("user_id"))
	email := strings.ToLower(strings.TrimSpace(req.URL.Query().Get("email")))
	if userID == "" || email == "" {
		writeAPIError(w, req, http.StatusBadRequest, "bad_request", "LOGIN_IDENTITY_REQUIRED", "user_id and email query params are required")
		return
	}
	if !devAutoLoginEnabled() {
		writeAPIError(w, req, http.StatusNotImplemented, "not_implemented", "LOGIN_NOT_CONFIGURED", "Local auto-login is disabled; set DEV_AUTOLOGIN=1")
		return
	}

	user := auth.User{
		ID:      userID,
		Email:   email,
		IsOwner: true,
	}
	if a.authState != nil {
		if err := a.authState.OnAuthenticated(req.Context(), user); err != nil {
			writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "AUTH_STATE_INIT_FAILED", "Unable to initialize user state")
			return
		}
	}

	if err := a.auth.SetCookie(w, user); err != nil {
		writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "SESSION_CREATE_FAILED", "Unable to create session")
		return
	}

	writeRedirect(w, safeRedirectPath(req.URL.Query().Get("redirect_uri")), http.StatusFound)
}

func (a *App) handleLoginRedirectLegacy(w http.ResponseWriter, req *http.Request) {
	user, err := a.provider.Login(req.Context(), "", "")
	if err != nil {
		if errors.Is(err, auth.ErrInvalidCredentials) {
			writeAPIError(w, req, http.StatusNotImplemented, "not_implemented", "LOGIN_NOT_CONFIGURED", "Local auto-login is disabled; set DEV_AUTOLOGIN=1")
			return
		}
		writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", "LOGIN_FAILED", "Unable to login")
		return
	}

	if a.authState != nil {
		if err := a.authState.OnAuthenticated(req.Context(), *user); err != nil {
			writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "AUTH_STATE_INIT_FAILED", "Unable to initialize user state")
			return
		}
	}

	if err := a.auth.SetCookie(w, *user); err != nil {
		writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "SESSION_CREATE_FAILED", "Unable to create session")
		return
	}

	writeRedirect(w, safeRedirectPath(req.URL.Query().Get("redirect_uri")), http.StatusFound)
}

func (a *App) handleLoginPOST(w http.ResponseWriter, req *http.Request) {
	var body loginRequest
	if err := json.NewDecoder(req.Body).Decode(&body); err != nil && !errors.Is(err, io.EOF) {
		writeAPIError(w, req, http.StatusBadRequest, "bad_request", "INVALID_JSON", "Request body must be valid JSON")
		return
	}

	user, err := a.provider.Login(req.Context(), body.Email, body.Password)
	if err != nil {
		status := http.StatusUnauthorized
		code := "LOGIN_FAILED"
		message := "Unable to login"
		if errors.Is(err, auth.ErrInvalidCredentials) {
			status = http.StatusNotImplemented
			code = "LOGIN_NOT_CONFIGURED"
			message = "Local auto-login is disabled; set DEV_AUTOLOGIN=1"
			writeAPIError(w, req, status, "not_implemented", code, message)
			return
		}
		writeAPIError(w, req, status, "unauthorized", code, message)
		return
	}

	if a.authState != nil {
		if err := a.authState.OnAuthenticated(req.Context(), *user); err != nil {
			writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "AUTH_STATE_INIT_FAILED", "Unable to initialize user state")
			return
		}
	}

	if err := a.auth.SetCookie(w, *user); err != nil {
		writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "SESSION_CREATE_FAILED", "Unable to create session")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"ok":            true,
		"authenticated": true,
		"redirect_uri":  safeRedirectPath(body.RedirectURI),
		"user": map[string]any{
			"user_id": user.ID,
			"email":   user.Email,
		},
	})
}

func (a *App) handleLogoutRedirect(w http.ResponseWriter, req *http.Request) {
	a.auth.ClearCookie(w)
	writeRedirect(w, "/auth/login", http.StatusFound)
}

func (a *App) handleLogoutPOST(w http.ResponseWriter, _ *http.Request) {
	a.auth.ClearCookie(w)
	writeJSON(w, http.StatusOK, map[string]any{"ok": true})
}

func (a *App) handleSession(w http.ResponseWriter, req *http.Request) {
	cookie, err := req.Cookie(a.auth.CookieName())
	if err != nil {
		writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", "SESSION_REQUIRED", "No active session")
		return
	}

	session, err := a.auth.Parse(cookie.Value)
	if err != nil {
		code := "SESSION_INVALID"
		message := "Session invalid"
		if errors.Is(err, auth.ErrSessionExpired) {
			code = "SESSION_EXPIRED"
			message = "Session expired"
		}
		writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", code, message)
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"ok":            true,
		"authenticated": true,
		"user": map[string]any{
			"user_id": session.UserID,
			"email":   session.Email,
		},
		"expires_at": session.ExpiresAt,
	})
}

func (a *App) handleTokenExchange(w http.ResponseWriter, req *http.Request) {
	var body auth.TokenExchangeRequest
	if err := json.NewDecoder(req.Body).Decode(&body); err != nil && !errors.Is(err, io.EOF) {
		writeAPIError(w, req, http.StatusBadRequest, "bad_request", "INVALID_JSON", "Request body must be valid JSON")
		return
	}

	user, err := auth.ExchangeToken(a.tokenVerifier, body.Token())
	if err != nil {
		switch {
		case errors.Is(err, auth.ErrMissingAccessToken):
			writeAPIError(w, req, http.StatusBadRequest, "bad_request", "MISSING_ACCESS_TOKEN", "access_token is required")
		case errors.Is(err, auth.ErrTokenVerifierNotConfigured):
			writeAPIError(w, req, http.StatusInternalServerError, "server_error", "NEON_AUTH_NOT_CONFIGURED", "NEON_AUTH_BASE_URL is not configured")
		case errors.Is(err, auth.ErrTokenVerifierUnavailable):
			writeAPIError(w, req, http.StatusBadGateway, "bad_gateway", "JWKS_UNAVAILABLE", "Unable to verify access token")
		case errors.Is(err, auth.ErrTokenExpired):
			writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", "ACCESS_TOKEN_EXPIRED", "Access token expired")
		default:
			writeAPIError(w, req, http.StatusUnauthorized, "unauthorized", "INVALID_ACCESS_TOKEN", "Access token invalid")
		}
		return
	}

	if a.authState != nil {
		if err := a.authState.OnAuthenticated(req.Context(), user); err != nil {
			writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "AUTH_STATE_INIT_FAILED", "Unable to initialize user state")
			return
		}
	}

	if err := a.auth.SetCookie(w, user); err != nil {
		writeAPIError(w, req, http.StatusInternalServerError, "internal_error", "SESSION_CREATE_FAILED", "Unable to create session")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"ok":           true,
		"redirect_uri": safeRedirectPath(body.RedirectURI),
	})
}

func writeAPIError(w http.ResponseWriter, req *http.Request, status int, errorKind, code, message string) {
	writeJSON(w, status, map[string]any{
		"error":      errorKind,
		"code":       code,
		"detail":     message,
		"message":    message,
		"request_id": requestIDFromContext(req.Context()),
	})
}

func safeRedirectPath(raw string) string {
	candidate := strings.TrimSpace(raw)
	if candidate == "" {
		return "/"
	}
	parsed, err := url.Parse(candidate)
	if err != nil || parsed.Scheme != "" || parsed.Host != "" {
		return "/"
	}
	normalized, err := url.PathUnescape(candidate)
	if err == nil && strings.HasPrefix(normalized, "//") {
		return "/"
	}
	if !strings.HasPrefix(candidate, "/") || strings.HasPrefix(candidate, "//") {
		return "/"
	}
	return candidate
}

func writeRedirect(w http.ResponseWriter, location string, status int) {
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("Location", location)
	w.WriteHeader(status)
}

func devAutoLoginEnabled() bool {
	value := strings.TrimSpace(os.Getenv("DEV_AUTOLOGIN"))
	switch strings.ToLower(value) {
	case "1", "true", "yes", "on":
		return true
	default:
		return false
	}
}
