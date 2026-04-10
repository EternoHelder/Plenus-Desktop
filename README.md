# 🐧 Pedro Desktop v2.0

> Clone do Claude Desktop — Assistente IA jurídico e técnico com interface web rica

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-green.svg)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.56+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Visão Geral

**Pedro Desktop** é um assistente de IA completo inspirado no Claude Desktop, construído para atender necessidades jurídicas e técnicas. Combina uma API FastAPI robusta com uma interface web Streamlit moderna, oferecendo:

- 💬 **Chat inteligente** com roteamento automático de modelos
- 📄 **Análise de arquivos** (código, documentos jurídicos, PDFs)
- 🔍 **Extração estruturada** de informações
- 🎨 **Geração de artifacts** (HTML, dashboards, SVG)
- 🔌 **Conectores MCP** (PostgreSQL, Redis, Firecrawl, DATAJUD, CNJ)

---

## ✨ Funcionalidades

### 🧠 Roteamento Inteligente de Modelos

O sistema detecta automaticamente o tipo de tarefa e seleciona o modelo ideal:

| Modelo | Uso Principal |
|--------|--------------|
| **Qwen3-Coder-Next** | Código, scripts, automação, análise técnica |
| **Qwen3.5 397B** | Texto geral, análise jurídica, redação |
| **Kimi K2.5** | Raciocínio complexo, análise lógica, estratégia |
| **Qwen3-Coder 480B** | Código pesado, projetos grandes |

### 📊 System Prompts Especializados

- **Jurídico**: Escrita técnica com citações de leis e artigos
- **Código**: Código limpo, tipado, com tratamento de erros
- **Extração**: Estruturação em tabelas, JSON, listas

### 🔌 Conectores MCP

- **PostgreSQL**: Consultas ao banco `plenus_rag`
- **Redis**: Memória e cache (DB 10)
- **Firecrawl**: Scraping web inteligente
- **DATAJUD**: Consultas processuais
- **CNJ**: Dados judiciais nacionais

---

## 🚀 Instalação

### Pré-requisitos

- Python 3.10+
- Redis Server
- PostgreSQL (opcional, para MCP)

### 1. Clone o Repositório

```bash
git clone https://github.com/EternoHelder/Plenus-Desktop.git
cd Plenus-Desktop
```

### 2. Crie o Ambiente Virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as Dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as Variáveis de Ambiente

```bash
export OPENAI_API_KEY="sua-api-key"

# Opcionais para MCP
export PG_USER="plenus_app"
export PG_PASSWORD="sua-senha"
export FIRECRAWL_API_KEY="sua-key"
export DATAJUD_API_KEY="sua-key"
export CNJ_API_KEY="sua-key"
```

---

## 📖 Uso

### Iniciar o Servidor API

```bash
# Com o script (recomendado)
./pedro-desktop.sh

# Ou diretamente
python3 orquestrador.py
```

O servidor inicia na porta **8765**.

### Verificar Status

```bash
./pedro-desktop.sh status
curl http://localhost:8765/health
```

### Iniciar a Interface Web

```bash
./pedro-desktop.sh web
# Ou
streamlit run web_ui.py --server.port 8766
```

Acesse: http://localhost:8766

---

## 🖥️ CLI — Pedro Coder

Interface de linha de comando avançada:

```bash
# Chat simples
./pedro-coder.sh "crie script de backup do Redis"

# Analisar arquivo
./pedro-coder.sh --file contrato.pdf "extraia cláusulas de risco"

# Usar diretório como contexto
./pedro-coder.sh --dir /opt/meu-projeto "explique a arquitetura"

# Extração estruturada
./pedro-coder.sh --extract "datas e valores" < peticao.txt

# Gerar artifact
./pedro-coder.sh --artifact html "dashboard de processos"

# Escolher modelo específico
./pedro-coder.sh --modelo reasoning "analise a tese"
```

---

## 📡 API Endpoints

### `GET /`
Informações do servidor e modelos disponíveis.

### `GET /health`
Health check do servidor, Redis e modelos.

### `POST /chat`
Endpoint principal de chat.

```json
{
  "prompt": "Analise este contrato",
  "modelo": "geral",
  "temperatura": 0.7,
  "max_tokens": 4096,
  "arquivos_contexto": ["/path/arquivo.txt"],
  "diretorio_contexto": "/path/projeto"
}
```

### `POST /analyze-file`
Análise completa de arquivo.

```json
{
  "caminho": "/path/arquivo.py",
  "tipo_analise": "codigo",
  "modelo": "coder"
}
```

### `POST /extract`
Extração estruturada de texto.

```json
{
  "texto": "Conteúdo do documento...",
  "o_que_extrair": "cláusulas de risco",
  "formato_saida": "markdown"
}
```

### `POST /generate-artifact`
Geração de artifacts HTML/Dashboard/SVG.

```
POST /generate-artifact?prompt=dashboard+de+vendas&artifact_type=html
```

### `GET /models`
Lista modelos disponíveis.

### `GET /mcp/status`
Status dos conectores MCP.

### Documentação Interativa

- **Swagger UI**: http://localhost:8765/docs
- **ReDoc**: http://localhost:8765/redoc

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     Pedro Desktop v2.0                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Web UI      │    │   CLI        │    │  API REST    │  │
│  │  (Streamlit) │    │ (pedro-coder)│    │  (FastAPI)   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                              │
│                    ┌────────▼────────┐                     │
│                    │   Orquestrador  │                     │
│                    │   (Router IA)   │                     │
│                    └────────┬────────┘                     │
│                             │                              │
│         ┌───────────────────┼───────────────────┐          │
│         │                   │                   │          │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐    │
│  │ MCP Manager │    │   Redis     │    │  ChatPlenus │    │
│  │ (Connectors)│    │  (Cache)    │    │  (LiteLLM)  │    │
│  └──────┬──────┘    └─────────────┘    └─────────────┘    │
│         │                                                  │
│  ┌──────┴──────────────────────────────────────────┐       │
│  │  PostgreSQL │ Firecrawl │ DATAJUD │ CNJ         │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura de Arquivos

```
Plenus-Desktop/
├── orquestrador.py      # 🧠 Cérebro: FastAPI + Router IA
├── web_ui.py            # 🖥️  Interface Streamlit
├── mcp_connectors.py    # 🔌 Conectores MCP
├── pedro-desktop.sh     # 🚀 Script de inicialização
├── pedro-coder.sh       # ⌨️  CLI avançado
├── deploy-vps.sh        # ☁️  Deploy para VPS
├── upload-vps.sh        # 📤 Upload + Deploy
└── requirements.txt     # 📦 Dependências Python
```

---

## ☁️ Deploy em VPS

### Upload e Deploy Automático

```bash
./upload-vps.sh
```

Este script:
1. Envia os arquivos para a VPS
2. Cria ambiente virtual
3. Configura systemd services
4. Configura Nginx como reverse proxy
5. Habilita HTTPS com Let's Encrypt

### Serviços Systemd

```bash
# Status
systemctl status pedro-desktop-api
systemctl status pedro-desktop-webui

# Logs
journalctl -u pedro-desktop-api -f
journalctl -u pedro-desktop-webui -f

# Reiniciar
systemctl restart pedro-desktop-api
```

---

## 🔧 Configuração Avançada

### Variáveis de Ambiente

| Variável | Descrição | Obrigatória |
|----------|-----------|-------------|
| `OPENAI_API_KEY` | API key do ChatPlenus/LiteLLM | ✅ |
| `PG_USER` | Usuário PostgreSQL | ❌ |
| `PG_PASSWORD` | Senha PostgreSQL | ❌ |
| `FIRECRAWL_API_KEY` | API key Firecrawl | ❌ |
| `DATAJUD_API_KEY` | API key DATAJUD | ❌ |
| `CNJ_API_KEY` | API key CNJ | ❌ |

### Portas Utilizadas

| Porta | Serviço |
|-------|---------|
| 8765 | API FastAPI |
| 8766 | Web UI Streamlit |
| 6379 | Redis |
| 5432 | PostgreSQL |

---

## 🧪 Teste Rápido

```bash
# Verificar servidor
curl http://localhost:8765/health

# Chat simples
curl -X POST http://localhost:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Olá, Pedro!"}'

# Listar modelos
curl http://localhost:8765/models
```

---

## 📝 Dependências

```txt
fastapi==0.135.3
uvicorn==0.44.0
python-multipart==0.0.26
redis==7.4.0
requests==2.33.1
chardet==7.4.1
psycopg2-binary==2.9.11
streamlit==1.56.0
```

---

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

## 👨‍💻 Autor

**EternoHelder** — [GitHub](https://github.com/EternoHelder)

---

<p align="center">
  <strong>🐧 Pedro Desktop v2.0</strong><br>
  <em>Seu assistente IA jurídico e técnico — powered by Qwen via ChatPlenus</em>
</p>
