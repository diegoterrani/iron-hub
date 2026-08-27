# irontools.iron-security.com — HTTPS Hub

## Pronto neste host
- nginx site `irontools-hub` (HTTP → Hub `:3900`, ACME webroot `/var/www/certbot`)
- certbot instalado
- script: `deploy/issue-letsencrypt.sh`
- watcher em background: `deploy/wait-and-issue-cert.sh` (log `/tmp/irontools-le-issue.log`)

## O que falta (fora deste host)

### 1) DNS Cloudflare
Criar registro:
- Type: `A`
- Name: `irontools`
- Content: `3.213.184.81`
- Proxy: **OFF** (cinza) na 1ª emissão do certificado; depois pode ligar o proxy se quiser

### 2) AWS Security Group `sg-097ac6e4197ebfbb7`
Inbound:
- TCP **80** from `0.0.0.0/0` (Let's Encrypt HTTP-01)
- TCP **443** from `0.0.0.0/0` (Hub HTTPS)

### 3) Emitir cert (se o watcher não pegar)
```bash
sudo /home/ubuntu/iron-tools/iron-hub/deploy/issue-letsencrypt.sh
```

Hub URL final: **https://irontools.iron-security.com/**
