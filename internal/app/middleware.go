package app

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"log/slog"
	"net"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/boringdata/boring-ui/internal/auth"
	"github.com/boringdata/boring-ui/internal/config"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const requestIDHeader = "X-Request-ID"

type contextKey string

const requestIDContextKey contextKey = "request_id"

type middleware func(http.Handler) http.Handler

type namedMiddleware struct {
	name string
	fn   middleware
}

type APIError struct {
	Status  int
	Code    string
	Message string
}

func (e APIError) Error() string {
	return e.Message
}

type responseRecorder struct {
	http.ResponseWriter
	status int
}

func (r *responseRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func (r *responseRecorder) Status() int {
	if r.status == 0 {
		return http.StatusOK
	}
	return r.status
}

func (r *responseRecorder) Flush() {
	flusher, ok := r.ResponseWriter.(http.Flusher)
	if ok {
		flusher.Flush()
	}
}

func (r *responseRecorder) Hijack() (net.Conn, *bufio.ReadWriter, error) {
	hijacker, ok := r.ResponseWriter.(http.Hijacker)
	if !ok {
		return nil, nil, http.ErrNotSupported
	}
	return hijacker.Hijack()
}

func (r *responseRecorder) Push(target string, opts *http.PushOptions) error {
	pusher, ok := r.ResponseWriter.(http.Pusher)
	if !ok {
		return http.ErrNotSupported
	}
	return pusher.Push(target, opts)
}

type appMetrics struct {
	registry *prometheus.Registry
	requests *prometheus.CounterVec
	duration *prometheus.HistogramVec
}

func newAppMetrics() *appMetrics {
	registry := prometheus.NewRegistry()
	requests := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests handled by the Go backend.",
		},
		[]string{"method", "path", "status"},
	)
	duration := prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path", "status"},
	)
	registry.MustRegister(requests, duration)
	return &appMetrics{
		registry: registry,
		requests: requests,
		duration: duration,
	}
}

func (m *appMetrics) Handler() http.Handler {
	return promhttp.HandlerFor(m.registry, promhttp.HandlerOpts{})
}

func (a *App) wrapMiddlewares(base http.Handler) http.Handler {
	stack := a.middlewareStack()
	handler := base
	for i := len(stack) - 1; i >= 0; i-- {
		handler = stack[i].fn(handler)
	}
	return handler
}

func (a *App) middlewareStack() []namedMiddleware {
	return []namedMiddleware{
		{name: "requestID", fn: requestIDMiddleware()},
		{name: "cors", fn: corsMiddleware(a.cfg)},
		{name: "prometheus", fn: prometheusMiddleware(a.metrics)},
		{name: "slog", fn: slogMiddleware(a.logger)},
		{name: "error", fn: errorMiddleware()},
		{name: "auth", fn: authMiddleware(a.auth)},
	}
}

func requestIDMiddleware() middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			requestID := strings.TrimSpace(req.Header.Get(requestIDHeader))
			if requestID == "" {
				requestID = generateRequestID()
			}

			ctx := context.WithValue(req.Context(), requestIDContextKey, requestID)
			w.Header().Set(requestIDHeader, requestID)
			next.ServeHTTP(w, req.WithContext(ctx))
		})
	}
}

func corsMiddleware(cfg config.Config) middleware {
	allowed := make(map[string]struct{}, len(cfg.CORSOrigins))
	for _, origin := range cfg.CORSOrigins {
		allowed[origin] = struct{}{}
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			origin := strings.TrimSpace(req.Header.Get("Origin"))
			_, ok := allowed[origin]
			if ok {
				w.Header().Set("Access-Control-Allow-Origin", origin)
				w.Header().Set("Vary", "Origin")
				w.Header().Set("Access-Control-Allow-Credentials", "true")
				w.Header().Set("Access-Control-Allow-Headers", "*")
				w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
			}
			if req.Method == http.MethodOptions && ok {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, req)
		})
	}
}

func prometheusMiddleware(metrics *appMetrics) middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			start := time.Now()
			recorder := &responseRecorder{ResponseWriter: w}
			next.ServeHTTP(recorder, req)

			status := fmt.Sprintf("%d", recorder.Status())
			labels := []string{req.Method, req.URL.Path, status}
			metrics.requests.WithLabelValues(labels...).Inc()
			metrics.duration.WithLabelValues(labels...).Observe(time.Since(start).Seconds())
		})
	}
}

func slogMiddleware(logger *slog.Logger) middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			start := time.Now()
			recorder := &responseRecorder{ResponseWriter: w}
			next.ServeHTTP(recorder, req)

			logger.Info(
				"request completed",
				"method", req.Method,
				"path", req.URL.Path,
				"status", recorder.Status(),
				"duration_ms", time.Since(start).Milliseconds(),
				"request_id", requestIDFromContext(req.Context()),
			)
		})
	}
}

func errorMiddleware() middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
			defer func() {
				if recovered := recover(); recovered != nil {
					apiErr := APIError{
						Status:  http.StatusInternalServerError,
						Code:    "internal_error",
						Message: "internal server error",
					}
					switch value := recovered.(type) {
					case APIError:
						apiErr = value
					case *APIError:
						apiErr = *value
					}
					writeJSON(w, apiErr.Status, map[string]string{
						"code":       apiErr.Code,
						"detail":     apiErr.Message,
						"message":    apiErr.Message,
						"request_id": requestIDFromContext(req.Context()),
					})
				}
			}()

			next.ServeHTTP(w, req)
		})
	}
}

func authMiddleware(sessionManager *auth.SessionManager) middleware {
	return auth.NewMiddleware(auth.MiddlewareConfig{
		SessionManager:    sessionManager,
		ProtectedPrefixes: []string{"/api/", "/ws/", "/w/"},
		PublicPaths: []string{
			"/api/capabilities",
			"/api/config",
			"/api/project",
			"/api/v1/auth/github/installations",
		},
	})
}

func requestIDFromContext(ctx context.Context) string {
	value, _ := ctx.Value(requestIDContextKey).(string)
	return value
}

func generateRequestID() string {
	var bytes [16]byte
	if _, err := rand.Read(bytes[:]); err != nil {
		return fmt.Sprintf("req-%d", time.Now().UnixNano())
	}
	return "req-" + hex.EncodeToString(bytes[:])
}

func newRedactingLogger(writer io.Writer) *slog.Logger {
	return slog.New(newRedactingHandler(slog.NewTextHandler(writer, nil)))
}

type redactingHandler struct {
	next slog.Handler
}

func newRedactingHandler(next slog.Handler) slog.Handler {
	return &redactingHandler{next: next}
}

func (h *redactingHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.next.Enabled(ctx, level)
}

func (h *redactingHandler) Handle(ctx context.Context, record slog.Record) error {
	clean := slog.NewRecord(record.Time, record.Level, redactSensitive(record.Message), record.PC)
	record.Attrs(func(attr slog.Attr) bool {
		clean.AddAttrs(redactAttr(attr))
		return true
	})
	return h.next.Handle(ctx, clean)
}

func (h *redactingHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	sanitized := make([]slog.Attr, 0, len(attrs))
	for _, attr := range attrs {
		sanitized = append(sanitized, redactAttr(attr))
	}
	return &redactingHandler{next: h.next.WithAttrs(sanitized)}
}

func (h *redactingHandler) WithGroup(name string) slog.Handler {
	return &redactingHandler{next: h.next.WithGroup(name)}
}

func redactAttr(attr slog.Attr) slog.Attr {
	attr.Value = redactValue(attr.Value)
	return attr
}

func redactValue(value slog.Value) slog.Value {
	switch value.Kind() {
	case slog.KindString:
		return slog.StringValue(redactSensitive(value.String()))
	case slog.KindGroup:
		group := value.Group()
		redacted := make([]slog.Attr, 0, len(group))
		for _, attr := range group {
			redacted = append(redacted, redactAttr(attr))
		}
		return slog.GroupValue(redacted...)
	case slog.KindAny:
		switch raw := value.Any().(type) {
		case string:
			return slog.StringValue(redactSensitive(raw))
		case error:
			return slog.StringValue(redactSensitive(raw.Error()))
		case fmt.Stringer:
			return slog.StringValue(redactSensitive(raw.String()))
		}
	}
	return value
}

var redactPatterns = []*regexp.Regexp{
	regexp.MustCompile(`https?://([^/\s:@]+):([^@\s/]+)@`),
	regexp.MustCompile(`(?i)bearer\s+[A-Za-z0-9._\-+/=]+`),
	regexp.MustCompile(`\bghp_[A-Za-z0-9]+\b`),
	regexp.MustCompile(`\bghs_[A-Za-z0-9]+\b`),
	regexp.MustCompile(`\bsk-[A-Za-z0-9]+\b`),
	regexp.MustCompile(`\bxox[baprs]-[A-Za-z0-9-]+\b`),
	regexp.MustCompile(`(?i)authorization:\s*basic\s+[A-Za-z0-9+/=]+`),
	regexp.MustCompile(`(?i)password=[^\s&]+`),
	regexp.MustCompile(`(?i)passwd=[^\s&]+`),
	regexp.MustCompile(`(?i)token=[^\s&]+`),
	regexp.MustCompile(`(?i)secret=[^\s&]+`),
	regexp.MustCompile(`(?i)api[_-]?key=[^\s&]+`),
	regexp.MustCompile(`(?i)access[_-]?token=[^\s&]+`),
	regexp.MustCompile(`(?i)refresh[_-]?token=[^\s&]+`),
}

func redactSensitive(value string) string {
	redacted := value
	for _, pattern := range redactPatterns {
		redacted = pattern.ReplaceAllStringFunc(redacted, func(match string) string {
			lower := strings.ToLower(match)
			switch {
			case strings.HasPrefix(lower, "http://"), strings.HasPrefix(lower, "https://"):
				return redactURLCredentials(match)
			case strings.HasPrefix(lower, "bearer "):
				return "Bearer [REDACTED]"
			case strings.HasPrefix(lower, "authorization: basic "):
				return "Authorization: Basic [REDACTED]"
			case strings.Contains(lower, "="):
				parts := strings.SplitN(match, "=", 2)
				return parts[0] + "=[REDACTED]"
			default:
				return "[REDACTED]"
			}
		})
	}
	return redacted
}

func redactURLCredentials(raw string) string {
	schemeSplit := strings.SplitN(raw, "://", 2)
	if len(schemeSplit) != 2 {
		return "[REDACTED]"
	}
	rest := schemeSplit[1]
	at := strings.Index(rest, "@")
	if at == -1 {
		return raw
	}
	return schemeSplit[0] + "://[REDACTED]@" + rest[at+1:]
}
