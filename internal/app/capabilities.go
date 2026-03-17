package app

import "strings"

type routerCapability struct {
	name        string
	prefix      string
	description string
	tags        []string
}

var defaultCapabilityRouters = []routerCapability{
	{name: "files", prefix: "/api/v1/files", description: "File system operations (read, write, rename, delete)", tags: []string{"files"}},
	{name: "git", prefix: "/api/v1/git", description: "Git operations (status, diff, show)", tags: []string{"git"}},
	{name: "ui_state", prefix: "/api/v1/ui", description: "Workspace UI state snapshots (open panes, active pane)", tags: []string{"ui"}},
	{name: "control_plane", prefix: "/api/v1/control-plane", description: "Workspace/user/membership/invite/settings metadata foundation", tags: []string{"control-plane"}},
	{name: "pty", prefix: "/ws", description: "PTY WebSocket for shell terminals", tags: []string{"websocket", "terminal"}},
	{name: "chat_claude_code", prefix: "/ws/agent/normal", description: "Claude stream WebSocket for AI chat", tags: []string{"websocket", "ai"}},
	{name: "stream", prefix: "/ws/agent/normal", description: "Claude stream WebSocket for AI chat (alias for chat_claude_code)", tags: []string{"websocket", "ai"}},
	{name: "approval", prefix: "/api", description: "Approval workflow endpoints", tags: []string{"approval"}},
}

func (a *App) capabilitiesPayload() map[string]any {
	enabledModules := make(map[string]struct{}, len(a.modules))
	for _, module := range a.modules {
		enabledModules[strings.TrimSpace(module.Name())] = struct{}{}
	}

	hasModule := func(name string) bool {
		_, ok := enabledModules[name]
		return ok
	}

	features := map[string]bool{
		"files":            hasModule("files"),
		"git":              hasModule("git"),
		"ui_state":         hasModule("ui_state"),
		"control_plane":    hasModule("control_plane"),
		"pty":              hasModule("pty"),
		"chat_claude_code": hasModule("chat_claude_code"),
		"stream":           hasModule("chat_claude_code"),
		"approval":         false,
		"companion":        true,
		"pi":               true,
		"github":           hasModule("github"),
	}

	routers := make([]map[string]any, 0, len(defaultCapabilityRouters))
	for _, router := range defaultCapabilityRouters {
		tags := make([]string, len(router.tags))
		copy(tags, router.tags)
		routers = append(routers, map[string]any{
			"name":                       router.name,
			"prefix":                     router.prefix,
			"description":                router.description,
			"tags":                       tags,
			"enabled":                    features[router.name],
			"contract_metadata":          nil,
			"contract_metadata_included": false,
		})
	}

	return map[string]any{
		"version":  "0.1.0",
		"features": features,
		"routers":  routers,
	}
}
