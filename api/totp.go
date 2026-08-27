package main

import (
	"bytes"
	"crypto/hmac"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"image/png"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
	qrcode "github.com/skip2/go-qrcode"
)

const (
	totpIssuer      = "Iron Security Hub"
	pending2FATTL   = 3 * time.Minute
	totpSecretFile  = "totp.json"
	totpPendingFile = "totp.pending.json"
)

type totpStore struct {
	Enabled bool   `json:"enabled"`
	Secret  string `json:"secret"` // base32
}

var (
	totpMu       sync.RWMutex
	totpState    totpStore
	pendingSetup string // temporary secret while enabling
	totpDataDir  string
)

func initTOTP(root string) {
	if env := strings.TrimSpace(os.Getenv("IRON_HUB_DATA")); env != "" {
		totpDataDir = env
	} else {
		totpDataDir = filepath.Join(root, "data")
	}
	_ = os.MkdirAll(totpDataDir, 0o700)

	// Env override (optional)
	if sec := strings.TrimSpace(os.Getenv("IRON_HUB_TOTP_SECRET")); sec != "" {
		totpState = totpStore{Enabled: true, Secret: sec}
		log.Printf("2FA: loaded secret from IRON_HUB_TOTP_SECRET")
		return
	}
	path := filepath.Join(totpDataDir, totpSecretFile)
	data, err := os.ReadFile(path)
	if err == nil {
		var st totpStore
		if json.Unmarshal(data, &st) == nil && st.Enabled && st.Secret != "" {
			totpState = st
			log.Printf("2FA: loaded enabled secret from %s", path)
		}
	}
	// Restore in-progress setup across restarts
	if pend, err := os.ReadFile(filepath.Join(totpDataDir, totpPendingFile)); err == nil {
		var st totpStore
		if json.Unmarshal(pend, &st) == nil && st.Secret != "" && !totpState.Enabled {
			pendingSetup = st.Secret
			log.Printf("2FA: restored pending setup secret")
		}
	}
}

func totpEnabled() bool {
	totpMu.RLock()
	defer totpMu.RUnlock()
	return totpState.Enabled && totpState.Secret != ""
}

func totpSecret() string {
	totpMu.RLock()
	defer totpMu.RUnlock()
	return totpState.Secret
}

func writeTOTPFile(name string, st totpStore) error {
	if err := os.MkdirAll(totpDataDir, 0o700); err != nil {
		return err
	}
	path := filepath.Join(totpDataDir, name)
	raw, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, raw, 0o600); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func persistTOTP(st totpStore) error {
	if err := writeTOTPFile(totpSecretFile, st); err != nil {
		return err
	}
	// clear pending setup file when enabling/disabling
	_ = os.Remove(filepath.Join(totpDataDir, totpPendingFile))
	return nil
}

func persistPendingSetup(secret string) error {
	return writeTOTPFile(totpPendingFile, totpStore{Enabled: false, Secret: secret})
}

func validateTOTP(code string) bool {
	code = strings.TrimSpace(code)
	if code == "" {
		return false
	}
	sec := totpSecret()
	if sec == "" {
		return false
	}
	ok, err := totp.ValidateCustom(code, sec, time.Now(), totp.ValidateOpts{
		Period:    30,
		Skew:      1,
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	})
	return err == nil && ok
}

func issuePending2FA(username string) (string, error) {
	exp := time.Now().Add(pending2FATTL).Unix()
	payload := fmt.Sprintf("2fa|%s|%d", username, exp)
	sig := sign([]byte(payload))
	return base64.RawURLEncoding.EncodeToString([]byte(payload)) + "." + base64.RawURLEncoding.EncodeToString(sig), nil
}

func parsePending2FA(token string) (string, bool) {
	parts := strings.Split(token, ".")
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
	if len(fields) != 3 || fields[0] != "2fa" {
		return "", false
	}
	var exp int64
	if _, err := fmt.Sscanf(fields[2], "%d", &exp); err != nil {
		return "", false
	}
	if time.Now().Unix() > exp {
		return "", false
	}
	return fields[1], true
}

type login2FARequest struct {
	PendingToken string `json:"pending_token"`
	Code         string `json:"code"`
}

type totpEnableRequest struct {
	Code string `json:"code"`
}

type totpDisableRequest struct {
	Password string `json:"password"`
	Code     string `json:"code"`
}

func handleLogin2FA(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	if !totpEnabled() {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "2FA não está ativo"})
		return
	}
	var req login2FARequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "invalid json"})
		return
	}
	user, ok := parsePending2FA(req.PendingToken)
	if !ok || user != hubUser {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "token 2FA inválido ou expirado"})
		return
	}
	if !validateTOTP(req.Code) {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "código 2FA inválido"})
		return
	}
	if err := setSessionCookie(w, r, user); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "session error"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "user": user})
}

func handle2FAStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":      true,
		"enabled": totpEnabled(),
	})
}

func handle2FASetup(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	if totpEnabled() {
		writeJSON(w, http.StatusConflict, map[string]any{"ok": false, "error": "2FA já está ativo — desative antes de reconfigurar"})
		return
	}
	key, err := totp.Generate(totp.GenerateOpts{
		Issuer:      totpIssuer,
		AccountName: hubUser,
		Period:      30,
		Digits:      otp.DigitsSix,
		Algorithm:   otp.AlgorithmSHA1,
	})
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "falha ao gerar secret"})
		return
	}
	totpMu.Lock()
	pendingSetup = key.Secret()
	totpMu.Unlock()
	if err := persistPendingSetup(key.Secret()); err != nil {
		log.Printf("2FA: failed to persist pending setup: %v", err)
	}

	pngBytes, err := qrcode.Encode(key.URL(), qrcode.Medium, 256)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "falha ao gerar QR"})
		return
	}
	// Ensure valid PNG (library returns PNG already)
	if _, err := png.Decode(bytes.NewReader(pngBytes)); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "QR inválido"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":         true,
		"secret":     key.Secret(),
		"otpauth_url": key.URL(),
		"qr_png_base64": base64.StdEncoding.EncodeToString(pngBytes),
		"issuer":     totpIssuer,
		"account":    hubUser,
	})
}

func handle2FAEnable(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	var req totpEnableRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "invalid json"})
		return
	}
	totpMu.Lock()
	sec := pendingSetup
	totpMu.Unlock()
	if sec == "" {
		// recover from disk if process restarted mid-setup
		if pend, err := os.ReadFile(filepath.Join(totpDataDir, totpPendingFile)); err == nil {
			var st totpStore
			if json.Unmarshal(pend, &st) == nil {
				sec = st.Secret
				totpMu.Lock()
				pendingSetup = sec
				totpMu.Unlock()
			}
		}
	}
	if sec == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "inicie o setup 2FA primeiro (Gerar QR)"})
		return
	}
	ok, err := totp.ValidateCustom(strings.TrimSpace(req.Code), sec, time.Now(), totp.ValidateOpts{
		Period:    30,
		Skew:      1,
		Digits:    otp.DigitsSix,
		Algorithm: otp.AlgorithmSHA1,
	})
	if err != nil || !ok {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "código inválido — confira o app Authenticator"})
		return
	}
	st := totpStore{Enabled: true, Secret: sec}
	if err := persistTOTP(st); err != nil {
		log.Printf("2FA: persist enable failed: %v", err)
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "falha ao salvar 2FA: " + err.Error()})
		return
	}
	totpMu.Lock()
	totpState = st
	pendingSetup = ""
	totpMu.Unlock()
	log.Printf("2FA: ENABLED and saved to %s", filepath.Join(totpDataDir, totpSecretFile))
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "enabled": true})
}

func handle2FADisable(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"ok": false, "error": "method not allowed"})
		return
	}
	if !totpEnabled() {
		writeJSON(w, http.StatusOK, map[string]any{"ok": true, "enabled": false})
		return
	}
	var req totpDisableRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"ok": false, "error": "invalid json"})
		return
	}
	if req.Password != hubPass {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "senha inválida"})
		return
	}
	if !validateTOTP(req.Code) {
		time.Sleep(200 * time.Millisecond)
		writeJSON(w, http.StatusUnauthorized, map[string]any{"ok": false, "error": "código 2FA inválido"})
		return
	}
	st := totpStore{Enabled: false, Secret: ""}
	if err := persistTOTP(st); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"ok": false, "error": "falha ao desativar 2FA"})
		return
	}
	totpMu.Lock()
	totpState = st
	pendingSetup = ""
	totpMu.Unlock()
	writeJSON(w, http.StatusOK, map[string]any{"ok": true, "enabled": false})
}

func setSessionCookie(w http.ResponseWriter, r *http.Request, username string) error {
	token, err := issueSession(username)
	if err != nil {
		return err
	}
	http.SetCookie(w, &http.Cookie{
		Name:     sessionCookie,
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		Secure:   requestScheme(r) == "https",
		SameSite: http.SameSiteLaxMode,
		MaxAge:   int(sessionTTL.Seconds()),
	})
	return nil
}
