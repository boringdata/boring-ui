package boringui

import (
	apppkg "github.com/boringdata/boring-ui/internal/app"
	"github.com/boringdata/boring-ui/internal/config"
)

type App = apppkg.App
type Module = apppkg.Module
type Router = apppkg.Router
type Config = config.Config

func LoadConfig(path string) (Config, error) {
	return config.Load(path)
}
