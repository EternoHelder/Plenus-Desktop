#!/usr/bin/env python3
"""
PEDRO DESKTOP v2.0 — Orquestrador FastAPI
Cérebro do sistema: router inteligente, context manager, file reader, artifact generator
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import requests
import json
import os
import time
import uuid
import redis
import hashlib
from datetime import datetime
from pathlib import Path
import chardet

# Import MCP Connectors
try:
    from mcp_connectors import mcp as mcp_manager
    MCP_AVAILABLE = True
except:
    MCP_AVAILABLE = False

# ── Config ──────────────────────────────────────────────────
API_BASE = "https://chatplenus.advocaciaplenus.com/litellm"
API_KEY = os.environ.get("OPENAI_API_KEY", "")
REDIS_DB = 10
BASE_DIR = Path("/home/jostter/.qwen/pietro")
PROJECTS_DIR = Path("/home/jostter/projetos")
SESSIONS_DIR = BASE_DIR / "chats" / "sessions"

# ── Modelos IA ──────────────────────────────────────────────
MODELOS = {
    "coder": {
        "id": "ollama-cloud/qwen3-coder-next",
        "nome": "Qwen3-Coder-Next",
        "uso": "código, scripts, automação, análise técnica",
        "max_tokens": 8192,
    },
    "geral": {
        "id": "ollama-cloud/qwen3.5:397b",
        "nome": "Qwen3.5 397B",
        "uso": "texto geral, análise jurídica, redação",
        "max_tokens": 8192,
    },
    "reasoning": {
        "id": "ollama-cloud/kimi-k2.5",
        "nome": "Kimi K2.5",
        "uso": "raciocínio complexo, análise lógica, estratégia",
        "max_tokens": 8192,
    },
    "480b": {
        "id": "ollama-cloud/qwen3-coder:480b",
        "nome": "Qwen3-Coder 480B",
        "uso": "código pesado, projetos grandes",
        "max_tokens": 8192,
    },
}

DEFAULT_MODEL = "coder"

# ── System Prompts Jurídicos com Few-Shot Examples ─────────
SYSTEM_PROMPTS = {
    "juridico": """Você é Pedro, advogado sênior especialista em direito brasileiro. 
Sua escrita é técnica mas fluida, persuasiva sem ser agressiva.
Sempre cite leis de forma natural (nome + número + artigo).
Use parágrafos curtos e objetivos. Seja direto.

EXEMPLO DE ESTILO (bom):
"O Código de Defesa do Consumidor, em seu artigo 18, impõe ao fornecedor 
responsabilidade objetiva pelos vícios de qualidade que tornem os produtos 
impróprios ao consumo. No caso, o veículo apresentou defeito grave apenas 
3 meses após a aquisição, o que evidencia vício oculto preexistente."

EXEMPLO DE ESTILO (ruim - NÃO usar):
"O autor comprou o carro e estragou. Quer o dinheiro de volta por causa 
do artigo 18 do CDC."

Sempre estruture respostas com tópicos claros quando houver múltiplos pontos.""",

    "codigo": """Você é Pedro, engenheiro de software sênior. 
Seu código é limpo, tipado, documentado o necessário (não excessivo).
Sempre inclua tratamento de erros.
Use type hints em Python.
Prefira composição a herança.
Siga PEP 8 / convenções da linguagem.
Sempre explique decisões arquiteturais brevemente.""",

    "extracao": """Você é Pedro, especialista em análise e estruturação de documentos.
Extraia informações e organize SEMPRE em formato estruturado:
- Tabelas markdown para dados comparáveis
- Listas numeradas para sequências
- Tópicos com hierarquia clara
- JSON quando pedido

Seja completo mas conciso. Não repita informações óbvias.""",

    "padrao": """Você é Pedro - Guardião do PC, Mestre do Linux.
Assistente IA do Jostter, advogado.
Seu estilo é técnico, direto, prático.
Trate o usuário por "Chefe" ou "Jostter".
Responda em português.
Seja completo mas vá direto ao ponto.""",
}

# ── Router de Modelo Inteligente ────────────────────────────
PALAVRAS_CODIGO = ["código", "script", "python", "javascript", "bash", "sql", "api", 
                   "função", "debug", "refator", "git", "docker", "install", "bug",
                   "code", "function", "class", "import", "npm", "pip", "apt"]

PALAVRAS_RACIOCINIO = ["analise", "estratégia", "tese", "defesa", "precedente", 
                        "jurisprudência", "argumento", "contra-argumento", "risco",
                        "parecer", "opinião técnica", "due diligence"]

PALAVRAS_EXTRACAO = ["extraia", "extração", "cláusula", "tabela", "resumo", 
                      "liste", "identifique", "enumere", "mapear", "scrape"]

def detectar_tipo_tarefa(prompt: str) -> tuple[str, str]:
    """Detecta tipo de tarefa e recomenda modelo"""
    texto = prompt.lower()
    
    score_coder = sum(1 for p in PALAVRAS_CODIGO if p in texto)
    score_reasoning = sum(1 for p in PALAVRAS_RACIOCINIO if p in texto)
    score_extracao = sum(1 for p in PALAVRAS_EXTRACAO if p in texto)
    
    if score_coder >= 2:
        return "codigo", "coder"
    elif score_extracao >= 2:
        return "extracao", "geral"
    elif score_reasoning >= 2:
        return "raciocinio", "reasoning"
    else:
        # Detecta por contexto adicional
        if any(ext in prompt for ext in [".py", ".js", ".sh", ".ts", "function", "def "]):
            return "codigo", "coder"
        elif any(w in texto for w in ["contrato", "petição", "processo", "lei", "artigo"]):
            return "juridico", "geral"
        return "padrao", DEFAULT_MODEL

def get_system_prompt(tipo: str) -> str:
    return SYSTEM_PROMPTS.get(tipo, SYSTEM_PROMPTS["padrao"])

def escolher_modelo(prompt: str, modelo_forcado: str = None) -> tuple[str, str, str]:
    """Retorna (modelo_id, tipo_tarefa, modelo_nome)"""
    if modelo_forcado and modelo_forcado in MODELOS:
        m = MODELOS[modelo_forcado]
        tipo, _ = detectar_tipo_tarefa(prompt)
        return m["id"], tipo, m["nome"]
    
    tipo, recomendacao = detectar_tipo_tarefa(prompt)
    m = MODELOS[recomendacao]
    return m["id"], tipo, m["nome"]

# ── FastAPI App ─────────────────────────────────────────────
app = FastAPI(title="Pedro Desktop v2.0", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis ───────────────────────────────────────────────────
def get_redis():
    try:
        return redis.Redis(host="localhost", port=6379, db=REDIS_DB, decode_responses=True)
    except:
        return None

# ── Pydantic Models ────────────────────────────────────────
class ChatRequest(BaseModel):
    prompt: str
    modelo: Optional[str] = None
    system_prompt: Optional[str] = None
    temperatura: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    session_id: Optional[str] = None
    arquivos_contexto: Optional[List[str]] = []  # paths de arquivos para incluir no contexto
    diretorio_contexto: Optional[str] = None  # diretório para ler arquivos relevantes

class ChatResponse(BaseModel):
    resposta: str
    modelo_usado: str
    tipo_tarefa: str
    tempo: float
    tokens_prompt: Any
    tokens_completion: Any
    session_id: str

class FileAnalysisRequest(BaseModel):
    caminho: str
    tipo_analise: str = "geral"  # geral, codigo, juridico, extracao
    modelo: Optional[str] = None

class ExtractionRequest(BaseModel):
    texto: str
    o_que_extrair: str
    formato_saida: str = "markdown"  # markdown, json, tabela
    modelo: Optional[str] = None

class ArtifactRequest(BaseModel):
    prompt: str
    artifact_type: str = "html"
    modelo: Optional[str] = None

# ── API Endpoints ───────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "nome": "Pedro Desktop v2.0",
        "status": "online",
        "modelos_disponiveis": {k: v["nome"] for k, v in MODELOS.items()},
        "modelo_padrao": MODELOS[DEFAULT_MODEL]["nome"],
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/health")
async def health():
    r = get_redis()
    redis_ok = False
    if r:
        try:
            redis_ok = r.ping()
        except:
            pass
    return {
        "api": "ok",
        "redis": "ok" if redis_ok else "offline",
        "modelos": len(MODELOS),
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Endpoint principal de chat com router inteligente"""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key não configurada")
    
    # Detectar tipo e escolher modelo
    modelo_id, tipo_tarefa, modelo_nome = escolher_modelo(req.prompt, req.modelo)
    
    # Construir messages
    system_prompt = req.system_prompt or get_system_prompt(tipo_tarefa)
    
    # Incluir contexto de arquivos se pedido
    contexto_extra = ""
    if req.arquivos_contexto:
        for path in req.arquivos_contexto:
            p = Path(path)
            if p.exists():
                try:
                    conteudo = p.read_text(encoding="utf-8")
                    contexto_extra += f"\n\n--- Arquivo: {p.name} ---\n{conteudo[:5000]}"
                except:
                    pass
    
    if req.diretorio_contexto:
        d = Path(req.diretorio_contexto)
        if d.exists() and d.is_dir():
            # Lê arquivos relevantes (prioriza .md, .txt, .py, .json)
            for ext in ["*.md", "*.txt", "*.py", "*.json", "*.yaml", "*.yml"]:
                for f in d.rglob(ext):
                    if f.is_file() and f.stat().st_size < 50000:  # Max 50KB por arquivo
                        try:
                            ctx = f.read_text(encoding="utf-8")
                            rel = f.relative_to(d)
                            contexto_extra += f"\n\n--- {rel} ---\n{ctx[:3000]}"
                        except:
                            pass
    
    user_content = req.prompt
    if contexto_extra:
        user_content += f"\n\n[CONTEXTO DE ARQUIVOS]{contexto_extra}\n[/CONTEXTO]"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    
    # Chamada à API
    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": modelo_id,
                "messages": messages,
                "temperature": req.temperatura,
                "max_tokens": req.max_tokens,
            },
            timeout=300,
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Erro no modelo: {resp.text[:500]}")
        
        data = resp.json()
        conteudo = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {})
        
        # Salvar sessão
        session_id = req.session_id or str(uuid.uuid4())[:8]
        _salvar_sessao(session_id, req.prompt, conteudo, modelo_nome, tipo_tarefa, elapsed)
        
        return ChatResponse(
            resposta=conteudo,
            modelo_usado=modelo_nome,
            tipo_tarefa=tipo_tarefa,
            tempo=round(elapsed, 1),
            tokens_prompt=tokens.get("prompt_tokens", "?"),
            tokens_completion=tokens.get("completion_tokens", "?"),
            session_id=session_id,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])

@app.post("/analyze-file")
async def analyze_file(req: FileAnalysisRequest):
    """Analisa um arquivo completo com o modelo"""
    p = Path(req.caminho)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Arquivo não encontrado: {req.caminho}")
    
    # Ler arquivo
    try:
        raw = p.read_bytes()
        encoding = chardet.detect(raw).get("encoding", "utf-8")
        conteudo = raw.decode(encoding, errors="replace")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler arquivo: {e}")
    
    # Truncar se muito grande
    max_chars = 80000
    truncated = len(conteudo) > max_chars
    conteudo_crop = conteudo[:max_chars]
    
    # Detectar tipo
    tipo_map = {
        "codigo": "codigo",
        "juridico": "juridico",
        "extracao": "extracao",
    }
    tipo_analise = tipo_map.get(req.tipo_analise, "padrao")
    modelo_id, _, modelo_nome = escolher_modelo(
        f"Analise o arquivo {p.name} ({req.tipo_analise})", 
        req.modelo
    )
    
    system = get_system_prompt(tipo_analise)
    prompt = f"""Analise o seguinte arquivo e forneça uma análise completa e estruturada.

Arquivo: {p.name}
Caminho: {p.absolute()}
Tamanho: {len(conteudo)} caracteres{"(TRUNCADO)" if truncated else ""}

{"[ARQUIVO TRUNCADO - mostrando primeiros 80k chars]" if truncated else ""}

---
{conteudo_crop}
---

Forneça:
1. Resumo do que o arquivo faz/conteúdo
2. Pontos importantes identificados
3. Problemas ou riscos (se houver)
4. Sugestões de melhoria
5. Análise detalhada conforme o tipo ({req.tipo_analise})"""

    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": modelo_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 4096,
            },
            timeout=300,
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Erro no modelo: {resp.text[:500]}")
        
        data = resp.json()
        conteudo_resp = data["choices"][0]["message"]["content"]
        
        return {
            "arquivo": str(p.name),
            "tamanho": len(conteudo),
            "truncado": truncated,
            "tipo_analise": req.tipo_analise,
            "modelo": modelo_nome,
            "tempo": round(elapsed, 1),
            "analise": conteudo_resp,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])

@app.post("/extract")
async def extract(req: ExtractionRequest):
    """Extrai informações de texto com formato estruturado"""
    tipo = "extracao"
    modelo_id, _, modelo_nome = escolher_modelo(f"extração: {req.o_que_extrair}", req.modelo)
    
    formato_instrucoes = {
        "markdown": "Responda em markdown com tabelas e tópicos estruturados.",
        "json": 'Responda APENAS com JSON válido, sem texto adicional. Use formato: {"itens": [...]}',
        "tabela": "Responda APENAS com uma tabela markdown, sem texto adicional.",
    }
    
    prompt = f"""Extraia as seguintes informações do texto abaixo:
O que extrair: {req.o_que_extrair}

Formato de saída: {formato_instrucoes.get(req.formato_saida, formato_instrucoes['markdown'])}

--- TEXTO ---
{req.texto[:50000]}
---"""

    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": modelo_id,
                "messages": [
                    {"role": "system", "content": get_system_prompt("extracao")},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
            timeout=300,
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Erro no modelo: {resp.text[:500]}")
        
        data = resp.json()
        conteudo = data["choices"][0]["message"]["content"]
        
        # Se pediu JSON, tenta parsear
        if req.formato_saida == "json":
            try:
                # Extrai JSON do conteúdo
                inicio = conteudo.find("{")
                fim = conteudo.rfind("}") + 1
                if inicio >= 0 and fim > inicio:
                    conteudo = json.loads(conteudo[inicio:fim])
            except:
                pass  # Retorna como string se não parsear
        
        return {
            "extracted": conteudo,
            "formato": req.formato_saida,
            "modelo": modelo_nome,
            "tempo": round(elapsed, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])

@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Recebe upload de arquivo e salva temporariamente para análise"""
    content = await file.read()
    
    # Hash único para nome
    file_hash = hashlib.md5(content).hexdigest()[:8]
    ext = Path(file.filename).suffix if file.filename else ""
    temp_path = Path(f"/tmp/pedro-upload-{file_hash}{ext}")
    temp_path.write_bytes(content)
    
    return {
        "file_id": file_hash,
        "filename": file.filename,
        "size": len(content),
        "path": str(temp_path),
        "message": f"Arquivo salvo. Use /analyze-file com caminho: {temp_path}",
    }

@app.get("/sessions")
async def list_sessions():
    """Lista sessões salvas"""
    sessions = []
    if SESSIONS_DIR.exists():
        for f in sorted(SESSIONS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(f.read_text())
                meta = data.get("metadata", {})
                sessions.append({
                    "id": meta.get("session_id", f.stem),
                    "titulo": meta.get("titulo", f.stem),
                    "categoria": meta.get("categoria", "geral"),
                    "data": meta.get("data_atualizacao", ""),
                    "mensagens": meta.get("num_mensagens", 0),
                })
            except:
                pass
    return {"sessions": sessions}

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Recupera sessão"""
    # Tenta Redis primeiro
    r = get_redis()
    if r:
        try:
            data = r.get(f"chat:{session_id}")
            if data:
                return json.loads(data)
        except:
            pass
    
    # Tenta arquivo
    session_file = SESSIONS_DIR / f"{session_id}.json"
    if session_file.exists():
        return json.loads(session_file.read_text())
    
    raise HTTPException(status_code=404, detail="Sessão não encontrada")

@app.post("/generate-artifact")
async def generate_artifact(
    req: Optional[ArtifactRequest] = None,
    prompt: Optional[str] = None,
    artifact_type: str = "html",
    modelo: Optional[str] = None,
):
    """Gera artifact (HTML, tabela, dashboard, SVG, etc)"""
    final_prompt = (req.prompt if req else prompt) or ""
    final_prompt = final_prompt.strip()
    final_artifact_type = (req.artifact_type if req else artifact_type) or "html"
    final_modelo = req.modelo if req else modelo

    if not final_prompt:
        raise HTTPException(status_code=400, detail="prompt é obrigatório")

    artifact_prompts = {
        "html": "Gere um arquivo HTML completo e autocontido (CSS + JS inline) que seja visualmente bonito e funcional.",
        "dashboard": "Gere um HTML com dashboard interativo usando Chart.js (via CDN) com dados de exemplo relevantes.",
        "svg": "Gere um SVG completo e detalhado. Responda APENAS com o código SVG.",
        "react": "Gere um componente React completo em um único bloco de código.",
        "tabela": "Gere uma tabela HTML estilizada com os dados.",
        "relatorio": "Gere um relatório markdown completo e bem formatado.",
    }
    
    instrucao = artifact_prompts.get(final_artifact_type, artifact_prompts["html"])
    modelo_id, _, modelo_nome = escolher_modelo(final_prompt, final_modelo)
    
    full_prompt = f"""{instrucao}

Tema/conteúdo: {final_prompt}

IMPORTANTE: Responda APENAS com o código/artefato solicitado, sem texto adicional."""

    start = time.time()
    try:
        resp = requests.post(
            f"{API_BASE}/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": modelo_id,
                "messages": [
                    {"role": "system", "content": "Você é um gerador de artifacts. Produza código limpo, completo e funcional."},
                    {"role": "user", "content": full_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            timeout=300,
        )
        elapsed = time.time() - start
        
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Erro: {resp.text[:500]}")
        
        data = resp.json()
        conteudo = data["choices"][0]["message"]["content"]
        
        # Salva artifact temporário
        artifact_id = str(uuid.uuid4())[:8]
        artifact_dir = Path("/tmp/pedro-artifacts")
        artifact_dir.mkdir(exist_ok=True)
        
        ext_map = {"html": "html", "dashboard": "html", "svg": "svg", "react": "jsx", "tabela": "html", "relatorio": "md"}
        ext = ext_map.get(final_artifact_type, "html")
        artifact_path = artifact_dir / f"{artifact_id}.{ext}"
        artifact_path.write_text(conteudo, encoding="utf-8")
        
        return {
            "artifact_id": artifact_id,
            "type": final_artifact_type,
            "modelo": modelo_nome,
            "tempo": round(elapsed, 1),
            "path": str(artifact_path),
            "preview_url": f"/artifact/{artifact_id}.{ext}" if ext in ["html", "svg", "md"] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:500])

@app.get("/artifact/{filename}")
async def get_artifact(filename: str):
    """Serve artifact para preview"""
    artifact_dir = Path("/tmp/pedro-artifacts")
    path = artifact_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact não encontrado")
    
    ext = path.suffix.lower()
    media_types = {".html": "text/html", ".svg": "image/svg+xml", ".md": "text/markdown"}
    media_type = media_types.get(ext, "text/plain")
    
    return FileResponse(path, media_type=media_type)

@app.get("/models")
async def list_models():
    """Lista modelos disponíveis com status"""
    result = {}
    for key, m in MODELOS.items():
        result[key] = {**m, "default": key == DEFAULT_MODEL}
    return result

@app.post("/models/switch")
async def switch_default_model(modelo: str):
    """Troca modelo padrão"""
    global DEFAULT_MODEL
    if modelo not in MODELOS:
        raise HTTPException(status_code=400, detail=f"Modelo inválido. Opções: {list(MODELOS.keys())}")
    DEFAULT_MODEL = modelo
    return {"mensagem": f"Modelo padrão alterado para {MODELOS[modelo]['nome']}"}

# ── Helpers ─────────────────────────────────────────────────

def _salvar_sessao(session_id: str, user_msg: str, assistant_msg: str, modelo: str, tipo: str, tempo: float):
    """Salva sessão no Redis + arquivo"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    metadata = {
        "session_id": session_id,
        "titulo": user_msg[:80],
        "categoria": tipo,
        "modelo": modelo,
        "tempo": tempo,
        "data_inicio": datetime.now().isoformat(),
        "data_atualizacao": datetime.now().isoformat(),
        "num_mensagens": 2,
        "status": "ativa",
    }
    
    dados = {
        "metadata": metadata,
        "mensagens": [
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": assistant_msg, "modelo": modelo, "tempo": tempo},
        ]
    }
    
    # Salva arquivo
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    session_file = SESSIONS_DIR / f"{session_id}_{timestamp}.json"
    session_file.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Salva Redis
    r = get_redis()
    if r:
        try:
            r.hset(f"chat:{session_id}", mapping={
                "metadata": json.dumps(metadata),
                "mensagens": json.dumps(dados["mensagens"], ensure_ascii=False),
            })
            r.sadd("chats:ativas", session_id)
        except:
            pass

class QueryRequest(BaseModel):
    sql: str
    params: Optional[Dict] = None

@app.get("/mcp/status")
async def mcp_status():
    """Status dos MCP connectors"""
    if not MCP_AVAILABLE:
        return {"status": "MCP connectors não disponíveis"}
    return mcp_manager.status()

@app.post("/mcp/postgres/query")
async def mcp_postgres_query(req: QueryRequest):
    """Executa query SQL no PostgreSQL plenus_rag"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    try:
        results = mcp_manager.postgres.query(req.sql, tuple(req.params.values()) if req.params else None)
        return {
            "rows": results,
            "count": len(results),
            "markdown": mcp_manager.to_markdown_table(results),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/mcp/postgres/tables")
async def mcp_postgres_tables():
    """Lista tabelas do PostgreSQL"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    try:
        tables = mcp_manager.postgres.tables()
        return {"tables": tables, "count": len(tables)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/mcp/postgres/table/{table_name}")
async def mcp_postgres_table_info(table_name: str):
    """Info de uma tabela"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    try:
        info = mcp_manager.postgres.table_info(table_name)
        return info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/mcp/redis/info")
async def mcp_redis_info():
    """Info do Redis"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    return mcp_manager.redis_conn.info()

@app.get("/mcp/redis/keys")
async def mcp_redis_keys(pattern: str = "pedro:*"):
    """Lista chaves Redis"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    keys = mcp_manager.redis_conn.keys(pattern)
    return {"keys": keys, "count": len(keys)}

@app.get("/mcp/redis/get/{key}")
async def mcp_redis_get(key: str):
    """Get valor Redis"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    val = mcp_manager.redis_conn.get(key)
    if val is None:
        raise HTTPException(status_code=404, detail=f"Chave não encontrada: {key}")
    return {"key": key, "value": val}

@app.post("/mcp/firecrawl/search")
async def mcp_firecrawl_search(query: str, limit: int = 5):
    """Busca web via Firecrawl"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    result = mcp_manager.firecrawl.search(query, limit)
    return result

@app.post("/mcp/firecrawl/scrape")
async def mcp_firecrawl_scrape(url: str):
    """Scrape URL via Firecrawl"""
    if not MCP_AVAILABLE:
        raise HTTPException(status_code=503, detail="MCP connectors não disponíveis")
    
    result = mcp_manager.firecrawl.scrape(url)
    return result

# ── Run ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("🚀 Pedro Desktop v2.0 — Orquestrador")
    print(f"📡 Modelos: {', '.join(MODELOS[k]['nome'] for k in MODELOS)}")
    print(f"🔧 Modelo padrão: {MODELOS[DEFAULT_MODEL]['nome']}")
    print(f"🌐 http://localhost:8765")
    print(f"📖 Docs: http://localhost:8765/docs")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
