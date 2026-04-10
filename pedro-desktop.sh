#!/bin/bash
# ============================================================
# pedro-desktop.sh — Inicializa Pedro Desktop v2.0
# ============================================================
# Uso:
#   pedro-desktop              # Inicia servidor (porta 8765)
#   pedro-desktop status       # Verifica status
#   pedro-desktop stop         # Para servidor
#   pedro-desktop test         # Testa conexão
# ============================================================

set -euo pipefail

DESKTOP_DIR="/opt/pedro-desktop"
VENV="$DESKTOP_DIR/venv"
PIDFILE="/tmp/pedro-desktop.pid"
PORT=8765
API_KEY="${OPENAI_API_KEY:-sk-litellm-internal}"

case "${1:-start}" in
    start)
        echo "🚀 Pedro Desktop v2.0"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Verifica se já está rodando
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "✅ Já rodando (PID $PID)"
                echo "🌐 http://localhost:$PORT"
                echo "📖 Docs: http://localhost:$PORT/docs"
                exit 0
            else
                rm -f "$PIDFILE"
            fi
        fi
        
        # Verifica API key
        if [ -z "$API_KEY" ]; then
            echo "❌ OPENAI_API_KEY não configurada"
            exit 1
        fi
        
        # Ativa venv e inicia
        export OPENAI_API_KEY="$API_KEY"
        source "$VENV/bin/activate"
        
        echo "📡 Iniciando servidor na porta $PORT..."
        echo ""
        
        nohup python3 "$DESKTOP_DIR/orquestrador.py" > "$DESKTOP_DIR/server.log" 2>&1 &
        PID=$!
        echo $PID > "$PIDFILE"
        
        # Espera inicializar
        echo "⏳ Aguardando inicialização..."
        for i in $(seq 1 15); do
            if curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
                echo ""
                echo "══════════════════════════════════════════"
                echo "✅ Pedro Desktop v2.0 ONLINE"
                echo "══════════════════════════════════════════"
                echo "🌐 API:     http://localhost:$PORT"
                echo "📖 Docs:    http://localhost:$PORT/docs"
                echo "🧪 Swagger: http://localhost:$PORT/redoc"
                echo "📋 PID:     $PID"
                echo "📝 Log:     $DESKTOP_DIR/server.log"
                echo "══════════════════════════════════════════"
                echo ""
                echo "# Teste rápido:"
                echo "curl -s http://localhost:$PORT/ | python3 -m json.tool"
                exit 0
            fi
            sleep 1
            echo -n "."
        done
        
        echo ""
        echo "❌ Timeout - servidor não respondeu"
        echo "📝 Log:"
        tail -20 "$DESKTOP_DIR/server.log"
        exit 1
        ;;
    
    status)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "✅ Pedro Desktop v2.0 rodando (PID $PID)"
                echo "🌐 http://localhost:$PORT"
                
                # Health check
                HEALTH=$(curl -s "http://localhost:$PORT/health" 2>/dev/null || echo '{"api":"offline"}')
                echo "📊 Health: $HEALTH"
            else
                echo "❌ Processo $PID morto"
                rm -f "$PIDFILE"
            fi
        else
            echo "❌ Pedro Desktop não está rodando"
            echo "Inicie com: pedro-desktop"
        fi
        ;;
    
    stop)
        if [ -f "$PIDFILE" ]; then
            PID=$(cat "$PIDFILE")
            kill "$PID" 2>/dev/null && echo "✅ Pedro Desktop parado (PID $PID)" || echo "⚠️ Não foi possível parar"
            rm -f "$PIDFILE"
        else
            echo "ℹ️ Não havia servidor rodando"
            # Mata por porta
            pkill -f "orquestrador.py" 2>/dev/null && echo "✅ Processos encerrados" || true
        fi
        ;;
    
    test)
        echo "🧪 Testando Pedro Desktop..."
        RESP=$(curl -s "http://localhost:$PORT/" 2>/dev/null || echo "OFFLINE")
        if [ "$RESP" = "OFFLINE" ]; then
            echo "❌ Servidor não está rodando"
            echo "Inicie com: pedro-desktop"
        else
            echo "$RESP" | python3 -m json.tool
        fi
        ;;
    
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    
    web)
        echo "🌐 Abrindo Pedro Desktop Web UI..."
        
        # Verifica se servidor API está rodando
        if ! curl -s "http://localhost:$PORT/health" > /dev/null 2>&1; then
            echo "⚠️ Servidor API não está rodando. Iniciando..."
            $0 start
            sleep 3
        fi
        
        # Ativa venv e inicia Streamlit
        source "$VENV/bin/activate"
        export OPENAI_API_KEY="$API_KEY"
        
        echo "🌐 Iniciando Streamlit na porta 8766..."
        echo ""
        
        nohup streamlit run "$DESKTOP_DIR/web_ui.py" \
            --server.port 8766 \
            --server.headless true \
            --server.address localhost \
            --theme.base "light" \
            --theme.primaryColor "#1a73e8" \
            > "$DESKTOP_DIR/webui.log" 2>&1 &
        
        WEBUI_PID=$!
        echo $WEBUI_PID > "/tmp/pedro-desktop-webui.pid"
        
        echo "⏳ Aguardando Streamlit..."
        for i in $(seq 1 10); do
            if curl -s "http://localhost:8766" > /dev/null 2>&1; then
                echo ""
                echo "══════════════════════════════════════════"
                echo "🌐 Pedro Desktop Web UI ONLINE"
                echo "══════════════════════════════════════════"
                echo "🖥️  UI:      http://localhost:8766"
                echo "📡 API:     http://localhost:$PORT"
                echo "📖 Docs:    http://localhost:$PORT/docs"
                echo "══════════════════════════════════════════"
                
                # Tenta abrir no browser
                xdg-open "http://localhost:8766" 2>/dev/null || true
                exit 0
            fi
            sleep 1
            echo -n "."
        done
        
        echo ""
        echo "❌ Timeout - Web UI não respondeu"
        tail -10 "$DESKTOP_DIR/webui.log"
        ;;
    
    stop-webui)
        if [ -f "/tmp/pedro-desktop-webui.pid" ]; then
            PID=$(cat "/tmp/pedro-desktop-webui.pid")
            kill "$PID" 2>/dev/null && echo "✅ Web UI parada" || echo "⚠️ Não foi possível parar"
            rm -f "/tmp/pedro-desktop-webui.pid"
        else
            pkill -f "streamlit.*web_ui.py" 2>/dev/null && echo "✅ Web UI encerrada" || echo "ℹ️ Web UI não estava rodando"
        fi
        ;;
    
    *)
        echo "🐧 Pedro Desktop v2.0"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Uso: pedro-desktop [comando]"
        echo ""
        echo "Comandos:"
        echo "  start      - Inicia servidor API (padrão)"
        echo "  status     - Verifica status"
        echo "  stop       - Para servidor"
        echo "  restart    - Reinicia"
        echo "  web        - Inicia Web UI Streamlit"
        echo "  stop-webui - Para Web UI"
        echo "  test       - Testa conexão"
        ;;
esac
