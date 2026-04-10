#!/bin/bash
# ============================================================
# deploy-vps.sh — Deploy Pedro Desktop v2.0 na VPS
# ============================================================
# Uso: ./deploy-vps.sh
# Executa via SSH na VPS: ssh prod 'bash -s' < deploy-vps.sh
# ============================================================

set -euo pipefail

DESKTOP_DIR="/opt/pedro-desktop"
API_PORT=8765
WEBUI_PORT=8766
DOMAIN="desktop.plenus.advocaciaplenus.com"
PG_PASSWORD="${PG_PASSWORD:-Deuseeu_2025}"
PG_USER="${PG_USER:-plenus_app}"
LITELLM_API_KEY="${LITELLM_API_KEY:-sk-litellm-internal}"
FIRECRAWL_API_KEY="${FIRECRAWL_API_KEY:-}"
DATAJUD_API_KEY="${DATAJUD_API_KEY:-}"
CNJ_API_KEY="${CNJ_API_KEY:-}"

echo "══════════════════════════════════════════"
echo "🚀 Pedro Desktop v2.0 — Deploy VPS"
echo "══════════════════════════════════════════"
echo ""
echo "📍 Destino: $DESKTOP_DIR"
echo "🌐 Domínio: $DOMAIN"
echo "📡 API:    porta $API_PORT"
echo "🖥️  Web:    porta $WEBUI_PORT"
echo ""

# ── 1. Instalar dependências do sistema ─────────────────────
echo "[1/7] Instalando dependências do sistema..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx curl jq > /dev/null 2>&1
echo "✅ Sistema pronto"

# ── 2. Criar diretório ──────────────────────────────────────
echo "[2/7] Criando diretório $DESKTOP_DIR..."
mkdir -p "$DESKTOP_DIR"
cd "$DESKTOP_DIR"

# ── 3. Receber arquivos ─────────────────────────────────────
echo "[3/7] Recebendo arquivos..."
# Os arquivos são enviados via scp antes deste script rodar
# Se não existem, o deploy para
if [ ! -f "$DESKTOP_DIR/orquestrador.py" ]; then
    echo "❌ orquestrador.py não encontrado!"
    echo "Execute primeiro: scp -r pedro-desktop/ prod:$DESKTOP_DIR/"
    exit 1
fi
echo "✅ Arquivos presentes"

# ── 4. Criar venv e instalar deps ───────────────────────────
echo "[4/7] Criando ambiente virtual..."
python3 -m venv "$DESKTOP_DIR/venv"
source "$DESKTOP_DIR/venv/bin/activate"

if [ -f "$DESKTOP_DIR/requirements.txt" ]; then
    pip install -r "$DESKTOP_DIR/requirements.txt" -q 2>&1 | tail -1
else
    pip install fastapi uvicorn python-multipart redis requests chardet psycopg2-binary streamlit -q 2>&1 | tail -1
fi
echo "✅ Python pronto"

# ── 5. Criar systemd services ───────────────────────────────
echo "[5/7] Configurando systemd services..."

# API Service
cat > /etc/systemd/system/pedro-desktop-api.service << EOF
[Unit]
Description=Pedro Desktop API
After=network.target redis-server.service nginx.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pedro-desktop
Environment="OPENAI_API_KEY=$LITELLM_API_KEY"
Environment="PG_USER=$PG_USER"
Environment="PG_PASSWORD=$PG_PASSWORD"
Environment="FIRECRAWL_API_KEY=$FIRECRAWL_API_KEY"
Environment="DATAJUD_API_KEY=$DATAJUD_API_KEY"
Environment="CNJ_API_KEY=$CNJ_API_KEY"
ExecStart=/opt/pedro-desktop/venv/bin/python3 /opt/pedro-desktop/orquestrador.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Web UI Service
cat > /etc/systemd/system/pedro-desktop-webui.service << EOF
[Unit]
Description=Pedro Desktop Web UI
After=network.target pedro-desktop-api.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pedro-desktop
Environment="OPENAI_API_KEY=$LITELLM_API_KEY"
Environment="PG_USER=$PG_USER"
Environment="PG_PASSWORD=$PG_PASSWORD"
Environment="FIRECRAWL_API_KEY=$FIRECRAWL_API_KEY"
Environment="DATAJUD_API_KEY=$DATAJUD_API_KEY"
Environment="CNJ_API_KEY=$CNJ_API_KEY"
ExecStart=/opt/pedro-desktop/venv/bin/streamlit run /opt/pedro-desktop/web_ui.py --server.port 8766 --server.headless true --server.address 127.0.0.1 --theme.base light --theme.primaryColor "#1a73e8"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pedro-desktop-api
systemctl enable pedro-desktop-webui
echo "✅ Services criados e habilitados"

# ── 6. Configurar Nginx ─────────────────────────────────────
echo "[6/7] Configurando Nginx..."

cat > /etc/nginx/sites-available/pedro-desktop << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:$API_PORT/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (para futuros upgrades)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts generosos para IA
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Web UI (Streamlit)
    location / {
        proxy_pass http://127.0.0.1:$WEBUI_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (Streamlit precisa)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
EOF

ln -sf /etc/nginx/sites-available/pedro-desktop /etc/nginx/sites-enabled/
nginx -t > /dev/null 2>&1 && systemctl reload nginx
echo "✅ Nginx configurado"

# ── 7. Certbot HTTPS ────────────────────────────────────────
echo "[7/7] Configurando HTTPS com Let's Encrypt..."

# Verifica se DNS está apontando
echo "⏳ Verificando DNS..."
DNS_IP=$(dig +short $DOMAIN 2>/dev/null | head -1 || echo "N/A")
if [ "$DNS_IP" = "76.13.161.29" ]; then
    echo "✅ DNS OK: $DOMAIN → $DNS_IP"
    
    # Roda certbot
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --register-unsafely-without-email 2>&1 | tail -5
    echo "✅ HTTPS configurado!"
else
    echo "⚠️ DNS ainda não propagou ($DOMAIN → $DNS_IP)"
    echo "⚠️ Execute manualmente depois:"
    echo "   certbot --nginx -d $DOMAIN"
fi

# ── Iniciar serviços ────────────────────────────────────────
echo ""
echo "🚀 Iniciando serviços..."
systemctl start pedro-desktop-api
systemctl start pedro-desktop-webui

sleep 5

# Status
echo ""
echo "══════════════════════════════════════════"
echo "📊 STATUS DOS SERVIÇOS"
echo "══════════════════════════════════════════"
echo -n "API:      "
systemctl is-active pedro-desktop-api 2>/dev/null || echo "falhou"
echo -n "Web UI:   "
systemctl is-active pedro-desktop-webui 2>/dev/null || echo "falhou"
echo -n "Nginx:    "
systemctl is-active nginx 2>/dev/null || echo "falhou"

echo ""
echo "══════════════════════════════════════════"
echo "✅ Pedro Desktop v2.0 — Deploy Concluído!"
echo "══════════════════════════════════════════"
echo ""
echo "🌐 Web UI:  https://$DOMAIN"
echo "📡 API:     https://$DOMAIN/api/"
echo "📖 Docs:    https://$DOMAIN/api/docs"
echo ""
echo "📋 Comandos úteis:"
echo "  systemctl status pedro-desktop-api"
echo "  systemctl status pedro-desktop-webui"
echo "  journalctl -u pedro-desktop-api -f"
echo "  journalctl -u pedro-desktop-webui -f"
echo ""
