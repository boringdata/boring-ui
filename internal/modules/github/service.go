package github

import (
	"bytes"
	"context"
	"crypto/rsa"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

const (
	defaultGitHubBaseURL = "https://github.com"
	defaultGitHubAPIURL  = "https://api.github.com"
	tokenCacheTTL        = 10 * time.Minute
	tokenRefreshSkew     = 30 * time.Second
)

type installationToken struct {
	Token     string
	ExpiresAt time.Time
	CachedAt  time.Time
}

type appConfig struct {
	AppID         string
	ClientID      string
	ClientSecret  string
	PrivateKeyPEM string
	AppSlug       string
	BaseURL       string
	APIBaseURL    string
}

type appService struct {
	cfg        appConfig
	httpClient *http.Client
	now        func() time.Time

	mu         sync.Mutex
	privateKey *rsa.PrivateKey
	cache      map[int64]installationToken
}

func newAppService(cfg appConfig) (*appService, error) {
	service := &appService{
		cfg: cfg,
		httpClient: &http.Client{
			Timeout: 15 * time.Second,
		},
		now:   time.Now,
		cache: map[int64]installationToken{},
	}

	if strings.TrimSpace(cfg.PrivateKeyPEM) != "" {
		privateKey, err := jwt.ParseRSAPrivateKeyFromPEM([]byte(cfg.PrivateKeyPEM))
		if err != nil {
			return nil, fmt.Errorf("parse GitHub app private key: %w", err)
		}
		service.privateKey = privateKey
	}
	if strings.TrimSpace(service.cfg.BaseURL) == "" {
		service.cfg.BaseURL = defaultGitHubBaseURL
	}
	if strings.TrimSpace(service.cfg.APIBaseURL) == "" {
		service.cfg.APIBaseURL = defaultGitHubAPIURL
	}
	return service, nil
}

func (s *appService) configured() bool {
	return strings.TrimSpace(s.cfg.AppID) != "" && s.privateKey != nil
}

func (s *appService) canAuthorize() bool {
	return strings.TrimSpace(s.cfg.ClientID) != "" || strings.TrimSpace(s.cfg.AppSlug) != ""
}

func (s *appService) authorizeURL(redirectURI, state string, forceInstall bool) (string, error) {
	baseURL := strings.TrimRight(s.cfg.BaseURL, "/")
	switch {
	case !forceInstall && strings.TrimSpace(s.cfg.ClientID) != "":
		values := url.Values{}
		values.Set("client_id", s.cfg.ClientID)
		values.Set("redirect_uri", redirectURI)
		if strings.TrimSpace(state) != "" {
			values.Set("state", state)
		}
		return baseURL + "/login/oauth/authorize?" + values.Encode(), nil
	case strings.TrimSpace(s.cfg.AppSlug) != "":
		values := url.Values{}
		if strings.TrimSpace(state) != "" {
			values.Set("state", state)
		}
		return baseURL + "/apps/" + url.PathEscape(s.cfg.AppSlug) + "/installations/new?" + values.Encode(), nil
	default:
		return "", fmt.Errorf("github authorization is not configured")
	}
}

func (s *appService) exchangeCode(ctx context.Context, code string) (string, error) {
	payload := map[string]string{
		"client_id":     s.cfg.ClientID,
		"client_secret": s.cfg.ClientSecret,
		"code":          code,
	}
	var response struct {
		AccessToken string `json:"access_token"`
		Error       string `json:"error"`
		Description string `json:"error_description"`
	}
	if err := s.doJSON(ctx, http.MethodPost, strings.TrimRight(s.cfg.BaseURL, "/")+"/login/oauth/access_token", payload, map[string]string{
		"Accept": "application/json",
	}, &response); err != nil {
		return "", err
	}
	if strings.TrimSpace(response.Error) != "" {
		return "", fmt.Errorf("github oauth error: %s", strings.TrimSpace(response.Description))
	}
	if strings.TrimSpace(response.AccessToken) == "" {
		return "", fmt.Errorf("github oauth returned no access token")
	}
	return response.AccessToken, nil
}

func (s *appService) userInstallations(ctx context.Context, accessToken string) ([]map[string]any, error) {
	var response struct {
		Installations []map[string]any `json:"installations"`
	}
	if err := s.doJSON(ctx, http.MethodGet, strings.TrimRight(s.cfg.APIBaseURL, "/")+"/user/installations", nil, map[string]string{
		"Authorization": "Bearer " + accessToken,
		"Accept":        "application/vnd.github+json",
	}, &response); err != nil {
		return nil, err
	}
	return response.Installations, nil
}

func (s *appService) listInstallations(ctx context.Context) ([]map[string]any, error) {
	appJWT, err := s.appJWT()
	if err != nil {
		return nil, err
	}
	var response []map[string]any
	if err := s.doJSON(ctx, http.MethodGet, strings.TrimRight(s.cfg.APIBaseURL, "/")+"/app/installations", nil, map[string]string{
		"Authorization": "Bearer " + appJWT,
		"Accept":        "application/vnd.github+json",
	}, &response); err != nil {
		return nil, err
	}
	return response, nil
}

func (s *appService) repositories(ctx context.Context, installationID int64) ([]map[string]any, error) {
	token, err := s.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	var response struct {
		Repositories []map[string]any `json:"repositories"`
	}
	if err := s.doJSON(ctx, http.MethodGet, strings.TrimRight(s.cfg.APIBaseURL, "/")+"/installation/repositories", nil, map[string]string{
		"Authorization": "Bearer " + token,
		"Accept":        "application/vnd.github+json",
	}, &response); err != nil {
		return nil, err
	}
	return response.Repositories, nil
}

func (s *appService) gitCredentials(ctx context.Context, installationID int64) (map[string]any, error) {
	token, err := s.installationToken(ctx, installationID)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"username": "x-access-token",
		"password": token,
		"token":    token,
	}, nil
}

func (s *appService) installationToken(ctx context.Context, installationID int64) (string, error) {
	now := s.now()
	s.mu.Lock()
	if cached, ok := s.cache[installationID]; ok {
		cacheExpiry := cached.CachedAt.Add(tokenCacheTTL)
		if cached.ExpiresAt.Before(cacheExpiry) {
			cacheExpiry = cached.ExpiresAt
		}
		if now.Add(tokenRefreshSkew).Before(cacheExpiry) {
			s.mu.Unlock()
			return cached.Token, nil
		}
	}
	s.mu.Unlock()

	appJWT, err := s.appJWT()
	if err != nil {
		return "", err
	}

	var response struct {
		Token     string `json:"token"`
		ExpiresAt string `json:"expires_at"`
	}
	endpoint := fmt.Sprintf("%s/app/installations/%d/access_tokens", strings.TrimRight(s.cfg.APIBaseURL, "/"), installationID)
	if err := s.doJSON(ctx, http.MethodPost, endpoint, nil, map[string]string{
		"Authorization": "Bearer " + appJWT,
		"Accept":        "application/vnd.github+json",
	}, &response); err != nil {
		return "", err
	}
	if strings.TrimSpace(response.Token) == "" {
		return "", fmt.Errorf("github installation token response missing token")
	}

	expiresAt, err := time.Parse(time.RFC3339, response.ExpiresAt)
	if err != nil {
		return "", fmt.Errorf("parse github installation token expiry: %w", err)
	}

	s.mu.Lock()
	s.cache[installationID] = installationToken{
		Token:     response.Token,
		ExpiresAt: expiresAt,
		CachedAt:  now,
	}
	s.mu.Unlock()
	return response.Token, nil
}

func (s *appService) appJWT() (string, error) {
	if !s.configured() {
		return "", fmt.Errorf("github app is not configured")
	}
	now := s.now()
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, jwt.MapClaims{
		"iat": now.Add(-1 * time.Minute).Unix(),
		"exp": now.Add(10 * time.Minute).Unix(),
		"iss": strings.TrimSpace(s.cfg.AppID),
	})
	signed, err := token.SignedString(s.privateKey)
	if err != nil {
		return "", fmt.Errorf("sign github app jwt: %w", err)
	}
	return signed, nil
}

func (s *appService) doJSON(ctx context.Context, method, endpoint string, body any, headers map[string]string, out any) error {
	var reader io.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(payload)
	}

	req, err := http.NewRequestWithContext(ctx, method, endpoint, reader)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= http.StatusBadRequest {
		raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
		return fmt.Errorf("github api %s %s failed: %d %s", method, endpoint, resp.StatusCode, strings.TrimSpace(string(raw)))
	}
	if out == nil {
		return nil
	}
	return json.NewDecoder(resp.Body).Decode(out)
}

func parseInstallationID(value any) (int64, error) {
	switch typed := value.(type) {
	case int:
		return int64(typed), nil
	case int64:
		return typed, nil
	case float64:
		return int64(typed), nil
	case json.Number:
		return typed.Int64()
	case string:
		trimmed := strings.TrimSpace(typed)
		if trimmed == "" {
			return 0, fmt.Errorf("installation_id is required")
		}
		return strconv.ParseInt(trimmed, 10, 64)
	default:
		return 0, fmt.Errorf("installation_id is required")
	}
}
