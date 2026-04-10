"""
PEDRO DESKTOP v2.0 — Web UI Streamlit
Interface rica tipo Claude Desktop: chat, artifacts, upload, MCP connectors
"""

import streamlit as st
import requests
import time
from datetime import datetime
from urllib.parse import quote

# ── Config ──────────────────────────────────────────────────
API_URL = "http://localhost:8765"
UPLOAD_FILE_TYPES = [
    "py", "js", "ts", "sh", "go", "rs", "java", "c", "cpp", "h",
    "md", "txt", "json", "yaml", "yml", "xml", "html", "css",
    "sql", "pdf", "docx", "csv", "log",
]
NON_TEXT_PREVIEW_TYPES = {"pdf", "docx"}
TEXT_FILE_EXTENSIONS = tuple(ext for ext in UPLOAD_FILE_TYPES if ext not in NON_TEXT_PREVIEW_TYPES)
TEXT_PREVIEW_EXTENSIONS = tuple(f".{ext}" for ext in TEXT_FILE_EXTENSIONS)
MAX_PREVIEW_CHARS = 2500
MAX_ANALYSIS_HISTORY = 20
MAX_ANALYSIS_HISTORY_DISPLAY = 10
st.set_page_config(
    page_title="Pedro Desktop v2.0",
    page_icon="🐧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Helpers ─────────────────────────────────────────────────
def api_get(endpoint):
    try:
        return requests.get(f"{API_URL}{endpoint}", timeout=10).json()
    except Exception:
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

def init_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "analysis_history" not in st.session_state:
        st.session_state.analysis_history = []
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "Escuro"
    if "quick_analyze_path" not in st.session_state:
        st.session_state.quick_analyze_path = ""

def status_chip(status: str) -> str:
    palette = {
        "online": "var(--ok)",
        "configured": "var(--ok)",
        "not_configured": "var(--warn)",
        "offline": "var(--danger)",
    }
    color = palette.get(str(status), "var(--text-muted)")
    return f'<span class="status-chip" style="border-color:{color}; color:{color};">{status}</span>'

def health_with_latency():
    t0 = time.perf_counter()
    health = api_get("/health")
    latency_ms = round((time.perf_counter() - t0) * 1000)
    return health, latency_ms

def theme_index(current_theme: str) -> int:
    options = ["Escuro", "Claro"]
    return options.index(current_theme) if current_theme in options else 0

def inject_theme(theme_mode: str):
    if theme_mode == "Claro":
        css_vars = """
        :root {
            --bg: #f5f7fb;
            --card: #ffffff;
            --card-soft: #f0f4fa;
            --text: #1f2937;
            --text-muted: #6b7280;
            --primary: #2563eb;
            --accent: #06b6d4;
            --ok: #16a34a;
            --warn: #d97706;
            --danger: #dc2626;
            --border: #dbe3ef;
            --shadow: 0 8px 24px rgba(17, 24, 39, 0.06);
        }
        """
    else:
        css_vars = """
        :root {
            --bg: #0b1220;
            --card: #111a2b;
            --card-soft: #0f172a;
            --text: #e5edf7;
            --text-muted: #94a3b8;
            --primary: #60a5fa;
            --accent: #22d3ee;
            --ok: #22c55e;
            --warn: #f59e0b;
            --danger: #f87171;
            --border: #243247;
            --shadow: 0 8px 24px rgba(0, 0, 0, 0.32);
        }
        """

    st.markdown(
        f"""
        <style>
            {css_vars}
            .stApp {{
                background: linear-gradient(180deg, var(--bg) 0%, var(--card-soft) 100%);
                color: var(--text);
            }}
            .main-header {{
                font-size: 2.15rem;
                font-weight: 800;
                margin-bottom: 0.2rem;
                background: linear-gradient(90deg, var(--primary), var(--accent));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .sub-header {{
                color: var(--text-muted);
                margin-bottom: 1rem;
            }}
            .ui-card {{
                background: var(--card);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 14px;
                box-shadow: var(--shadow);
                margin-bottom: 12px;
            }}
            .ui-card h4 {{
                margin: 0 0 8px;
                color: var(--text);
            }}
            .model-badge {{
                display: inline-block;
                padding: 2px 10px;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 700;
                border: 1px solid var(--primary);
                color: var(--primary);
                background: transparent;
            }}
            .status-chip {{
                display: inline-block;
                padding: 2px 10px;
                border-radius: 999px;
                border: 1px solid;
                font-size: 0.72rem;
                font-weight: 700;
                margin-right: 6px;
            }}
            .metric-line {{
                font-size: 0.86rem;
                color: var(--text-muted);
                line-height: 1.7;
            }}
            div[data-testid="stChatMessage"] {{
                border: 1px solid var(--border);
                border-radius: 14px;
                background: var(--card);
                box-shadow: var(--shadow);
            }}
            div[data-testid="stFileUploader"] {{
                border-radius: 12px;
            }}
            .stTabs [data-baseweb="tab-list"] {{
                gap: 6px;
            }}
            .stTabs [data-baseweb="tab"] {{
                border-radius: 10px;
                border: 1px solid var(--border);
                padding: 0.3rem 0.8rem;
                background: var(--card);
            }}
            .stTabs [aria-selected="true"] {{
                border-color: var(--primary) !important;
                color: var(--primary) !important;
            }}
            .stButton>button, .stDownloadButton>button {{
                border-radius: 10px;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ── Init ────────────────────────────────────────────────────
init_state()

# ── Sidebar ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🐧 Pedro Desktop")
    st.markdown("**v2.0** — Interface Pro")
    st.session_state.theme_mode = st.radio(
        "🎨 Tema",
        options=["Escuro", "Claro"],
        index=theme_index(st.session_state.theme_mode),
        horizontal=True,
    )
    inject_theme(st.session_state.theme_mode)
    st.divider()

    # Status do servidor
    health, latency_ms = health_with_latency()
    server_online = bool(health and health.get("api") == "ok")
    if server_online:
        st.success("✅ Servidor Online")
        st.caption(f"Latência API: {latency_ms} ms")
    else:
        st.error("❌ Servidor Offline")
        st.info("Inicie: `pedro-desktop`")
        st.stop()

    # Modelos
    modelos_data = api_get("/models") or {}
    modelo_opcoes = {}
    for key, info in modelos_data.items():
        modelo_opcoes[info.get("nome", key)] = key

    modelo_atual = st.selectbox(
        "🧠 Modelo para tarefas nesta sessão",
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
    st.markdown("#### 🔌 Connectores")
    mcp_status = api_get("/mcp/status") or {}
    for connector, status in mcp_status.items():
        icon = "🟢" if status in ["online", "configured"] else "🟡" if status == "not_configured" else "🔴"
        st.caption(f"{icon} {connector.title()}: {status}")

    st.divider()

    # Info
    st.markdown("#### 📊 Sistema")
    redis_info = api_get("/mcp/redis/info") or {}
    if redis_info:
        # Supports both legacy (`memory_used`) and current (`used_memory_human`) API payload keys.
        redis_memory = redis_info.get("used_memory_human") or redis_info.get("memory_used") or "?"
        st.caption(f"🔴 Redis keys: {redis_info.get('total_keys', '?')}")
        st.caption(f"🔴 Redis mem: {redis_memory}")

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
st.markdown('<div class="sub-header">Seu assistente IA jurídico e técnico com foco em produtividade visual e operacional.</div>', unsafe_allow_html=True)

# Tabs
tab_chat, tab_upload, tab_extract, tab_artifacts, tab_providers = st.tabs([
    "💬 Chat",
    "📤 Upload & Análise",
    "🔍 Extração",
    "🎨 Artifacts",
    "🔌 Providers",
])

# ── Tab: Chat ───────────────────────────────────────────────
with tab_chat:
    st.markdown('<div class="ui-card"><h4>Conversa</h4><div class="metric-line">Roteamento automático no backend quando necessário. Você pode forçar o modelo pela sidebar.</div></div>', unsafe_allow_html=True)

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
                    st.error("Não foi possível obter resposta do servidor. Verifique se a API está online na sidebar e se o modelo está configurado.")

    # Limpar chat
    if st.session_state.chat_history and st.button("🗑️ Limpar Chat", type="secondary"):
        st.session_state.chat_history = []
        st.rerun()

# ── Tab: Upload & Análise ──────────────────────────────────
with tab_upload:
    st.header("📤 Upload & Análise")
    st.caption("Faça drag-and-drop, valide os arquivos e rode análises com histórico de execução.")

    col1, col2 = st.columns([1, 1])

    with col1:
        uploaded_files = st.file_uploader(
            "📤 Upload de arquivo(s)",
            type=UPLOAD_FILE_TYPES,
            accept_multiple_files=True,
        )

    with col2:
        file_path = st.text_input(
            "Ou caminho local já existente:",
            value=st.session_state.quick_analyze_path,
            placeholder="/home/jostter/projetos/meu_app/main.py",
        )

    if uploaded_files:
        st.markdown('<div class="ui-card"><h4>Arquivos selecionados</h4></div>', unsafe_allow_html=True)
        for i, f in enumerate(uploaded_files, start=1):
            size_kb = round(f.size / 1024, 1)
            st.caption(f"{i}. **{f.name}** • {size_kb} KB • `{f.type or 'tipo desconhecido'}`")

        preview_file = st.selectbox(
            "Pré-visualizar arquivo (texto):",
            options=[f.name for f in uploaded_files],
        )
        selected_preview = next((f for f in uploaded_files if f.name == preview_file), None)
        is_text_content = bool(selected_preview and selected_preview.type and selected_preview.type.startswith("text"))
        has_text_extension = bool(selected_preview and selected_preview.name.endswith(TEXT_PREVIEW_EXTENSIONS))
        if selected_preview and (is_text_content or has_text_extension):
            # 4x buffer captures enough bytes for multi-byte UTF-8 chars before final char truncation.
            preview_bytes = selected_preview.getvalue()[:MAX_PREVIEW_CHARS * 4]
            content = preview_bytes.decode("utf-8", errors="replace")[:MAX_PREVIEW_CHARS]
            st.code(content or "(arquivo vazio)", language=None)

    tipo_analise = st.selectbox(
        "Tipo de análise:",
        ["automático", "código", "jurídico", "extracao"],
        help="Automático detecta pelo tipo de arquivo"
    )

    if st.button("🔍 Analisar", type="primary", use_container_width=True):
        caminhos_para_analise = []

        if uploaded_files:
            for uploaded_file in uploaded_files:
                save_path = f"/tmp/pedro-upload-{uploaded_file.name}"
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                caminhos_para_analise.append(save_path)
        elif file_path:
            caminhos_para_analise.append(file_path)
        else:
            st.warning("Faça upload ou informe o caminho de um arquivo")
            st.stop()

        progress = st.progress(0, text="Preparando análise...")
        if tipo_analise == "automático":
            tipo = None
        else:
            tipo = tipo_analise

        total = len(caminhos_para_analise)
        try:
            for idx, caminho in enumerate(caminhos_para_analise, start=1):
                with st.spinner(f"🧠 Analisando {caminho} com {modelo_atual}..."):
                    payload = {"caminho": caminho, "modelo": modelo_id}
                    if tipo:
                        payload["tipo_analise"] = tipo
                    resp = api_post("/analyze-file", payload)

                progress.progress(idx / total, text=f"Analisado {idx}/{total}")
                if resp and "analise" in resp:
                    st.success(f"✅ {resp.get('arquivo', caminho)} ({resp.get('tempo', '?')}s)")
                    with st.expander(f"Resultado: {resp.get('arquivo', caminho)}", expanded=(idx == 1)):
                        st.markdown(resp["analise"])
                        cols = st.columns(3)
                        cols[0].metric("Arquivo", resp.get("arquivo", "?"))
                        cols[1].metric("Tamanho", f"{resp.get('tamanho', 0):,} chars")
                        cols[2].metric("Modelo", resp.get("modelo", "?"))

                    st.session_state.analysis_history.insert(0, {
                        "arquivo": resp.get("arquivo", caminho),
                        "caminho": caminho,
                        "modelo": resp.get("modelo", "?"),
                        "tipo": tipo_analise,
                        "tempo": resp.get("tempo", "?"),
                        "timestamp": datetime.now().strftime("%d/%m %H:%M"),
                    })
                    st.session_state.analysis_history = st.session_state.analysis_history[:MAX_ANALYSIS_HISTORY]
                else:
                    st.error(f"Erro na análise de {caminho}: {resp}")
        finally:
            progress.empty()

    st.markdown("---")
    st.subheader("🕘 Histórico de análises")
    if st.session_state.analysis_history:
        for i, item in enumerate(st.session_state.analysis_history[:MAX_ANALYSIS_HISTORY_DISPLAY]):
            c1, c2, c3, c4 = st.columns([2.5, 1.2, 1, 1])
            c1.text(f"📄 {item['arquivo']} — {item['caminho']}")
            c2.caption(f"🧠 {item['modelo']}")
            c3.caption(f"⏱️ {item['tempo']}s")
            if c4.button("Reusar caminho", key=f"reuse_{i}"):
                st.session_state.quick_analyze_path = item["caminho"]
                st.rerun()
    else:
        st.info("Nenhuma análise executada nesta sessão.")

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
                st.error("Falha ao extrair conteúdo. Revise o texto e tente novamente.")

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
                except Exception:
                    st.info(f"Artifact salvo. ID: {artifact_id}")
            else:
                st.error(f"Erro ao gerar artifact: {resp}")

# ── Tab: Providers ─────────────────────────────────────────
with tab_providers:
    st.header("🔌 Providers & Conectores")
    st.caption("Visão operacional dos modelos, fallback e integrações MCP.")

    modelos = api_get("/models") or {}
    mcp_status = api_get("/mcp/status") or {}
    health, latency_ms = health_with_latency()

    c1, c2, c3 = st.columns(3)
    c1.metric("Modelos disponíveis", len(modelos))
    c2.metric("Conectores MCP", len(mcp_status))
    c3.metric("Latência API", f"{latency_ms} ms")

    st.markdown(
        '<div class="ui-card"><h4>Fallback e roteamento</h4>'
        '<div class="metric-line">Quando você não força modelo, o backend escolhe automaticamente pelo tipo de tarefa. '
        'Você pode definir um modelo padrão global abaixo.</div></div>',
        unsafe_allow_html=True,
    )

    st.subheader("🧠 Modelos")
    if modelos:
        for key, info in modelos.items():
            default_label = " (padrão)" if info.get("default") else ""
            st.markdown(
                f"""
                <div class="ui-card">
                    <h4>{info.get("nome", key)}{default_label}</h4>
                    <div class="metric-line"><b>ID:</b> {info.get("id", "-")}</div>
                    <div class="metric-line"><b>Uso:</b> {info.get("uso", "-")}</div>
                    <div class="metric-line"><b>Max tokens:</b> {info.get("max_tokens", "-")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.warning("Não foi possível carregar os modelos.")

    available_keys = list(modelos.keys())
    if available_keys:
        selected_default = st.selectbox("Definir modelo padrão global:", available_keys)
        if st.button("Aplicar modelo padrão", type="primary"):
            result = api_post(f"/models/switch?modelo={quote(selected_default)}")
            if result and "mensagem" in result:
                st.success(result["mensagem"])
            else:
                st.error(f"Falha ao trocar modelo: {result}")

    st.subheader("🧩 Connectores MCP")
    if mcp_status:
        for connector, status in mcp_status.items():
            st.markdown(
                f'<div class="ui-card"><h4>{connector.title()}</h4>{status_chip(status)}</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("Sem dados de conectores.")

    if health:
        st.subheader("📡 Health completo")
        st.json(health)

# ── Footer ──────────────────────────────────────────────────
st.divider()
st.caption("🐧 Pedro Desktop v2.0 | UI refresh com design system, upload evoluído e hub de providers")
