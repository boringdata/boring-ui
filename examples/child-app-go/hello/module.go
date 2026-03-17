package hello

import (
	"encoding/json"
	"net/http"

	"github.com/boringdata/boring-ui/internal/app"
)

type Module struct{}

func NewModule() *Module {
	return &Module{}
}

func (m *Module) Name() string {
	return "hello"
}

func (m *Module) RegisterRoutes(router app.Router) {
	router.Route("/api/v1/hello", func(r app.Router) {
		r.Method(http.MethodGet, "/ping", http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
			writeJSON(w, http.StatusOK, map[string]any{
				"ok":      true,
				"message": "hello from child-app-go",
			})
		}))
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
