#!/bin/bash
# ============================================================
# pedro-coder — CLI Avançado do Pedro Desktop v2.0
# ============================================================
# Interface de linha pro Orquestrador FastAPI
# ============================================================
# Uso:
#   pedro-coder "analise este contrato"
#   pedro-coder --file /path/arquivo.pdf "analise"
#   pedro-coder --dir /path/projeto "explique a arquitetura"
#   pedro-coder --extract "cláusulas de risco" < arquivo.txt
#   pedro-coder --modelo reasoning "analise a tese"
#   pedro-coder --artifact html "dashboard de vendas"
#   pedro-coder --web    # Abre UI web
# ============================================================

set -euo pipefail

API="http://localhost:8765"
MODELO=""
ARQUIVO=""
DIRETORIO=""
EXTRACAO=""
ARTIFACT=""
WEB_MODE=false
TEMPERATURA=0.7
PROMPT=""

# ── Parse de argumentos ─────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --modelo|-m)
            MODELO="$2"
            shift 2
            ;;
        --file|-f)
            ARQUIVO="$2"
            shift 2
            ;;
        --dir|-d)
            DIRETORIO="$2"
            shift 2
            ;;
        --extract|-e)
            EXTRACAO="$2"
            shift 2
            ;;
        --artifact|-a)
            ARTIFACT="$2"
            shift 2
            ;;
        --web|-w)
            WEB_MODE=true
            shift
            ;;
        --temp|-t)
            TEMPERATURA="$2"
            shift 2
            ;;
        --help|-h)
            echo "🐧 Pedro Coder v2.0 — CLI Avançado"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo ""
            echo "Uso: pedro-coder [opções] \"prompt\""
            echo ""
            echo "Opções:"
            echo "  --modelo, -m     Modelo: coder, geral, reasoning, 480b"
            echo "  --file, -f       Analisa arquivo específico"
            echo "  --dir, -d        Usa diretório como contexto"
            echo "  --extract, -e    Extração estruturada de texto"
            echo "  --artifact, -a   Gera artifact: html, dashboard, svg, relatorio"
            echo "  --web, -w        Abre UI web no browser"
            echo "  --temp, -t       Temperatura (0.0-1.0, padrão 0.7)"
            echo "  --help, -h       Esta ajuda"
            echo ""
            echo "Exemplos:"
            echo '  pedro-coder "crie script de backup do Redis"'
            echo '  pedro-coder --file contrato.pdf "extraia cláusulas de risco"'
            echo '  pedro-coder --dir /opt/plenus-juridico "explique a arquitetura"'
            echo '  pedro-coder --extract "datas e valores" < peticao.txt'
            echo '  pedro-coder --artifact html "dashboard de processos"'
            echo "  pedro-coder --web"
            exit 0
            ;;
        *)
            if [[ -z "$PROMPT" ]]; then
                PROMPT="$1"
            else
                PROMPT="$PROMPT $1"
            fi
            shift
            ;;
    esac
done

# ── Verificar se servidor está rodando ──────────────────────
check_server() {
    if ! curl -s "$API/health" > /dev/null 2>&1; then
        echo "❌ Pedro Desktop não está rodando"
        echo "Inicie com: pedro-desktop"
        exit 1
    fi
}

# ── Modo Web ────────────────────────────────────────────────
if [[ "$WEB_MODE" == true ]]; then
    xdg-open "$API/docs" 2>/dev/null || echo "🌐 Abra no browser: http://localhost:8765/docs"
    exit 0
fi

# ── Modo Artifact ───────────────────────────────────────────
if [[ -n "$ARTIFACT" && -z "$PROMPT" ]]; then
    echo "❌ Prompt é obrigatório para artifacts"
    exit 1
fi

if [[ -n "$ARTIFACT" ]]; then
    check_server
    
    echo "🎨 Gerando artifact ($ARTIFACT)..."
    RESP=$(curl -s -X POST "$API/Generate-artifact?prompt=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$PROMPT'))")&artifact_type=$ARTIFACT" 2>/dev/null)
    
    if echo "$RESP" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
        echo "$RESP" | python3 -m json.tool
    else
        echo "❌ Erro: $RESP"
    fi
    exit 0
fi

# ── Modo Extração ───────────────────────────────────────────
if [[ -n "$EXTRACAO" ]]; then
    check_server
    
    # Lê stdin ou arquivo
    if [[ ! -t 0 ]]; then
        TEXTO=$(cat)
    elif [[ -n "$ARQUIVO" ]]; then
        TEXTO=$(cat "$ARQUIVO")
    else
        echo "❌ Extração requer stdin ou --file"
        exit 1
    fi
    
    echo "🔍 Extraindo: $EXTRACAO..."
    
    # JSON payload
    JSON_DATA=$(python3 -c "
import json, sys
data = {'texto': '''$TEXTO''', 'o_que_extrair': '$EXTRACAO', 'formato_saida': 'markdown'}
if '$MODELO':
    data['modelo'] = '$MODELO'
print(json.dumps(data))
")
    
    RESP=$(curl -s -X POST "$API/extract" \
        -H "Content-Type: application/json" \
        -d "$JSON_DATA")
    
    echo "$RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"Modelo: {d.get('modelo', '?')} | Tempo: {d.get('tempo', '?')}s\")
    print()
    extracted = d.get('extracted', '')
    if isinstance(extracted, dict):
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
    else:
        print(extracted)
except:
    print(sys.stdin.read())
"
    exit 0
fi

# ── Modo Análise de Arquivo ─────────────────────────────────
if [[ -n "$ARQUIVO" && -z "$PROMPT" ]]; then
    PROMPT="Analise este arquivo completamente"
fi

if [[ -n "$ARQUIVO" ]]; then
    check_server
    
    if [[ ! -f "$ARQUIVO" ]]; then
        echo "❌ Arquivo não encontrado: $ARQUIVO"
        exit 1
    fi
    
    echo "📄 Analisando: $(basename "$ARQUIVO")..."
    
    # Detectar tipo de análise
    TIPO="geral"
    case "$ARQUIVO" in
        *.py|*.js|*.ts|*.sh|*.go|*.rs) TIPO="codigo" ;;
        *.pdf|*.docx|*.txt|*.md) TIPO="juridico" ;;
    esac
    
    RESP=$(curl -s -X POST "$API/analyze-file" \
        -H "Content-Type: application/json" \
        -d "{\"caminho\": \"$ARQUIVO\", \"tipo_analise\": \"$TIPO\"$( [[ -n "$MODELO" ]] && echo ", \"modelo\": \"$MODELO\"")}")
    
    echo "$RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"Arquivo: {d.get('arquivo', '?')}\")
    print(f\"Tamanho: {d.get('tamanho', '?')} chars\")
    print(f\"Modelo: {d.get('modelo', '?')} | Tempo: {d.get('tempo', '?')}s\")
    print()
    print(d.get('analise', '(Sem análise)'))
except:
    print(sys.stdin.read())
"
    exit 0
fi

# ── Modo Chat Normal ────────────────────────────────────────
if [[ -z "$PROMPT" ]]; then
    # Modo interativo
    echo "🐧 Pedro Coder v2.0 — Modo Interativo"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Digite seu prompt (Ctrl+D para enviar, Ctrl+C para sair)"
    echo ""
    
    PROMPT=$(cat)
fi

if [[ -z "$PROMPT" ]]; then
    echo "❌ Nenhum prompt fornecido"
    echo "Use: pedro-coder --help"
    exit 1
fi

check_server

# Monta request
JSON_DATA=$(python3 -c "
import json
data = {
    'prompt': '''$PROMPT''',
    'temperatura': $TEMPERATURA,
}
if '$MODELO':
    data['modelo'] = '$MODELO'
if '$DIRETORIO':
    data['diretorio_contexto'] = '$DIRETORIO'
print(json.dumps(data))
")

# Mostra info
echo "🧠 Enviando para análise..."
if [[ -n "$MODELO" ]]; then
    echo "📡 Modelo: $MODELO"
fi
if [[ -n "$DIRETORIO" ]]; then
    echo "📂 Contexto: $DIRETORIO"
fi
echo ""

RESP=$(curl -s -X POST "$API/chat" \
    -H "Content-Type: application/json" \
    -d "$JSON_DATA")

# Parse resposta
echo "$RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f\"🤖 Modelo: {d.get('modelo_usado', '?')}\")
    print(f\"📋 Tipo: {d.get('tipo_tarefa', '?')}\")
    print(f\"⏱️  Tempo: {d.get('tempo', '?')}s\")
    print(f\"💬 Tokens: prompt={d.get('tokens_prompt', '?')}, completion={d.get('tokens_completion', '?')}\")
    print(f\"🆔 Session: {d.get('session_id', '?')}\")
    print()
    print('━' * 60)
    print()
    print(d.get('resposta', '(Sem resposta)'))
except json.JSONDecodeError:
    # Se não é JSON, mostra raw
    content = sys.stdin.read()
    if content:
        print(content)
    else:
        print('❌ Erro na resposta do servidor')
        print('Tente: pedro-desktop status')
except Exception as e:
    print(f'❌ Erro: {e}')
"
