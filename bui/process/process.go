// Package process manages spawning and supervising child processes.
package process

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// Proc wraps a managed child process.
type Proc struct {
	Name string
	Cmd  *exec.Cmd
}

// Supervisor runs multiple processes and shuts them all down
// when any one exits or a signal is received.
type Supervisor struct {
	procs []*Proc
}

// Add registers a process to be supervised.
func (s *Supervisor) Add(name string, cmd *exec.Cmd) {
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	s.procs = append(s.procs, &Proc{Name: name, Cmd: cmd})
}

// Run starts all processes and waits. Returns on first exit or signal.
func (s *Supervisor) Run(ctx context.Context) error {
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	// Catch signals
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		select {
		case <-sig:
			cancel()
		case <-ctx.Done():
		}
	}()

	var wg sync.WaitGroup
	errCh := make(chan error, len(s.procs))

	for _, p := range s.procs {
		wg.Add(1)
		go func(p *Proc) {
			defer wg.Done()
			fmt.Printf("[bui] starting %s: %s\n", p.Name, p.Cmd.String())
			if err := p.Cmd.Start(); err != nil {
				errCh <- fmt.Errorf("%s failed to start: %w", p.Name, err)
				cancel()
				return
			}

			done := make(chan error, 1)
			go func() { done <- p.Cmd.Wait() }()

			select {
			case err := <-done:
				if err != nil {
					errCh <- fmt.Errorf("%s exited: %w", p.Name, err)
				}
				cancel()
			case <-ctx.Done():
				_ = p.Cmd.Process.Signal(syscall.SIGTERM)
				select {
				case <-done:
				case <-time.After(5 * time.Second):
					_ = p.Cmd.Process.Kill()
					<-done
				}
			}
		}(p)
	}

	wg.Wait()
	close(errCh)

	for err := range errCh {
		return err
	}
	return nil
}
