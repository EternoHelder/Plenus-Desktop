#!/bin/bash
# ============================================================
# upload-vps.sh — Envia arquivos e executa deploy na VPS
# ============================================================
# Uso: ./upload-vps.sh
# ============================================================

set -euo pipefail

VPS="root@srv1291514"
REMOTE_DIR="/opt/pedro-desktop"
LOCAL_DIR="/tmp/Plenus-Desktop-temp"

echo "══════════════════════════════════════════"
echo "📤 Upload + Deploy VPS"
echo "══════════════════════════════════════════"
echo ""
echo "📍 De: $LOCAL_DIR"
echo "📍 Para: $VPS:$REMOTE_DIR"
echo ""

# ── 1. Criar dir remoto ─────────────────────────────────────
echo "[1/3] Preparando VPS..."
ssh $VPS "mkdir -p $REMOTE_DIR"

# ── 2. Enviar arquivos ──────────────────────────────────────
echo "[2/3] Enviando arquivos..."
scp -q \
    "$LOCAL_DIR/orquestrador.py" \
    "$LOCAL_DIR/mcp_connectors.py" \
    "$LOCAL_DIR/web_ui.py" \
    "$LOCAL_DIR/requirements.txt" \
    "$VPS:$REMOTE_DIR/"

echo "✅ Arquivos enviados:"
ssh $VPS "ls -lh $REMOTE_DIR/*.py $REMOTE_DIR/*.txt 2>/dev/null"

# ── 3. Executar deploy ──────────────────────────────────────
echo ""
echo "[3/3] Executando deploy na VPS..."
echo ""
scp -q "$LOCAL_DIR/deploy-vps.sh" "$VPS:/tmp/deploy-vps.sh"
ssh $VPS "bash /tmp/deploy-vps.sh"

echo ""
echo "══════════════════════════════════════════"
echo "✅ Deploy completo!"
echo "══════════════════════════════════════════"
