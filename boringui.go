package boringui

import (
	"path/filepath"

	apppkg "github.com/boringdata/boring-ui/internal/app"
	"github.com/boringdata/boring-ui/internal/config"
	controlplane "github.com/boringdata/boring-ui/internal/modules/controlplane"
	filesmodule "github.com/boringdata/boring-ui/internal/modules/files"
	gitmodule "github.com/boringdata/boring-ui/internal/modules/git"
	githubmodule "github.com/boringdata/boring-ui/internal/modules/github"
	pluginsmodule "github.com/boringdata/boring-ui/internal/modules/plugins"
	ptymodule "github.com/boringdata/boring-ui/internal/modules/pty"
	streammodule "github.com/boringdata/boring-ui/internal/modules/stream"
	uistatemodule "github.com/boringdata/boring-ui/internal/modules/uistate"
	"github.com/boringdata/boring-ui/internal/storage"
)

// BuildApp wires the default Go backend surface that cmd/server exposes.
func BuildApp(cfg config.Config) (*apppkg.App, error) {
	application := apppkg.New(cfg)

	workspaceRoot := "."
	if cfg.ConfigPath != "" {
		workspaceRoot = filepath.Dir(cfg.ConfigPath)
	}
	store, err := storage.NewLocal(workspaceRoot)
	if err != nil {
		return nil, err
	}

	filesModule, err := filesmodule.NewModule(cfg, store)
	if err != nil {
		return nil, err
	}
	application.AddModule(filesModule)

	uiStateModule, err := uistatemodule.NewModule(cfg, store)
	if err != nil {
		return nil, err
	}
	application.AddModule(uiStateModule)

	gitModule, err := gitmodule.NewModule(cfg, nil)
	if err != nil {
		return nil, err
	}
	application.AddModule(gitModule)

	ptyModule, err := ptymodule.NewModule(cfg)
	if err != nil {
		return nil, err
	}
	application.AddModule(ptyModule)

	streamModule, err := streammodule.NewModule(cfg)
	if err != nil {
		return nil, err
	}
	application.AddModule(streamModule)

	controlPlaneModule, err := controlplane.NewModule(cfg)
	if err != nil {
		return nil, err
	}
	application.SetAuthStateBridge(controlPlaneModule)
	application.AddModule(controlPlaneModule)

	githubModule, err := githubmodule.NewModule(cfg)
	if err != nil {
		return nil, err
	}
	application.AddModule(githubModule)

	pluginsModule, err := pluginsmodule.NewModule(cfg)
	if err != nil {
		return nil, err
	}
	application.AddModule(pluginsModule)

	return application, nil
}
