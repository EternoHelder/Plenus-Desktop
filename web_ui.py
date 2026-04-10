"""
PEDRO DESKTOP v2.0 — Web UI Streamlit
Interface rica tipo Claude Desktop: chat, artifacts, upload, MCP connectors
"""

import streamlit as st
import requests
import json
import os
import time
from datetime import datetime

# ── Config ──────────────────────────────────────────────────
API_URL = "http://localhost:8765"
st.set_page_config(
    page_title="Pedro Desktop v2.0",
    page_icon="🐧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #1a73e8, #34a853);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .model-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #e8f0fe;
        color: #1a73e8;
    }
    .chat-msg {
        padding: 12px 16px;
        border-radius: 12px;
        margin: 8px 0;
        line-height: 1.6;
    }
    .user-msg {
        background: #e8f0fe;
        border-left: 4px solid #1a73e8;
    }
    .assistant-msg {
        background: #f1f3f4;
        border-left: 4px solid #34a853;
    }
    .info-bar {
        display: flex;
        gap: 16px;
        font-size: 0.8rem;
        color: #5f6368;
        margin-top: 4px;
    }
    div[data-testid="stChatMessage"] {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ── Helpers ─────────────────────────────────────────────────
def api_get(endpoint):
    try:
        return requests.get(f"{API_URL}{endpoint}", timeout=10).json()
    except:
        return None

def api_post(endpoint, data=None, files=None):
    try:
        if files:
            return requests.post(f"{API_URL}{endpoint}", files=files, timeout=60).json()
        return requests.post(f"{API_URL}{endpoint}", json=data or {}, timeout=300).json()
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return None

def check_server():
    """Verifica se servidor está online"""
    health = api_get("/health")
    return health and health.get("api") == "ok"

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🐧 Pedro Desktop")
    st.markdown("**v2.0** — Clone do Claude Sonnet")
    st.divider()
    
    # Status do servidor
    server_online = check_server()
    if server_online:
        st.success("✅ Servidor Online")
    else:
        st.error("❌ Servidor Offline")
        st.info("Inicie: `pedro-desktop`")
        st.stop()
    
    # Modelo
    modelos_data = api_get("/models") or {}
    modelo_opcoes = {}
    for key, info in modelos_data.items():
        modelo_opcoes[info.get("nome", key)] = key
    
    modelo_atual = st.selectbox(
        "🧠 Modelo IA",
        options=list(modelo_opcoes.keys()),
        index=0,
    )
    modelo_id = modelo_opcoes.get(modelo_atual, "coder")
    
    # Temperatura
    temperatura = st.slider("🌡️ Temperatura", 0.0, 1.5, 0.7, 0.1)
    
    # Max tokens
    max_tokens = st.slider("📏 Max Tokens", 512, 8192, 4096, 512)
    
    st.divider()
    
    # MCP Status
    st.markdown("#### 🔌 MCP Connectors")
    mcp_status = api_get("/mcp/status") or {}
    for connector, status in mcp_status.items():
        icon = "✅" if status in ["online", "configured"] else "⏸️" if status == "not_configured" else "❌"
        st.caption(f"{icon} {connector.title()}: {status}")
    
    st.divider()
    
    # Info
    st.markdown("#### 📊 Sistema")
    redis_info = api_get("/mcp/redis/info") or {}
    if redis_info:
        st.caption(f"🔴 Redis keys: {redis_info.get('total_keys', '?')}")
        st.caption(f"🔴 Redis mem: {redis_info.get('memory_used', '?')}")
    
    # Sessões
    st.markdown("#### 💬 Sessões")
    sessions = api_get("/sessions") or {"sessions": []}
    if sessions.get("sessions"):
        for s in sessions["sessions"][:5]:
            st.caption(f"💬 {s.get('titulo', '?')[:40]}...")
    else:
        st.caption("Nenhuma sessão salva")
    
    st.divider()
    st.caption(f"⏱️ {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# ── Main Content ────────────────────────────────────────────

# Header
st.markdown('<div class="main-header">🐧 Pedro Desktop v2.0</div>')
st.caption("Seu assistente IA jurídico e técnico — powered by Qwen via ChatPlenus")

# Tabs
tab_chat, tab_analyze, tab_extract, tab_artifacts = st.tabs([
    "💬 Chat",
    "📄 Analisar Arquivo",
    "🔍 Extração",
    "🎨 Artifacts",
])

# ── Tab: Chat ───────────────────────────────────────────────
with tab_chat:
    # Inicializar histórico
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Mostrar histórico
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("metadata"):
                meta = msg["metadata"]
                cols = st.columns(4)
                cols[0].markdown(f'<span class="model-badge">{meta.get("modelo", "")}</span>', unsafe_allow_html=True)
                cols[1].caption(f"Tipo: {meta.get('tipo', '?')}")
                cols[2].caption(f"Tempo: {meta.get('tempo', '?')}s")
                cols[3].caption(f"Session: {meta.get('session', '?')}")
    
    # Input
    if prompt := st.chat_input("Digite sua pergunta..."):
        # Adiciona mensagem do usuário
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Chama API
        with st.chat_message("assistant"):
            with st.spinner(f"🧠 Pensando com {modelo_atual}..."):
                resp = api_post("/chat", {
                    "prompt": prompt,
                    "modelo": modelo_id,
                    "temperatura": temperatura,
                    "max_tokens": max_tokens,
                })
                
                if resp and "resposta" in resp:
                    st.markdown(resp["resposta"])
                    
                    # Metadata
                    cols = st.columns(4)
                    cols[0].markdown(f'<span class="model-badge">{resp.get("modelo_usado", "")}</span>', unsafe_allow_html=True)
                    cols[1].caption(f"Tipo: {resp.get('tipo_tarefa', '?')}")
                    cols[2].caption(f"Tempo: {resp.get('tempo', '?')}s")
                    cols[3].caption(f"Session: {resp.get('session_id', '?')}")
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": resp["resposta"],
                        "metadata": {
                            "modelo": resp.get("modelo_usado", ""),
                            "tipo": resp.get("tipo_tarefa", ""),
                            "tempo": resp.get("tempo", ""),
                            "session": resp.get("session_id", ""),
                        }
                    })
                else:
                    st.error("Erro na resposta do servidor")
    
    # Limpar chat
    if st.session_state.chat_history and st.button("🗑️ Limpar Chat", type="secondary"):
        st.session_state.chat_history = []
        st.rerun()

# ── Tab: Analisar Arquivo ──────────────────────────────────
with tab_analyze:
    st.header("📄 Analisar Arquivo")
    st.caption("Upload um arquivo ou informe o caminho para análise completa")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader("📤 Upload de arquivo", type=[
            "py", "js", "ts", "sh", "go", "rs", "java", "c", "cpp", "h",
            "md", "txt", "json", "yaml", "yml", "xml", "html", "css",
            "sql", "pdf", "docx", "csv", "log",
        ])
    
    with col2:
        file_path = st.text_input("Ou caminho do arquivo:", placeholder="/home/jostter/projetos/meu_app/main.py")
    
    tipo_analise = st.selectbox(
        "Tipo de análise:",
        ["automático", "código", "jurídico", "extracao"],
        help="Automático detecta pelo tipo de arquivo"
    )
    
    if st.button("🔍 Analisar", type="primary", use_container_width=True):
        # Decide fonte do arquivo
        if uploaded_file:
            # Upload temporário
            save_path = f"/tmp/pedro-upload-{uploaded_file.name}"
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            caminho = save_path
        elif file_path:
            caminho = file_path
        else:
            st.warning("Faça upload ou informe o caminho de um arquivo")
            st.stop()
        
        if tipo_analise == "automático":
            tipo = None  # API detecta automaticamente
        else:
            tipo = tipo_analise
        
        with st.spinner(f"🧠 Analisando {caminho} com {modelo_atual}..."):
            payload = {"caminho": caminho}
            if tipo:
                payload["tipo_analise"] = tipo
            payload["modelo"] = modelo_id
            
            resp = api_post("/analyze-file", payload)
            
            if resp and "analise" in resp:
                st.success(f"✅ Análise completa ({resp.get('tempo', '?')}s)")
                st.markdown("---")
                st.markdown(resp["analise"])
                
                # Stats
                cols = st.columns(3)
                cols[0].metric("Arquivo", resp.get("arquivo", "?"))
                cols[1].metric("Tamanho", f"{resp.get('tamanho', 0):,} chars")
                cols[2].metric("Modelo", resp.get("modelo", "?"))
            else:
                st.error(f"Erro na análise: {resp}")

# ── Tab: Extração ───────────────────────────────────────────
with tab_extract:
    st.header("🔍 Extração Estruturada")
    st.caption("Extraia informações de textos e transforme em tabelas, JSON ou relatórios")
    
    texto = st.text_area(
        "📝 Texto de entrada:",
        height=200,
        placeholder="Cole aqui o texto do contrato, petição, processo...",
    )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        o_que = st.text_input(
            "O que extrair?",
            placeholder="cláusulas de risco, datas, valores, partes envolvidas...",
        )
    
    with col2:
        formato = st.selectbox("Formato:", ["markdown", "json", "tabela"])
    
    if st.button("🔍 Extrair", type="primary", use_container_width=True):
        if not texto or not o_que:
            st.warning("Preencha o texto e o que deseja extrair")
            st.stop()
        
        with st.spinner(f"🧠 Extraindo com {modelo_atual}..."):
            resp = api_post("/extract", {
                "texto": texto,
                "o_que_extrair": o_que,
                "formato_saida": formato,
                "modelo": modelo_id,
            })
            
            if resp:
                st.success(f"✅ Extração completa ({resp.get('tempo', '?')}s)")
                
                extracted = resp.get("extracted", "")
                if isinstance(extracted, dict):
                    st.json(extracted)
                else:
                    st.markdown(extracted)
            else:
                st.error("Erro na extração")

# ── Tab: Artifacts ─────────────────────────────────────────
with tab_artifacts:
    st.header("🎨 Gerador de Artifacts")
    st.caption("Gere HTML, dashboards, tabelas e relatórios completos")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        artifact_prompt = st.text_area(
            "Descreva o artifact:",
            height=100,
            placeholder="Dashboard de processos judiciais com gráfico de pizza por status e tabela de valores...",
        )
    
    with col2:
        artifact_type = st.selectbox(
            "Tipo:",
            ["html", "dashboard", "tabela", "relatorio", "svg"],
        )
    
    if st.button("🎨 Gerar", type="primary", use_container_width=True):
        if not artifact_prompt:
            st.warning("Descreva o artifact desejado")
            st.stop()
        
        with st.spinner(f"🧠 Gerando {artifact_type} com {modelo_atual}..."):
            from urllib.parse import quote
            resp = api_post(f"/generate-artifact?prompt={quote(artifact_prompt)}&artifact_type={artifact_type}")
            
            if resp and "artifact_id" in resp:
                st.success(f"✅ Artifact gerado ({resp.get('tempo', '?')}s)")
                
                artifact_id = resp["artifact_id"]
                ext = "html" if artifact_type in ["html", "dashboard", "tabela"] else artifact_type
                
                # Preview
                preview_url = f"{API_URL}/artifact/{artifact_id}.{ext}"
                st.markdown(f"**Preview:** [{artifact_id}.{ext}]({preview_url})")
                
                try:
                    artifact_content = requests.get(preview_url, timeout=10).text
                    
                    if ext == "html":
                        st.components.v1.html(artifact_content, height=600, scrolling=True)
                    else:
                        st.code(artifact_content, language="html" if ext == "html" else None)
                except:
                    st.info(f"Artifact salvo. ID: {artifact_id}")
            else:
                st.error(f"Erro ao gerar artifact: {resp}")

# ── Footer ──────────────────────────────────────────────────
st.divider()
st.caption("🐧 Pedro Desktop v2.0 | Powered by Qwen via ChatPlenus LiteLLM | Zorin OS 17.3")
