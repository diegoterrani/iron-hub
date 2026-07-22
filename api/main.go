package main

import (
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

//go:embed all:dist
var webFS embed.FS

type ServiceDef struct {
	ID         string `json:"id"`
	URL        string `json:"url,omitempty"`
	HealthPath string `json:"healthPath,omitempty"`
	Type       string `json:"type"`
}

type HealthEntry struct {
	Status    string `json:"status"`
	LatencyMs int64  `json:"latency_ms,omitempty"`
}

type HealthResponse struct {
	Services  map[string]HealthEntry `json:"services"`
	CheckedAt string                 `json:"checked_at"`
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
	{ID: "darkweb-tracker", URL: "http://127.0.0.1:13200", HealthPath: "/", Type: "web"},
	{ID: "darkweb-observatory", URL: "http://127.0.0.1:8791", HealthPath: "/api/health", Type: "web"},
	{ID: "robin", URL: "http://127.0.0.1:18501", HealthPath: "/_stcore/health", Type: "web"},
	{ID: "open-webui", URL: "http://127.0.0.1:3080", HealthPath: "/health", Type: "web"},
	{ID: "moneyprinter", URL: "http://127.0.0.1:8502", HealthPath: "/_stcore/health", Type: "web"},
	{ID: "bot-live", URL: "http://127.0.0.1:3000", HealthPath: "/", Type: "web"},
	{ID: "onboarding", URL: "http://127.0.0.1:3001", HealthPath: "/", Type: "web"},
}

func main() {
	port := os.Getenv("IRON_HUB_PORT")
	if port == "" {
		port = "3900"
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/health", handleHealth)
	mux.HandleFunc("/api/services", handleServices)

	distFS, err := fs.Sub(webFS, "dist")
	if err != nil {
		log.Fatalf("dist fs: %v", err)
	}
	fileServer := http.FileServer(http.FS(distFS))
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/api/") {
			http.NotFound(w, r)
			return
		}
		path := strings.TrimPrefix(r.URL.Path, "/")
		if path == "" {
			serveIndex(w, distFS)
			return
		}
		if _, err := distFS.Open(path); err != nil {
			serveIndex(w, distFS)
			return
		}
		fileServer.ServeHTTP(w, r)
	})

	addr := ":" + port
	log.Printf("Iron Hub listening on http://127.0.0.1:%s", port)
	log.Fatal(http.ListenAndServe(addr, withCORS(mux)))
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

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func handleServices(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(services)
}

func handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 8*time.Second)
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

	resp := HealthResponse{
		Services:  results,
		CheckedAt: time.Now().UTC().Format(time.RFC3339),
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
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

	client := &http.Client{Timeout: 10 * time.Second}
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
	return "offline", latency
}

func init() {
	if _, err := webFS.Open("dist/index.html"); err != nil {
		fmt.Fprintf(os.Stderr, "warning: dist/ not embedded yet — run npm run build first\n")
	}
}
