package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"path"
	"regexp"
	"sort"
	"strings"
	"time"
)

var defaultAllPaths = []string{
	"/health",
	"/api/capabilities",
}

type multiFlag []string

func (m *multiFlag) String() string {
	return strings.Join(*m, ",")
}

func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}

type runConfig struct {
	baseURL      string
	targetURL    string
	paths        []string
	useAll       bool
	loginPath    string
	format       string
	ignores      []*regexp.Regexp
	baseClient   *http.Client
	targetClient *http.Client
}

type report struct {
	OK            bool           `json:"ok"`
	ComparedPaths []string       `json:"compared_paths"`
	MatchedPaths  []string       `json:"matched_paths"`
	Diffs         []endpointDiff `json:"diffs"`
	Errors        []string       `json:"errors,omitempty"`
}

type endpointDiff struct {
	Path     string   `json:"path"`
	Problems []string `json:"problems"`
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout, stderr io.Writer) int {
	cfg, err := parseArgs(args)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 2
	}

	rep, err := execute(cfg)
	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}

	if cfg.format == "json" {
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(rep); err != nil {
			fmt.Fprintln(stderr, err)
			return 1
		}
	} else {
		writeTextReport(stdout, rep)
	}

	if rep.OK {
		return 0
	}
	return 1
}

func parseArgs(args []string) (runConfig, error) {
	var cfg runConfig
	var pathsFlag string
	var ignores multiFlag
	fs := flag.NewFlagSet("api-diff", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	fs.StringVar(&cfg.baseURL, "base", "", "base backend URL")
	fs.StringVar(&cfg.targetURL, "target", "", "target backend URL")
	fs.StringVar(&pathsFlag, "paths", "", "comma-separated paths to compare")
	fs.BoolVar(&cfg.useAll, "all", false, "discover GET endpoints from /openapi.json")
	fs.StringVar(&cfg.loginPath, "login-path", "", "optional relative path to call before comparisons to establish session cookies")
	fs.StringVar(&cfg.format, "format", "text", "output format: text or json")
	fs.Var(&ignores, "ignore", "regex for JSON paths to ignore (repeatable)")

	if err := fs.Parse(args); err != nil {
		return cfg, err
	}
	if cfg.baseURL == "" || cfg.targetURL == "" {
		return cfg, errors.New("--base and --target are required")
	}
	if cfg.format != "text" && cfg.format != "json" {
		return cfg, fmt.Errorf("unsupported --format %q", cfg.format)
	}

	if pathsFlag != "" {
		cfg.paths = splitCSV(pathsFlag)
	}
	if !cfg.useAll && len(cfg.paths) == 0 {
		return cfg, errors.New("provide --paths or --all")
	}

	for _, pattern := range ignores {
		re, err := regexp.Compile(pattern)
		if err != nil {
			return cfg, fmt.Errorf("invalid --ignore %q: %w", pattern, err)
		}
		cfg.ignores = append(cfg.ignores, re)
	}

	baseClient, err := newHTTPClient()
	if err != nil {
		return cfg, err
	}
	targetClient, err := newHTTPClient()
	if err != nil {
		return cfg, err
	}
	cfg.baseClient = baseClient
	cfg.targetClient = targetClient
	return cfg, nil
}

func execute(cfg runConfig) (report, error) {
	if strings.TrimSpace(cfg.loginPath) != "" {
		if err := establishSession(cfg.baseClient, cfg.baseURL, cfg.loginPath); err != nil {
			return report{}, err
		}
		if err := establishSession(cfg.targetClient, cfg.targetURL, cfg.loginPath); err != nil {
			return report{}, err
		}
	}

	paths, err := expandPaths(cfg)
	if err != nil {
		return report{}, err
	}
	if cfg.useAll {
		discovered, err := discoverPaths(cfg.baseClient, cfg.baseURL, cfg.targetClient, cfg.targetURL)
		if err != nil {
			return report{}, err
		}
		paths = append(paths, discovered...)
	}
	paths = uniqueSorted(paths)
	if len(paths) == 0 {
		return report{}, errors.New("no paths to compare")
	}

	rep := report{ComparedPaths: paths}
	for _, path := range paths {
		diff, err := comparePath(cfg, path)
		if err != nil {
			rep.Diffs = append(rep.Diffs, endpointDiff{
				Path:     path,
				Problems: []string{err.Error()},
			})
			continue
		}
		if len(diff.Problems) == 0 {
			rep.MatchedPaths = append(rep.MatchedPaths, path)
			continue
		}
		rep.Diffs = append(rep.Diffs, diff)
	}

	rep.OK = len(rep.Diffs) == 0
	return rep, nil
}

func expandPaths(cfg runConfig) ([]string, error) {
	paths := append([]string{}, cfg.paths...)
	if !hasGlobPatterns(paths) {
		return paths, nil
	}

	discovered, err := discoverPaths(cfg.baseClient, cfg.baseURL, cfg.targetClient, cfg.targetURL)
	if err != nil {
		return nil, err
	}

	expanded := make([]string, 0, len(paths))
	for _, candidate := range paths {
		if !hasGlobMeta(candidate) {
			expanded = append(expanded, candidate)
			continue
		}

		matched := false
		for _, discoveredPath := range discovered {
			ok, err := path.Match(candidate, discoveredPath)
			if err != nil {
				return nil, fmt.Errorf("invalid path glob %q: %w", candidate, err)
			}
			if !ok {
				continue
			}
			expanded = append(expanded, discoveredPath)
			matched = true
		}
		if !matched {
			expanded = append(expanded, candidate)
		}
	}

	return expanded, nil
}

func comparePath(cfg runConfig, path string) (endpointDiff, error) {
	baseResp, err := fetch(cfg.baseClient, cfg.baseURL, path)
	if err != nil {
		return endpointDiff{}, fmt.Errorf("base request failed: %w", err)
	}
	targetResp, err := fetch(cfg.targetClient, cfg.targetURL, path)
	if err != nil {
		return endpointDiff{}, fmt.Errorf("target request failed: %w", err)
	}

	diff := endpointDiff{Path: path}
	if baseResp.StatusCode != targetResp.StatusCode {
		diff.Problems = append(diff.Problems, fmt.Sprintf(
			"status code mismatch: base=%d target=%d",
			baseResp.StatusCode,
			targetResp.StatusCode,
		))
	}

	baseType := mediaType(baseResp.Header.Get("Content-Type"))
	targetType := mediaType(targetResp.Header.Get("Content-Type"))
	if baseType != targetType {
		diff.Problems = append(diff.Problems, fmt.Sprintf(
			"content type mismatch: base=%s target=%s",
			baseType,
			targetType,
		))
		return diff, nil
	}

	if strings.HasSuffix(baseType, "/json") || strings.Contains(baseType, "+json") {
		baseJSON, err := decodeJSON(baseResp.Body)
		if err != nil {
			diff.Problems = append(diff.Problems, fmt.Sprintf("base JSON decode failed: %v", err))
			return diff, nil
		}
		targetJSON, err := decodeJSON(targetResp.Body)
		if err != nil {
			diff.Problems = append(diff.Problems, fmt.Sprintf("target JSON decode failed: %v", err))
			return diff, nil
		}
		diff.Problems = append(diff.Problems, compareJSON("$", baseJSON, targetJSON, cfg.ignores)...)
		return diff, nil
	}

	if shouldSkipBodyComparison(baseType) {
		return diff, nil
	}

	baseBody := strings.TrimSpace(string(baseResp.Body))
	targetBody := strings.TrimSpace(string(targetResp.Body))
	if baseBody != targetBody {
		diff.Problems = append(diff.Problems, fmt.Sprintf(
			"body mismatch: base=%q target=%q",
			baseBody,
			targetBody,
		))
	}
	return diff, nil
}

type httpResponse struct {
	StatusCode int
	Header     http.Header
	Body       []byte
}

type openAPIParameter struct {
	Required bool `json:"required"`
}

func fetch(client *http.Client, rootURL, path string) (httpResponse, error) {
	endpoint, err := joinURL(rootURL, path)
	if err != nil {
		return httpResponse{}, err
	}
	req, err := http.NewRequest(http.MethodGet, endpoint, nil)
	if err != nil {
		return httpResponse{}, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return httpResponse{}, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return httpResponse{}, err
	}
	return httpResponse{
		StatusCode: resp.StatusCode,
		Header:     resp.Header.Clone(),
		Body:       body,
	}, nil
}

func establishSession(client *http.Client, rootURL, loginPath string) error {
	resp, err := fetch(client, rootURL, loginPath)
	if err != nil {
		return fmt.Errorf("login bootstrap failed for %s%s: %w", strings.TrimRight(rootURL, "/"), loginPath, err)
	}
	if resp.StatusCode >= 400 {
		return fmt.Errorf("login bootstrap failed for %s%s: status %d", strings.TrimRight(rootURL, "/"), loginPath, resp.StatusCode)
	}
	return nil
}

func newHTTPClient() (*http.Client, error) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		return nil, err
	}
	return &http.Client{
		Timeout: 10 * time.Second,
		Jar:     jar,
		CheckRedirect: func(*http.Request, []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}, nil
}

func discoverPaths(baseClient *http.Client, baseURL string, targetClient *http.Client, targetURL string) ([]string, error) {
	set := make(map[string]struct{}, len(defaultAllPaths))
	for _, path := range defaultAllPaths {
		set[path] = struct{}{}
	}

	var errs []string
	for _, source := range []struct {
		client  *http.Client
		rootURL string
	}{
		{client: baseClient, rootURL: baseURL},
		{client: targetClient, rootURL: targetURL},
	} {
		paths, err := fetchOpenAPIPaths(source.client, source.rootURL)
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		for _, path := range paths {
			set[path] = struct{}{}
		}
	}

	paths := make([]string, 0, len(set))
	for path := range set {
		paths = append(paths, path)
	}
	sort.Strings(paths)

	if len(paths) == len(defaultAllPaths) && len(errs) == 2 {
		return paths, nil
	}
	return paths, nil
}

func fetchOpenAPIPaths(client *http.Client, rootURL string) ([]string, error) {
	resp, err := fetch(client, rootURL, "/openapi.json")
	if err != nil {
		return nil, fmt.Errorf("%s/openapi.json: %w", strings.TrimRight(rootURL, "/"), err)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s/openapi.json: status %d", strings.TrimRight(rootURL, "/"), resp.StatusCode)
	}

	var payload struct {
		Paths map[string]map[string]json.RawMessage `json:"paths"`
	}
	if err := json.Unmarshal(resp.Body, &payload); err != nil {
		return nil, fmt.Errorf("%s/openapi.json: %w", strings.TrimRight(rootURL, "/"), err)
	}

	var paths []string
	for routePath, methods := range payload.Paths {
		if strings.Contains(routePath, "{") {
			continue
		}
		if hasRequiredParameters(methods) {
			continue
		}
		if _, ok := methods[strings.ToLower(http.MethodGet)]; ok {
			paths = append(paths, routePath)
		}
	}
	sort.Strings(paths)
	return paths, nil
}

func hasRequiredParameters(methods map[string]json.RawMessage) bool {
	var pathLevel struct {
		Parameters []openAPIParameter `json:"parameters"`
	}
	if raw, ok := methods["parameters"]; ok {
		if err := json.Unmarshal(raw, &pathLevel); err == nil && anyRequiredParameters(pathLevel.Parameters) {
			return true
		}
	}

	for method, raw := range methods {
		if strings.EqualFold(method, "parameters") {
			continue
		}
		var operation struct {
			Parameters []openAPIParameter `json:"parameters"`
		}
		if err := json.Unmarshal(raw, &operation); err == nil && anyRequiredParameters(operation.Parameters) {
			return true
		}
	}
	return false
}

func anyRequiredParameters(parameters []openAPIParameter) bool {
	for _, parameter := range parameters {
		if parameter.Required {
			return true
		}
	}
	return false
}

func decodeJSON(body []byte) (any, error) {
	var value any
	if err := json.Unmarshal(body, &value); err != nil {
		return nil, err
	}
	return value, nil
}

func compareJSON(path string, base, target any, ignores []*regexp.Regexp) []string {
	if shouldIgnore(path, ignores) {
		return nil
	}

	baseKind := kindOf(base)
	targetKind := kindOf(target)
	if baseKind != targetKind {
		return []string{fmt.Sprintf("%s type mismatch: base=%s target=%s", path, baseKind, targetKind)}
	}

	switch baseValue := base.(type) {
	case map[string]any:
		targetValue := target.(map[string]any)
		var problems []string
		keys := make(map[string]struct{}, len(baseValue)+len(targetValue))
		for key := range baseValue {
			keys[key] = struct{}{}
		}
		for key := range targetValue {
			keys[key] = struct{}{}
		}

		keyList := make([]string, 0, len(keys))
		for key := range keys {
			keyList = append(keyList, key)
		}
		sort.Strings(keyList)
		for _, key := range keyList {
			childPath := path + "." + key
			if shouldIgnore(childPath, ignores) {
				continue
			}
			baseChild, baseOK := baseValue[key]
			targetChild, targetOK := targetValue[key]
			if !baseOK {
				problems = append(problems, fmt.Sprintf("%s missing in base", childPath))
				continue
			}
			if !targetOK {
				problems = append(problems, fmt.Sprintf("%s missing in target", childPath))
				continue
			}
			problems = append(problems, compareJSON(childPath, baseChild, targetChild, ignores)...)
		}
		return problems
	case []any:
		targetValue := target.([]any)
		baseShape := arrayShape(path, baseValue, ignores)
		targetShape := arrayShape(path, targetValue, ignores)
		if baseShape == "" || targetShape == "" {
			return nil
		}
		if baseShape != targetShape {
			return []string{fmt.Sprintf("%s array shape mismatch: base=%s target=%s", path, baseShape, targetShape)}
		}
		return nil
	default:
		return nil
	}
}

func arrayShape(path string, values []any, ignores []*regexp.Regexp) string {
	if len(values) == 0 {
		return ""
	}
	set := make(map[string]struct{}, len(values))
	for idx, value := range values {
		childPath := fmt.Sprintf("%s[%d]", path, idx)
		sig := normalizeShape(childPath, value, ignores)
		if sig == "" {
			continue
		}
		set[sig] = struct{}{}
	}
	if len(set) == 0 {
		return ""
	}
	shapes := make([]string, 0, len(set))
	for sig := range set {
		shapes = append(shapes, sig)
	}
	sort.Strings(shapes)
	return "[" + strings.Join(shapes, ",") + "]"
}

func normalizeShape(path string, value any, ignores []*regexp.Regexp) string {
	if shouldIgnore(path, ignores) {
		return ""
	}
	switch typed := value.(type) {
	case nil:
		return "null"
	case bool:
		return "bool"
	case string:
		return "string"
	case float64:
		return "number"
	case map[string]any:
		keys := make([]string, 0, len(typed))
		for key := range typed {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		parts := make([]string, 0, len(keys))
		for _, key := range keys {
			childPath := path + "." + key
			if shouldIgnore(childPath, ignores) {
				continue
			}
			parts = append(parts, key+":"+normalizeShape(childPath, typed[key], ignores))
		}
		return "{" + strings.Join(parts, ",") + "}"
	case []any:
		return arrayShape(path, typed, ignores)
	default:
		return kindOf(value)
	}
}

func kindOf(value any) string {
	switch value.(type) {
	case nil:
		return "null"
	case bool:
		return "bool"
	case string:
		return "string"
	case float64:
		return "number"
	case map[string]any:
		return "object"
	case []any:
		return "array"
	default:
		return fmt.Sprintf("%T", value)
	}
}

func mediaType(value string) string {
	if value == "" {
		return "application/octet-stream"
	}
	parsed, _, err := mime.ParseMediaType(value)
	if err != nil {
		return value
	}
	return parsed
}

func shouldSkipBodyComparison(contentType string) bool {
	return contentType == "text/html"
}

func shouldIgnore(path string, ignores []*regexp.Regexp) bool {
	for _, re := range ignores {
		if re.MatchString(path) {
			return true
		}
	}
	return false
}

func splitCSV(raw string) []string {
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		out = append(out, part)
	}
	return out
}

func hasGlobPatterns(values []string) bool {
	for _, value := range values {
		if hasGlobMeta(value) {
			return true
		}
	}
	return false
}

func hasGlobMeta(value string) bool {
	return strings.ContainsAny(value, "*?[")
}

func uniqueSorted(values []string) []string {
	set := make(map[string]struct{}, len(values))
	for _, value := range values {
		if value == "" {
			continue
		}
		set[value] = struct{}{}
	}
	out := make([]string, 0, len(set))
	for value := range set {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

func joinURL(rootURL, path string) (string, error) {
	base, err := url.Parse(rootURL)
	if err != nil {
		return "", err
	}
	ref, err := url.Parse(path)
	if err != nil {
		return "", err
	}
	return base.ResolveReference(ref).String(), nil
}

func writeTextReport(w io.Writer, rep report) {
	if rep.OK {
		fmt.Fprintf(w, "OK: %d path(s) matched\n", len(rep.MatchedPaths))
		for _, path := range rep.MatchedPaths {
			fmt.Fprintf(w, "  %s\n", path)
		}
		return
	}

	fmt.Fprintf(w, "DIFF: %d/%d path(s) differ\n", len(rep.Diffs), len(rep.ComparedPaths))
	for _, diff := range rep.Diffs {
		fmt.Fprintf(w, "%s\n", diff.Path)
		for _, problem := range diff.Problems {
			fmt.Fprintf(w, "  - %s\n", problem)
		}
	}
}
