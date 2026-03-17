package app

import (
	"net/http"

	"github.com/go-chi/chi/v5"
)

// Router keeps modules decoupled from chi while still exposing route composition.
type Router interface {
	Method(method, pattern string, handler http.Handler)
	With(middlewares ...func(http.Handler) http.Handler) Router
	Route(pattern string, fn func(Router))
	HandleWebSocket(pattern string, handler http.Handler)
}

type chiAdapter struct {
	router chi.Router
}

func newChiAdapter() *chiAdapter {
	return &chiAdapter{router: chi.NewRouter()}
}

func newScopedRouter(router chi.Router) *chiAdapter {
	return &chiAdapter{router: router}
}

func (r *chiAdapter) Method(method, pattern string, handler http.Handler) {
	r.router.Method(method, pattern, handler)
}

func (r *chiAdapter) With(middlewares ...func(http.Handler) http.Handler) Router {
	return newScopedRouter(r.router.With(middlewares...))
}

func (r *chiAdapter) Route(pattern string, fn func(Router)) {
	r.router.Route(pattern, func(child chi.Router) {
		fn(newScopedRouter(child))
	})
}

func (r *chiAdapter) HandleWebSocket(pattern string, handler http.Handler) {
	r.router.Get(pattern, func(w http.ResponseWriter, req *http.Request) {
		handler.ServeHTTP(w, req)
	})
}

func URLParam(req *http.Request, name string) string {
	return chi.URLParam(req, name)
}

func (r *chiAdapter) Handler() http.Handler {
	return r.router
}
