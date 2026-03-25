package cmd

import (
	"slices"
	"testing"
)

func TestDefaultNeonTrustedOrigins(t *testing.T) {
	origins := defaultNeonTrustedOrigins("boring-ui")

	want := []string{
		"https://boring-ui.fly.dev",
		"http://127.0.0.1:3000",
		"http://127.0.0.1:5173",
		"http://127.0.0.1:5174",
		"http://127.0.0.1:5175",
		"http://127.0.0.1:5176",
	}

	if len(origins) != len(want) {
		t.Fatalf("expected %d trusted origins, got %d: %#v", len(want), len(origins), origins)
	}
	for idx, expected := range want {
		if origins[idx] != expected {
			t.Fatalf("origin[%d]: expected %q, got %q", idx, expected, origins[idx])
		}
	}
}

func TestNeonSetupNextStepsWhenEmailConfigured(t *testing.T) {
	lines := neonSetupNextSteps(true)
	if len(lines) != 3 {
		t.Fatalf("expected 3 next-step lines, got %d: %#v", len(lines), lines)
	}
	if slices.Contains(lines, "  1. Configure a custom SMTP provider in Neon Console if you need verification emails") {
		t.Fatalf("unexpected SMTP setup prompt when email is already configured: %#v", lines)
	}
}

func TestNeonSetupNextStepsWhenEmailMissing(t *testing.T) {
	lines := neonSetupNextSteps(false)
	if len(lines) != 5 {
		t.Fatalf("expected 5 next-step lines, got %d: %#v", len(lines), lines)
	}
	if !slices.Contains(lines, "     Neon Console → Settings → Auth → Custom SMTP provider") {
		t.Fatalf("expected Neon Console guidance when email is missing: %#v", lines)
	}
}
