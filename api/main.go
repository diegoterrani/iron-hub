package main

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

//go:embed all:dist
var webFS embed.FS

const (
	sessionCookie = "iron_session"
	sessionTTL    = 12 * time.Hour
)

type ServiceDef struct {
	ID         string `json:"id"`
	URL        string `json:"-"` // internal only — never exposed to browser
	HealthPath string `json:"healthPath,omitempty"`
	Type       string `json:"type"`
	Gateway    string `json:"gateway,omitempty"` // public path /t/{id}/
}

type PublicService struct {
	ID         string `json:"id"`
	Type       string `json:"type"`
	Gateway    string `json:"gateway,omitempty"`
	HealthPath string `json:"healthPath,omitempty"`
}

type HealthEntry struct {
	Status    string `json:"status"`
	LatencyMs int64  `json:"latency_ms,omitempty"`
}

type HealthResponse struct {
	Services  map[string]HealthEntry `json:"services"`
	CheckedAt string                 `json:"checked_at"`
}

type loginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

var services = []ServiceDef{
	{ID: "mosint", URL: "http://127.0.0.1:8787", HealthPath: "/api/health", Type: "web"},
	{ID: "osint-mapping", URL: "http://127.0.0.1:8789", HealthPath: "/health", Type: "web"},
	{ID: "maverick", URL: "http://127.0.0.1:8766", HealthPath: "/api/health", Type: "web"},
	{ID: "hackingbuddygpt", URL: "http://127.0.0.1:8778", HealthPath: "/api/health", Type: "web"},
	{ID: "pentestgpt", URL: "http://127.0.0.1:8777", HealthPath: "/api/health", Type: "web"},
	{ID: "scrapling", URL: "http://127.0.0.1:8770", HealthPath: "/api/health", Type: "web"},
	{ID: "pentest-ops", URL: "http://127.0.0.1:8788", HealthPath: "/api/health", Type: "web"},
	{ID: "burpgpt", URL: "http://127.0.0.1:8772", HealthPath: "/api/health", Type: "web"},
	{ID: "o365-csirt", URL: "http://127.0.0.1:8000", HealthPath: "/api/health", Type: "web"},
	{ID: "darkweb-tracker", URL: "http://127.0.0.1:13200", HealthPath: "/api/health", Type: "web"},
	{ID: "darkweb-observatory", URL: "http://127.0.0.1:8791", HealthPath: "/api/health", Type: "web"},
	{ID: "robin", URL: "http://127.0.0.1:18501", HealthPath: "/_stcore/health", Type: "web"},
	{ID: "open-webui", URL: "http://127.0.0.1:3080", HealthPath: "/health", Type: "web"},
	{ID: "moneyprinter", URL: "http://127.0.0.1:8502", HealthPath: "/_stcore/health", Type: "web"},
	{ID: "bot-live", URL: "http://127.0.0.1:3000", HealthPath: "/api/health", Type: "web"},
	{ID: "onboarding", URL: "http://127.0.0.1:3001", HealthPath: "/", Type: "web"},
	{ID: "betbonus", URL: "http://127.0.0.1:8010", HealthPath: "/api/health", Type: "web"},
	{ID: "casino-bot", URL: "http://127.0.0.1:8011", HealthPath: "/api/health", Type: "web"},
	{ID: "cdn-image", URL: "http://127.0.0.1:8794", HealthPath: "/api/health", Type: "web"},
	{ID: "graphify", URL: "http://127.0.0.1:8792", HealthPath: "/mcp", Type: "api"},
}

var (
	hubUser   string
	hubPass   string
	sessionKey []byte
	serviceByID map[string]ServiceDef
)

func init() {
	serviceByID = make(map[string]ServiceDef, len(services))
	for i := range services {
		if services[i].Type == "web" || services[i].Type == "api" {
			// Open WebUI does not support subpaths; nginx switches root via /go/open-webui.
			if services[i].ID == "open-webui" {
				if upstream := strings.TrimSpace(os.Getenv("IRON_OPEN_WEBUI_UPSTREAM")); upstream != "" {
					services[i].URL = upstream
				}
				if u := strings.TrimSpace(os.Getenv("IRON_OPEN_WEBUI_URL")); u != "" {
					services[i].Gateway = u
				} else {
					services[i].Gateway = "/go/open-webui"
				}
			} else {
				services[i].Gateway = "/t/" + services[i].ID + "/"
			}
		}
		serviceByID[services[i].ID] = services[i]
	}
}

func main() {
	loadAuthConfig()

	wd, err := os.Getwd()
	if err != nil {
		wd = "."
	}
	initTOTP(wd)
	if totpEnabled() {
		log.Printf("2FA/TOTP: enabled")
	} else {
		log.Printf("2FA/TOTP: disabled (ative no Hub após login)")
	}

	port := os.Getenv("IRON_HUB_PORT")
	if port == "" {
		port = "3900"
	}
	// Produção: só localhost — nginx :443 é a única porta pública.
	// Override com IRON_HUB_BIND=0.0.0.0 se precisar de acesso LAN/Docker direto.
	bind := os.Getenv("IRON_HUB_BIND")
	if bind == "" {
		bind = "127.0.0.1"
	}

	distFS, err := fs.Sub(webFS, "dist")
	if err != nil {
		log.Fatalf("dist fs: %v", err)
	}
	fileServer := http.FileServer(http.FS(distFS))

	mux := http.NewServeMux()

	// Control plane (auth)
	mux.HandleFunc("/hub/api/login", handleLogin)
	mux.HandleFunc("/hub/api/login/2fa", handleLogin2FA)
	mux.HandleFunc("/hub/api/logout", requireAuth(handleLogout))
	mux.HandleFunc("/hub/api/me", requireAuth(handleMe))
	mux.HandleFunc("/hub/api/health", requireAuth(handleHealth))
	mux.HandleFunc("/hub/api/services", requireAuth(handleServices))
	mux.HandleFunc("/hub/api/2fa/status", requireAuth(handle2FAStatus))
	mux.HandleFunc("/hub/api/2fa/setup", requireAuth(handle2FASetup))
	mux.HandleFunc("/hub/api/2fa/enable", requireAuth(handle2FAEnable))
	mux.HandleFunc("/hub/api/2fa/disable", requireAuth(handle2FADisable))

	// Legacy aliases (auth required) — prefer /hub/api/*
	mux.HandleFunc("/api/health", requireAuth(handleHealth))
	mux.HandleFunc("/api/services", requireAuth(handleServices))

	// Graphify: Hub session (UI/config) OU Bearer GRAPHIFY_API_KEY (clientes MCP)
	mux.HandleFunc("/t/graphify/", requireGraphifyAccess(handleGateway))
	// Authenticated gateway → tools
	mux.HandleFunc("/t/", requireAuth(handleGateway))

	// Open WebUI escape hatch: SvelteKit may still request /_app/* at site root
	// when base is empty. Proxy those (auth required) instead of serving Hub SPA HTML.
	mux.HandleFunc("/_app/", requireAuth(handleOpenWebUIEscapedAsset))

	// SPA — public UI lives under /console/ so nginx can keep Open WebUI at /
	serveSPA := func(w http.ResponseWriter, r *http.Request) {
		path := r.URL.Path
		if strings.HasPrefix(path, "/console/") {
			path = strings.TrimPrefix(path, "/console")
		} else if path == "/console" {
			path = "/"
		}
		if path == "/" || path == "" {
			serveIndex(w, distFS)
			return
		}
		rel := strings.TrimPrefix(path, "/")
		if _, err := distFS.Open(rel); err != nil {
			serveIndex(w, distFS)
			return
		}
		// Serve file with rewritten path for FileServer
		r2 := r.Clone(r.Context())
		r2.URL = r.URL.ResolveReference(r.URL)
		r2.URL.Path = path
		fileServer.ServeHTTP(w, r2)
	}

	mux.HandleFunc("/console", func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "/console/", http.StatusFound)
	})
	mux.HandleFunc("/console/", serveSPA)

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/hub/api/") || strings.HasPrefix(r.URL.Path, "/t/") || strings.HasPrefix(r.URL.Path, "/console") {
			http.NotFound(w, r)
			return
		}
		// OWUI also loads /static/*, /ws/*, /ollama/*, etc. at root when base is wrong.
		if openWebUIRootPath(r.URL.Path) {
			requireAuth(handleOpenWebUIEscapedAsset)(w, r)
			return
		}
		// Legacy root → console
		if r.URL.Path == "/" {
			http.Redirect(w, r, "/console/", http.StatusFound)
			return
		}
		serveSPA(w, r)
	})

	addr := bind + ":" + port
	log.Printf("Iron Hub listening on http://%s (auth gateway enabled)", addr)
	log.Printf("Local user: %s", hubUser)
	log.Fatal(http.ListenAndServe(addr, securityHeaders(mux)))
}

func requestScheme(r *http.Request) string {
	if proto := r.Header.Get("X-Forwarded-Proto"); proto != "" {
		return strings.ToLower(strings.TrimSpace(strings.Split(proto, ",")[0]))
	}
	if r.TLS != nil {
		return "https"
	}
	return "http"
}

func loadAuthConfig() {
	hubUser = envOr("IRON_HUB_USER", "iron")
	hubPass = os.Getenv("IRON_HUB_PASS")
	if hubPass == "" {
		hubPass = "iron-" + randomHex(4)
		log.Printf("WARNING: IRON_HUB_PASS not set — generated temporary password: %s", hubPass)
	}
	secret := os.Getenv("IRON_HUB_SESSION_SECRET")
	if secret == "" {
		secret = randomHex(32)
		log.Printf("WARNING: IRON_HUB_SESSION_SECRET not set — using ephemeral secret (sessions reset on restart)")
	}
	sessionKey = []byte(secret)
}

func envOr(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func randomHex(n int) string {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b)
}

func serveIndex(w http.ResponseWriter, distFS fs.FS) {
	f, err := distFS.Open("index.html")
	if err != nil {
		http.Error(w, "index not found", http.StatusInternalServerError)
		return
	}
	defer f.Close()
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	io.Copy(w, f)
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "SAMEORIGIN")
		w.Header().Set("Referrer-Policy", "same-origin")
		if r.Method == http.MethodOptions {
			w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func requireAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		user, ok := sessionUser(r)
		if !ok {
			if strings.HasPrefix(r.URL.Path, "/hub/api/") || strings.HasPrefix(r.URL.Path, "/api/") {
				writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "unauthorized"})
				return
			}
			// Gateway HTML navigation → send back to Hub login
			http.Redirect(w, r, "/console/?next="+url.QueryEscape(r.URL.RequestURI()), http.StatusFound)
			return
		}
		ctx := context.WithValue(r.Context(), ctxUserKey{}, user)
		next(w, r.WithContext(ctx))
	}
}

// requireGraphifyAccess allows Hub session for UI/config downloads, or the
// Graphify API key Bearer for MCP Streamable HTTP clients (Cursor/Continue).
func requireGraphifyAccess(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if user, ok := sessionUser(r); ok {
			ctx := context.WithValue(r.Context(), ctxUserKey{}, user)
			next(w, r.WithContext(ctx))
			return
		}
		if graphifyBearerOK(r) && (wantsMCPStream(r) || r.Method != http.MethodGet) {
			ctx := context.WithValue(r.Context(), ctxUserKey{}, "graphify-key")
			next(w, r.WithContext(ctx))
			return
		}
		// Browser without session → Hub login
		http.Redirect(w, r, "/console/?next="+url.QueryEscape(r.URL.RequestURI()), http.StatusFound)
	}
}

func graphifyAPIKey() string {
	return strings.TrimSpace(os.Getenv("GRAPHIFY_API_KEY"))
}

func graphifyBearerOK(r *http.Request) bool {
	key := graphifyAPIKey()
	if key == "" {
		return false
	}
	auth := strings.TrimSpace(r.Header.Get("Authorization"))
	if len(auth) < 8 || !strings.EqualFold(auth[:7], "Bearer ") {
		// Also accept X-API-Key (graphify serve supports it)
		if x := strings.TrimSpace(r.Header.Get("X-API-Key")); x != "" {
			return hmac.Equal([]byte(x), []byte(key))
		}
		return false
	}
	return hmac.Equal([]byte(strings.TrimSpace(auth[7:])), []byte(key))
}

type ctxUserKey struct{}

func setHubIdentityHeaders(req *http.Request, user string) {
	req.Header.Del("X-Hub-User")
	req.Header.Del("X-Hub-Name")
	if user != "" {
		req.Header.Set("X-Hub-User", strings.ToLower(user)+"@hub.local")
		req.Header.Set("X-Hub-Name", user)
	}
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	var req loginRequest
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "invalid json"})
		return
	}
	req.Username = strings.TrimSpace(req.Username)
	if req.Username != hubUser || req.Password != hubPass {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "credenciais inválidas"})
		return
	}
	if totpEnabled() {
		pending, err := issuePending2FA(req.Username)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "2fa pending error"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{
			"ok":            true,
			"requires_2fa":  true,
			"pending_token": pending,
		})
		return
	}
	if err := setSessionCookie(w, r, req.Username); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "session error"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "user": req.Username, "requires_2fa": false})
}

func handleLogout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    "",
		Path:     "/",
		HttpOnly: true,
		Secure:   requestScheme(r) == "https",
		MaxAge:   -1,
	})
	writeJSON(w, http.StatusOK, map[string]any{"ok": true})
}

func handleMe(w http.ResponseWriter, r *http.Request) {
	user, _ := r.Context().Value(ctxUserKey{}).(string)
	// For nginx auth_request → Open WebUI trusted-header SSO
	if user != "" {
		w.Header().Set("X-Hub-User", strings.ToLower(user)+"@hub.local")
		w.Header().Set("X-Hub-Name", user)
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "user": user})
}

func handleServices(w http.ResponseWriter, r *http.Request) {
	out := make([]PublicService, 0, len(services))
	for _, s := range services {
		out = append(out, PublicService{
			ID:         s.ID,
			Type:       s.Type,
			Gateway:    s.Gateway,
			HealthPath: s.HealthPath,
		})
	}
	writeJSON(w, http.StatusOK, out)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 20*time.Second)
	defer cancel()

	results := make(map[string]HealthEntry)
	var mu sync.Mutex
	var wg sync.WaitGroup

	for _, svc := range services {
		if svc.Type == "cli" || svc.Type == "desktop" || svc.URL == "" {
			continue
		}
		wg.Add(1)
		go func(s ServiceDef) {
			defer wg.Done()
			status, latency := probe(ctx, s)
			mu.Lock()
			results[s.ID] = HealthEntry{Status: status, LatencyMs: latency}
			mu.Unlock()
		}(svc)
	}
	wg.Wait()

	writeJSON(w, http.StatusOK, HealthResponse{
		Services:  results,
		CheckedAt: time.Now().UTC().Format(time.RFC3339),
	})
}

func handleGateway(w http.ResponseWriter, r *http.Request) {
	rest := strings.TrimPrefix(r.URL.Path, "/t/")
	if rest == "" {
		http.Error(w, "missing tool id", http.StatusBadRequest)
		return
	}
	id, path, _ := strings.Cut(rest, "/")
	// Open WebUI cannot run under /t/... — send clients to nginx cookie switch.
	if id == "open-webui" {
		http.Redirect(w, r, "/go/open-webui", http.StatusFound)
		return
	}
	svc, ok := serviceByID[id]
	if !ok || svc.URL == "" {
		http.Error(w, "unknown tool", http.StatusNotFound)
		return
	}

	// Graphify MCP: browsers get a landing page; MCP clients (Accept: text/event-stream) hit /mcp.
	if id == "graphify" {
		if path == "" && !strings.HasSuffix(r.URL.Path, "/") {
			http.Redirect(w, r, r.URL.Path+"/", http.StatusFound)
			return
		}
		switch {
		case path == "config/cursor.json":
			writeGraphifyCursorConfig(w, r)
			return
		case path == "config/continue.yaml":
			writeGraphifyContinueConfig(w, r)
			return
		}
		isMCPPath := path == "mcp" || strings.HasPrefix(path, "mcp/")
		if path == "" || path == "info" || (isMCPPath && !wantsMCPStream(r)) {
			writeGraphifyLanding(w, r)
			return
		}
	}

	target, err := url.Parse(svc.URL)
	if err != nil {
		http.Error(w, "bad upstream", http.StatusBadGateway)
		return
	}

	proxyPath := "/" + path
	if path == "" {
		// Ensure trailing slash for directory-style apps
		if !strings.HasSuffix(r.URL.Path, "/") {
			http.Redirect(w, r, r.URL.Path+"/", http.StatusFound)
			return
		}
		proxyPath = "/"
	}

	proxy := httputil.NewSingleHostReverseProxy(target)
	// WebSocket / streaming (Open WebUI, Streamlit, MCP SSE, etc.)
	proxy.FlushInterval = -1
	originalDirector := proxy.Director
	prefix := "/t/" + id
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.URL.Path = proxyPath
		req.URL.RawPath = ""
		req.Host = target.Host
		req.Header.Set("X-Forwarded-Host", r.Host)
		req.Header.Set("X-Forwarded-Proto", requestScheme(r))
		req.Header.Set("X-Forwarded-Prefix", prefix)
		req.Header.Set("X-Forwarded-For", clientIP(r))
		user, _ := r.Context().Value(ctxUserKey{}).(string)
		// Prevent clients from spoofing Hub identity toward upstream services.
		setHubIdentityHeaders(req, user)
		// Graphify MCP: keep client Bearer if present, else inject server key.
		if id == "graphify" {
			if !graphifyBearerOK(req) {
				if key := graphifyAPIKey(); key != "" {
					req.Header.Set("Authorization", "Bearer "+key)
				}
			}
		}
		// Open WebUI / Streamlit need cookies for their own sessions; keep them.
		// Only strip Hub session cookie name.
		if cookies := req.Header.Get("Cookie"); cookies != "" {
			req.Header.Set("Cookie", stripCookie(cookies, sessionCookie))
		}
	}
	proxy.ErrorHandler = func(rw http.ResponseWriter, req *http.Request, e error) {
		log.Printf("gateway %s → %s: %v", id, svc.URL, e)
		http.Error(rw, "tool unavailable", http.StatusBadGateway)
	}
	proxy.ModifyResponse = func(resp *http.Response) error {
		// Rewrite absolute redirects to stay on gateway
		if loc := resp.Header.Get("Location"); loc != "" {
			if u, err := url.Parse(loc); err == nil {
				if u.Host == "" || u.Host == target.Host || u.Host == "127.0.0.1:"+targetPort(target) {
					newLoc := prefix + ensureLeadingSlash(u.Path)
					if u.RawQuery != "" {
						newLoc += "?" + u.RawQuery
					}
					resp.Header.Set("Location", newLoc)
				}
			}
		}
		return rewriteUpstreamBody(resp, prefix, id)
	}

	// Preserve query string
	r2 := r.Clone(r.Context())
	r2.URL = cloneURL(r.URL)
	r2.URL.Path = proxyPath
	proxy.ServeHTTP(w, r2)
}

func clientIP(r *http.Request) string {
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		return strings.TrimSpace(strings.Split(xff, ",")[0])
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func stripCookie(header, name string) string {
	parts := strings.Split(header, ";")
	keep := make([]string, 0, len(parts))
	prefix := name + "="
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" || strings.HasPrefix(p, prefix) {
			continue
		}
		keep = append(keep, p)
	}
	return strings.Join(keep, "; ")
}

// Matches absolute app paths that tools commonly emit (never /t/...).
var reAbsAppPath = regexp.MustCompile(
	`(href=|src=|action=|fetch\(\s*|["'\x60])/(api|assets|_stcore|_app|static|ws|ollama|openai|audio|manifest\.json|manager|styles\.css|app\.js|favicon\.svg|socket\.io|libs|themes|websocket|index\.html|intelligence\.json|alert_statistics\.html|historical_trends\.html|threat_feeds\.html|keyword_hits\.json|scan_viewer\.html|deep_scans)(/|["'\x60?])`,
)

// Streamlit embeds /_stcore/... inside JS bundles; rewrite those without touching /api
// (rewriting /api in JS breaks tools that already use gatewayPrefix).
var reStreamlitJSPath = regexp.MustCompile(
	`(["'\x60])/_stcore(/|["'\x60?])`,
)

// Open WebUI SvelteKit bootstrap: __sveltekit_xxx = { base: "" }
var reSvelteKitBase = regexp.MustCompile(
	`(__sveltekit_[A-Za-z0-9]+\s*=\s*\{\s*base:\s*)""`,
)

func openWebUIRootPath(p string) bool {
	switch {
	// SvelteKit navigates to /error when backend/API base breaks under /t/open-webui.
	case p == "/error", strings.HasPrefix(p, "/error/"),
		// OWUI API often escapes to site root; Hub's /api/health|/api/services are registered
		// earlier and keep winning — everything else under /api goes to Open WebUI.
		strings.HasPrefix(p, "/api/"),
		strings.HasPrefix(p, "/static/"),
		strings.HasPrefix(p, "/ws"),
		strings.HasPrefix(p, "/ollama"),
		strings.HasPrefix(p, "/openai"),
		strings.HasPrefix(p, "/audio"),
		strings.HasPrefix(p, "/cache/"),
		p == "/manifest.json",
		p == "/opensearch.xml",
		p == "/robots.txt",
		p == "/favicon.png",
		p == "/favicon.ico":
		return true
	default:
		return false
	}
}

// handleOpenWebUIEscapedAsset proxies root-absolute Open WebUI paths to the tool upstream.
func handleOpenWebUIEscapedAsset(w http.ResponseWriter, r *http.Request) {
	svc, ok := serviceByID["open-webui"]
	if !ok || svc.URL == "" {
		http.Error(w, "open-webui unavailable", http.StatusBadGateway)
		return
	}
	target, err := url.Parse(svc.URL)
	if err != nil {
		http.Error(w, "bad upstream", http.StatusBadGateway)
		return
	}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.FlushInterval = -1
	prefix := "/t/open-webui"
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		req.URL.Path = r.URL.Path
		req.URL.RawPath = ""
		req.URL.RawQuery = r.URL.RawQuery
		req.Host = target.Host
		req.Header.Set("X-Forwarded-Host", r.Host)
		req.Header.Set("X-Forwarded-Proto", requestScheme(r))
		req.Header.Set("X-Forwarded-Prefix", prefix)
		req.Header.Set("X-Forwarded-For", clientIP(r))
		user, _ := r.Context().Value(ctxUserKey{}).(string)
		// Prevent clients from spoofing Hub identity toward upstream services.
		setHubIdentityHeaders(req, user)
		if cookies := req.Header.Get("Cookie"); cookies != "" {
			req.Header.Set("Cookie", stripCookie(cookies, sessionCookie))
		}
	}
	proxy.ErrorHandler = func(rw http.ResponseWriter, req *http.Request, e error) {
		log.Printf("gateway open-webui-escape → %s: %v", svc.URL, e)
		http.Error(rw, "tool unavailable", http.StatusBadGateway)
	}
	proxy.ModifyResponse = func(resp *http.Response) error {
		return rewriteUpstreamBody(resp, prefix, "open-webui")
	}
	proxy.ServeHTTP(w, r)
}

func openWebUIGatewayPatch(prefix string) string {
	// Prefix absolute fetch/XHR/WebSocket/EventSource/history URLs so runtime stays under /t/open-webui.
	return `<script>(function(){var P=` + strconv.Quote(prefix) + `;` +
		`if(location.pathname===P){history.replaceState(null,"",P+"/"+location.search+location.hash);}` +
		`function fix(u){if(typeof u!=="string")return u;if(!u||u.startsWith(P+"/")||u===P||u.startsWith("/t/"))return u;if(u.startsWith("/")&&!u.startsWith("//"))return P+u;return u;}` +
		`var F=window.fetch;window.fetch=function(i,n){if(typeof i==="string")i=fix(i);else if(i&&typeof i.url==="string"){try{i=new Request(fix(i.url),i);}catch(e){}}return F.call(this,i,n);};` +
		`var X=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(m,u){if(typeof u==="string")arguments[1]=fix(u);return X.apply(this,arguments);};` +
		`var WS=window.WebSocket;window.WebSocket=function(u,p){if(typeof u==="string"){if(u.indexOf("ws://")===0||u.indexOf("wss://")===0){try{var x=new URL(u);if(x.pathname.indexOf(P+"/")!==0){x.pathname=P+x.pathname;u=x.toString();}}catch(e){}}else u=fix(u);}return p===undefined?new WS(u):new WS(u,p);};window.WebSocket.prototype=WS.prototype;` +
		`if(window.EventSource){var ES=window.EventSource;window.EventSource=function(u,o){return o===undefined?new ES(fix(u)):new ES(fix(u),o);};window.EventSource.prototype=ES.prototype;}` +
		`var _ps=history.pushState,_rs=history.replaceState;history.pushState=function(s,t,u){if(typeof u==="string")u=fix(u);return _ps.call(this,s,t,u);};history.replaceState=function(s,t,u){if(typeof u==="string")u=fix(u);return _rs.call(this,s,t,u);};` +
		`})();</script>`
}

func rewriteUpstreamBody(resp *http.Response, prefix string, toolID string) error {
	ct := resp.Header.Get("Content-Type")
	if resp.Body == nil || resp.StatusCode >= 300 {
		return nil
	}
	isHTML := strings.Contains(ct, "text/html")
	isCSS := strings.Contains(ct, "text/css")
	isJS := strings.Contains(ct, "javascript") || strings.Contains(ct, "ecmascript")
	if !isHTML && !isCSS && !isJS {
		return nil
	}

	raw, err := io.ReadAll(resp.Body)
	resp.Body.Close()
	if err != nil {
		return err
	}

	enc := resp.Header.Get("Content-Encoding")
	var body []byte
	switch enc {
	case "gzip":
		gr, gerr := gzip.NewReader(bytes.NewReader(raw))
		if gerr != nil {
			resp.Body = io.NopCloser(bytes.NewReader(raw))
			return nil
		}
		body, err = io.ReadAll(gr)
		gr.Close()
		if err != nil {
			resp.Body = io.NopCloser(bytes.NewReader(raw))
			return nil
		}
	case "", "identity":
		body = raw
	default:
		resp.Body = io.NopCloser(bytes.NewReader(raw))
		return nil
	}

	s := string(body)
	if isHTML || isCSS {
		s = reAbsAppPath.ReplaceAllString(s, `${1}`+prefix+`/${2}${3}`)
	}
	if isJS || isHTML {
		s = reStreamlitJSPath.ReplaceAllString(s, `${1}`+prefix+`/_stcore${2}`)
	}
	// Open WebUI (SvelteKit): force asset/API resolution under the gateway prefix.
	if toolID == "open-webui" {
		if isJS {
			s = reAbsAppPath.ReplaceAllString(s, `${1}`+prefix+`/${2}${3}`)
		}
		if isHTML {
			s = reSvelteKitBase.ReplaceAllString(s, `${1}"`+prefix+`"`)
			// Do NOT inject <base href> — it fights SvelteKit's runtime base and
			// produces client-side "404: Not Found" while /api/config still 200s.
			patch := openWebUIGatewayPatch(prefix)
			if strings.Contains(s, "<head>") {
				s = strings.Replace(s, "<head>", "<head>"+patch, 1)
			} else if strings.Contains(s, "<head ") {
				idx := strings.Index(s, "<head")
				end := strings.Index(s[idx:], ">")
				if end > 0 {
					ins := idx + end + 1
					s = s[:ins] + patch + s[ins:]
				}
			}
		}
	}

	out := []byte(s)
	resp.Body = io.NopCloser(bytes.NewReader(out))
	resp.ContentLength = int64(len(out))
	resp.Header.Set("Content-Length", fmt.Sprintf("%d", len(out)))
	resp.Header.Del("Content-Encoding")
	return nil
}

func targetPort(u *url.URL) string {
	if u.Port() != "" {
		return u.Port()
	}
	if u.Scheme == "https" {
		return "443"
	}
	return "80"
}

func ensureLeadingSlash(p string) string {
	if p == "" {
		return "/"
	}
	if !strings.HasPrefix(p, "/") {
		return "/" + p
	}
	return p
}

func cloneURL(u *url.URL) *url.URL {
	c := *u
	return &c
}

func probe(ctx context.Context, svc ServiceDef) (string, int64) {
	start := time.Now()
	path := svc.HealthPath
	if path == "" {
		path = "/"
	}
	url := strings.TrimRight(svc.URL, "/") + path
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return "offline", 0
	}
	if svc.ID == "graphify" {
		if key := strings.TrimSpace(os.Getenv("GRAPHIFY_API_KEY")); key != "" {
			req.Header.Set("Authorization", "Bearer "+key)
		}
		req.Header.Set("Accept", "text/event-stream, application/json")
	}
	// MAVERICK /api/health checa Docker+LLM e pode levar ~6–8s
	client := &http.Client{Timeout: 12 * time.Second, Transport: &http.Transport{DialContext: (&net.Dialer{Timeout: 3 * time.Second}).DialContext}}
	resp, err := client.Do(req)
	latency := time.Since(start).Milliseconds()
	if err != nil {
		return "offline", latency
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)
	if resp.StatusCode >= 200 && resp.StatusCode < 400 {
		return "online", latency
	}
	// Graphify MCP: process up but method/accept may not match a plain GET.
	if svc.ID == "graphify" && (resp.StatusCode == 401 || resp.StatusCode == 405 || resp.StatusCode == 406) {
		return "online", latency
	}
	return "offline", latency
}

// wantsMCPStream reports whether the client is an MCP Streamable HTTP client
// (must Accept text/event-stream). Plain browser navigations do not.
func wantsMCPStream(r *http.Request) bool {
	accept := strings.ToLower(r.Header.Get("Accept"))
	if strings.Contains(accept, "text/event-stream") {
		return true
	}
	// Cursor / Continue sometimes send application/json only on initialize.
	if r.Method == http.MethodPost && strings.Contains(accept, "application/json") &&
		!strings.Contains(accept, "text/html") {
		return true
	}
	return false
}

func graphifyPublicURLs(r *http.Request) (mcpURL, aliasURL, localURL string) {
	scheme := requestScheme(r)
	host := strings.TrimSpace(r.Header.Get("X-Forwarded-Host"))
	if host == "" {
		host = r.Host
	}
	if host == "" || strings.HasPrefix(host, "127.0.0.1") || strings.HasPrefix(host, "localhost") {
		host = "irontools.iron-security.com"
		scheme = "https"
	}
	return scheme + "://" + host + "/t/graphify/mcp",
		scheme + "://" + host + "/mcp/graphify",
		"http://127.0.0.1:8792/mcp"
}

func writeGraphifyCursorConfig(w http.ResponseWriter, r *http.Request) {
	mcpURL, _, _ := graphifyPublicURLs(r)
	key := graphifyAPIKey()
	payload := map[string]any{
		"mcpServers": map[string]any{
			"graphify": map[string]any{
				"url": mcpURL,
				"headers": map[string]string{
					"Authorization": "Bearer " + key,
				},
			},
		},
	}
	body, _ := json.MarshalIndent(payload, "", "  ")
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Content-Disposition", `attachment; filename="graphify-mcp.json"`)
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	w.Write(append(body, '\n'))
}

func writeGraphifyContinueConfig(w http.ResponseWriter, r *http.Request) {
	mcpURL, _, _ := graphifyPublicURLs(r)
	key := graphifyAPIKey()
	body := fmt.Sprintf(`name: Graphify
version: 0.0.1
schema: v1
mcpServers:
  - name: Graphify
    type: streamable-http
    url: %s
    apiKey: %s
    requestOptions:
      headers:
        Authorization: Bearer %s
`, mcpURL, key, key)
	w.Header().Set("Content-Type", "text/yaml; charset=utf-8")
	w.Header().Set("Content-Disposition", `attachment; filename="graphify-mcp.yaml"`)
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	io.WriteString(w, body)
}

func writeGraphifyLanding(w http.ResponseWriter, r *http.Request) {
	publicMCP, aliasMCP, localMCP := graphifyPublicURLs(r)
	key := graphifyAPIKey()
	keyJSON, _ := json.Marshal(key)
	cursorJSON, _ := json.Marshal(map[string]any{
		"mcpServers": map[string]any{
			"graphify": map[string]any{
				"url": publicMCP,
				"headers": map[string]string{
					"Authorization": "Bearer " + key,
				},
			},
		},
	})
	continueYAML := fmt.Sprintf(`name: Graphify
version: 0.0.1
schema: v1
mcpServers:
  - name: Graphify
    type: streamable-http
    url: %s
    apiKey: %s
`, publicMCP, key)
	continueJSON, _ := json.Marshal(continueYAML)
	bearerJSON, _ := json.Marshal("Bearer " + key)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Graphify MCP · Iron Hub</title>
  <style>
    :root { color-scheme: dark; --bg:#0b0f14; --card:#121820; --line:#243041; --text:#e8eef7; --muted:#9aa7b8; --accent:#00d9ff; --ok:#3dd68c; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background:radial-gradient(1200px 600px at 10%% -10%%,#123 0%%,var(--bg) 55%%); color:var(--text); min-height:100vh; }
    main { max-width:760px; margin:0 auto; padding:48px 20px; }
    h1 { margin:0 0 8px; font-size:1.75rem; letter-spacing:-0.02em; }
    p { color:var(--muted); line-height:1.5; }
    .card { margin-top:20px; border:1px solid var(--line); background:var(--card); border-radius:14px; padding:18px 20px; }
    .actions { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:16px; }
    @media (max-width:640px) { .actions { grid-template-columns:1fr; } }
    .btn {
      display:flex; flex-direction:column; align-items:flex-start; gap:4px;
      padding:14px 16px; border-radius:12px; border:1px solid var(--line);
      text-decoration:none; color:var(--text); background:#162032; cursor:pointer; font:inherit; text-align:left;
    }
    .btn strong { font-size:1rem; }
    .btn span { color:var(--muted); font-size:0.85rem; line-height:1.35; }
    .btn.primary { background:linear-gradient(180deg,#0b6a7a,#084); border-color:#1a8; }
    .btn.ok { outline:1px solid var(--ok); }
    code { padding:2px 6px; border-radius:6px; background:#0a1018; border:1px solid var(--line); font-family: ui-monospace, Menlo, monospace; font-size:0.85rem; }
    .url { display:block; margin-top:8px; padding:10px 12px; border-radius:10px; background:#0a1018; border:1px solid var(--line); color:var(--accent); word-break:break-all; font-family: ui-monospace, Menlo, monospace; font-size:0.82rem; }
    .note { margin-top:14px; padding:12px 14px; border-radius:10px; border:1px solid #3a4a2a; background:#142016; color:#cfe8c8; }
    ul { margin:10px 0 0; padding-left:18px; color:var(--muted); }
    .row { display:flex; gap:12px; flex-wrap:wrap; margin-top:18px; }
  </style>
</head>
<body>
  <main>
    <h1>Graphify MCP</h1>
    <p>Knowledge graph do Iron Tools — acesso MCP com credenciais prontas (Bearer incluso nos botões).</p>
    <div class="note">Não abre como página web. Use os botões abaixo para baixar/copiar a config já autenticada para Cursor ou Continue.</div>

    <div class="card">
      <strong>Acesso com credenciais</strong>
      <div class="actions">
        <a class="btn primary" href="/t/graphify/config/cursor.json" download="graphify-mcp.json">
          <strong>Baixar config Cursor</strong>
          <span>mcp.json com URL + Authorization Bearer</span>
        </a>
        <a class="btn primary" href="/t/graphify/config/continue.yaml" download="graphify-mcp.yaml">
          <strong>Baixar config Continue</strong>
          <span>YAML streamable-http com apiKey</span>
        </a>
        <button type="button" class="btn" id="btnCursorCopy">
          <strong>Copiar config Cursor</strong>
          <span>JSON pronto para ~/.cursor/mcp.json</span>
        </button>
        <button type="button" class="btn" id="btnContinueCopy">
          <strong>Copiar config Continue</strong>
          <span>YAML pronto para .continue/mcpServers/</span>
        </button>
        <button type="button" class="btn" id="btnBearer">
          <strong>Copiar Bearer</strong>
          <span>Authorization header da API key</span>
        </button>
        <button type="button" class="btn" id="btnLocal">
          <strong>Copiar URL local + key</strong>
          <span>%s com Bearer</span>
        </button>
      </div>
    </div>

    <div class="card">
      <strong>Endpoints</strong>
      <span class="url">%s</span>
      <span class="url">%s</span>
      <span class="url">%s</span>
    </div>

    <div class="card">
      <strong>Tools</strong>
      <ul>
        <li>query_graph · get_node · get_neighbors · shortest_path</li>
        <li>god_nodes · graph_stats · get_community</li>
        <li>list_prs · get_pr_impact · triage_prs</li>
      </ul>
    </div>

    <div class="row">
      <a class="btn" href="/console/" style="flex-direction:row;align-items:center"><strong>Voltar ao Hub</strong></a>
    </div>
  </main>
  <script>
    const KEY = %s;
    const CURSOR = %s;
    const CONTINUE_YAML = %s;
    const BEARER = %s;
    const LOCAL = %s;
    function flash(btn) {
      btn.classList.add('ok');
      const old = btn.querySelector('strong').textContent;
      btn.querySelector('strong').textContent = 'Copiado!';
      setTimeout(() => { btn.classList.remove('ok'); btn.querySelector('strong').textContent = old; }, 1200);
    }
    async function copyText(text, btn) {
      await navigator.clipboard.writeText(text);
      flash(btn);
    }
    document.getElementById('btnCursorCopy').onclick = (e) => copyText(JSON.stringify(CURSOR, null, 2) + '\n', e.currentTarget);
    document.getElementById('btnContinueCopy').onclick = (e) => copyText(CONTINUE_YAML, e.currentTarget);
    document.getElementById('btnBearer').onclick = (e) => copyText(BEARER, e.currentTarget);
    document.getElementById('btnLocal').onclick = (e) => {
      const cfg = { mcpServers: { graphify: { url: LOCAL, headers: { Authorization: 'Bearer ' + KEY } } } };
      copyText(JSON.stringify(cfg, null, 2) + '\n', e.currentTarget);
    };
  </script>
</body>
</html>`, localMCP, publicMCP, aliasMCP, localMCP, keyJSON, cursorJSON, continueJSON, bearerJSON, func() string {
		b, _ := json.Marshal(localMCP)
		return string(b)
	}())
}

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

// --- session tokens: base64url(payload).base64url(hmac) ---

func issueSession(username string) (string, error) {
	exp := time.Now().Add(sessionTTL).Unix()
	payload := fmt.Sprintf("%s|%d", username, exp)
	sig := sign([]byte(payload))
	return base64.RawURLEncoding.EncodeToString([]byte(payload)) + "." + base64.RawURLEncoding.EncodeToString(sig), nil
}

func sessionUser(r *http.Request) (string, bool) {
	c, err := r.Cookie(sessionCookie)
	if err != nil || c.Value == "" {
		return "", false
	}
	parts := strings.Split(c.Value, ".")
	if len(parts) != 2 {
		return "", false
	}
	payload, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return "", false
	}
	sig, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", false
	}
	if !hmac.Equal(sign(payload), sig) {
		return "", false
	}
	fields := strings.Split(string(payload), "|")
	if len(fields) != 2 {
		return "", false
	}
	var exp int64
	if _, err := fmt.Sscanf(fields[1], "%d", &exp); err != nil {
		return "", false
	}
	if time.Now().Unix() > exp {
		return "", false
	}
	return fields[0], true
}

func sign(payload []byte) []byte {
	m := hmac.New(sha256.New, sessionKey)
	m.Write(payload)
	return m.Sum(nil)
}
