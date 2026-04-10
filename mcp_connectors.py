"""
PEDRO DESKTOP v2.0 — MCP Connectors
Conectores para PostgreSQL, Redis, Firecrawl, DATAJUD, CNJ
"""

import psycopg2
import psycopg2.extras
import redis
import requests
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Config ──────────────────────────────────────────────────
PG_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "dbname": "plenus_rag",
    "user": os.environ.get("PG_USER", "plenus_app"),
    "password": os.environ.get("PG_PASSWORD", ""),
}

REDIS_CONFIG = {"host": "localhost", "port": 6379, "db": 10, "decode_responses": True}

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
DATAJUD_API_KEY = os.environ.get("DATAJUD_API_KEY", "")
CNJ_API_KEY = os.environ.get("CNJ_API_KEY", "")


# ── PostgreSQL Connector ────────────────────────────────────
class PostgresConnector:
    """Conector para PostgreSQL - plenus_rag"""
    
    def __init__(self, config: dict = None):
        self.config = config or PG_CONFIG
        self._conn = None
    
    def connect(self):
        try:
            self._conn = psycopg2.connect(**self.config)
            return True
        except Exception as e:
            return False
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def query(self, sql: str, params: tuple = None) -> List[Dict]:
        """Executa query e retorna resultados como lista de dicts"""
        if not self._conn:
            self.connect()
        
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                
                if cur.description:  # SELECT
                    results = cur.fetchall()
                    return [dict(r) for r in results]
                else:  # INSERT/UPDATE/DELETE
                    self._conn.commit()
                    return [{"rows_affected": cur.rowcount}]
        except Exception as e:
            self._conn.rollback()
            raise
    
    def tables(self) -> List[str]:
        """Lista todas as tabelas do banco"""
        results = self.query("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        return [r["table_name"] for r in results]
    
    def table_info(self, table_name: str) -> Dict:
        """Retorna estrutura da tabela"""
        columns = self.query(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """)
        
        count_result = self.query(f"SELECT COUNT(*) as total FROM {table_name}")
        total = count_result[0]["total"] if count_result else 0
        
        return {"table": table_name, "columns": columns, "total_rows": total}
    
    def to_markdown(self, results: List[Dict]) -> str:
        """Converte resultados para tabela markdown"""
        if not results:
            return "_Nenhum resultado_"
        
        headers = list(results[0].keys())
        lines = []
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        
        for row in results[:50]:  # Max 50 rows
            lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
        
        if len(results) > 50:
            lines.append(f"\n_... e mais {len(results) - 50} linhas_")
        
        return "\n".join(lines)


# ── Redis Connector ─────────────────────────────────────────
class RedisConnector:
    """Conector para Redis DB 10 - memória Pedro"""
    
    def __init__(self, config: dict = None):
        self.config = config or REDIS_CONFIG
        self._r = None
    
    def connect(self):
        try:
            self._r = redis.Redis(**self.config)
            self._r.ping()
            return True
        except:
            return False
    
    def get(self, key: str):
        if not self._r:
            self.connect()
        val = self._r.get(key)
        if val:
            try:
                return json.loads(val)
            except:
                return val.decode() if isinstance(val, bytes) else val
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        if not self._r:
            self.connect()
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        if ttl:
            self._r.setex(key, ttl, value)
        else:
            self._r.set(key, value)
    
    def keys(self, pattern: str = "*") -> List[str]:
        if not self._r:
            self.connect()
        return [k.decode() if isinstance(k, bytes) else k for k in self._r.keys(pattern)]
    
    def delete(self, key: str) -> bool:
        if not self._r:
            self.connect()
        return bool(self._r.delete(key))
    
    def info(self) -> Dict:
        if not self._r:
            self.connect()
        info = self._r.info()
        return {
            "redis_version": info.get("redis_version", "?"),
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "?"),
            "total_keys": len(self.keys()),
        }


# ── Firecrawl Connector ─────────────────────────────────────
class FirecrawlConnector:
    """Conector para Firecrawl API - scraping web"""
    
    BASE_URL = "https://api.firecrawl.dev/v1"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or FIRECRAWL_API_KEY
    
    def search(self, query: str, limit: int = 5) -> Dict:
        """Busca na web e retorna resultados"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        resp = requests.post(
            f"{self.BASE_URL}/search",
            headers=headers,
            json={"query": query, "limit": limit, "lang": "pt"},
            timeout=60,
        )
        
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    
    def scrape(self, url: str, format: str = "markdown") -> Dict:
        """Scrape uma URL e retorna em formato"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        resp = requests.post(
            f"{self.BASE_URL}/scrape",
            headers=headers,
            json={"url": url, "formats": [format]},
            timeout=60,
        )
        
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
    
    def crawl(self, url: str, limit: int = 10) -> Dict:
        """Crawl completo de um site"""
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        
        resp = requests.post(
            f"{self.BASE_URL}/crawl",
            headers=headers,
            json={"url": url, "limit": limit, "scrapeOptions": {"formats": ["markdown"]}},
            timeout=120,
        )
        
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}


# ── DATAJUD Connector ───────────────────────────────────────
class DataJudConnector:
    """Conector para API DATAJUD - consultas processuais"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or DATAJUD_API_KEY
    
    def consultar_processo(self, numero: str) -> Dict:
        """Consulta processo por número"""
        # Placeholder - endpoint real depende da API
        return {"status": "API não configurada", "api_key_set": bool(self.api_key)}
    
    def consultar_parte(self, nome: str) -> Dict:
        """Consulta processos por parte"""
        return {"status": "API não configurada", "api_key_set": bool(self.api_key)}


# ── CNJ Connector ───────────────────────────────────────────
class CnjConnector:
    """Conector para API CNJ - dados judiciais nacionais"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or CNJ_API_KEY
    
    def dados_tribunal(self, tribunal: str) -> Dict:
        """Retorna dados estatísticos de tribunal"""
        return {"status": "API não configurada", "api_key_set": bool(self.api_key)}


# ── Manager ─────────────────────────────────────────────────
class MCPManager:
    """Gerencia todos os connectors"""
    
    def __init__(self):
        self.postgres = PostgresConnector()
        self.redis_conn = RedisConnector()
        self.firecrawl = FirecrawlConnector()
        self.datajud = DataJudConnector()
        self.cnj = CnjConnector()
    
    def status(self) -> Dict:
        """Status de todos os connectors"""
        return {
            "postgresql": "online" if self.postgres.connect() else "offline",
            "redis": "online" if self.redis_conn.connect() else "offline",
            "firecrawl": "configured" if self.firecrawl.api_key else "not_configured",
            "datajud": "configured" if self.datajud.api_key else "not_configured",
            "cnj": "configured" if self.cnj.api_key else "not_configured",
        }
    
    def to_markdown_table(self, results: List[Dict]) -> str:
        """Helper: resultados → markdown"""
        return self.postgres.to_markdown(results)


# Singleton
mcp = MCPManager()
