package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	apppkg "github.com/boringdata/boring-ui/internal/app"
	"github.com/boringdata/boring-ui/internal/config"
)

func main() {
	cfg, err := config.Load("")
	if err != nil {
		slog.Error("load config", "error", err)
		os.Exit(1)
	}

	application := apppkg.New(cfg)
	server := &http.Server{
		Addr:              cfg.ListenAddress(),
		Handler:           application.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdownCtx); err != nil {
			slog.Error("shutdown server", "error", err)
		}
	}()

	slog.Info("starting go backend", "addr", server.Addr, "config", cfg.ConfigPath)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server exited", "error", err)
		os.Exit(1)
	}
}
