"""
searcher.py — Módulo de búsqueda multi-fuente.
Compatible con ddgs (nueva versión de duckduckgo-search).
"""

import os
import time
import logging
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Importar ddgs con fallback a duckduckgo_search
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None
        log.warning("Instala ddgs: pip install ddgs")

# Importar GitHub con fallback
try:
    from github import Github
except ImportError:
    Github = None

# Importar praw con fallback
try:
    import praw
except ImportError:
    praw = None


def _detectar_plataforma(url: str) -> str:
    plataformas = {
        "linkedin.com":      "LinkedIn",
        "stackoverflow.com": "Stack Overflow",
        "github.com":        "GitHub",
        "reddit.com":        "Reddit",
        "medium.com":        "Medium",
        "dev.to":            "Dev.to",
        "quora.com":         "Quora",
        "youtube.com":       "YouTube",
        "twitter.com":       "X (Twitter)",
        "x.com":             "X (Twitter)",
        "facebook.com":      "Facebook",
        "instagram.com":     "Instagram",
    }
    for dominio, nombre in plataformas.items():
        if dominio in url:
            return nombre
    return "Web general"


def search_web(name: str, max_results: int = 10) -> list[dict]:
    """Búsqueda general en DuckDuckGo."""
    if not DDGS:
        log.warning("[WEB] ddgs no instalado — pip install ddgs")
        return []

    log.info(f"[WEB] Buscando: {name!r}")
    results = []
    seen = set()

    queries = [
        f'"{name}"',
        f'"{name}" site:linkedin.com OR site:github.com OR site:medium.com',
    ]

    for query in queries:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    url = r.get("href", "") or r.get("url", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    results.append({
                        "titulo":     r.get("title", "Sin título"),
                        "url":        url,
                        "snippet":    r.get("body", "") or r.get("snippet", ""),
                        "fuente":     "web",
                        "plataforma": _detectar_plataforma(url),
                    })
            time.sleep(0.8)
        except Exception as e:
            log.warning(f"[WEB] Error en query {query!r}: {e}")

    log.info(f"[WEB] {len(results)} resultados")
    return results


def search_linkedin_indexed(name: str) -> list[dict]:
    """Busca perfiles LinkedIn indexados por DuckDuckGo."""
    if not DDGS:
        return []

    log.info(f"[LINKEDIN] Buscando: {name!r}")
    results = []

    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f'site:linkedin.com/in "{name}"', max_results=5):
                url = r.get("href", "") or r.get("url", "")
                if url:
                    results.append({
                        "titulo":     r.get("title", "Perfil LinkedIn"),
                        "url":        url,
                        "snippet":    r.get("body", "") or r.get("snippet", ""),
                        "fuente":     "linkedin_indexado",
                        "plataforma": "LinkedIn",
                    })
        time.sleep(0.6)
    except Exception as e:
        log.warning(f"[LINKEDIN] Error: {e}")

    log.info(f"[LINKEDIN] {len(results)} resultados")
    return results


def search_github(name: str, max_results: int = 8) -> list[dict]:
    """Busca usuarios y repos en GitHub."""
    if not Github:
        log.warning("[GITHUB] PyGithub no instalado")
        return []

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        log.warning("[GITHUB] GITHUB_TOKEN no configurado — omitiendo")
        return []

    log.info(f"[GITHUB] Buscando: {name!r}")
    results = []

    try:
        g = Github(token)
        for user in list(g.search_users(name))[:max_results]:
            results.append({
                "titulo":     f"GitHub: {user.login}",
                "url":        user.html_url,
                "snippet":    f"Nombre: {user.name} · Bio: {user.bio or 'Sin bio'} · Repos públicos: {user.public_repos}",
                "fuente":     "github",
                "plataforma": "GitHub",
            })
            time.sleep(0.3)
    except Exception as e:
        log.warning(f"[GITHUB] Error: {e}")

    log.info(f"[GITHUB] {len(results)} resultados")
    return results


def search_reddit(name: str, max_results: int = 10) -> list[dict]:
    """Busca en Reddit si hay credenciales configuradas."""
    if not praw:
        return []

    client_id     = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent    = os.getenv("REDDIT_USER_AGENT", "agente/1.0")

    if not client_id or not client_secret:
        log.warning("[REDDIT] Credenciales no configuradas — omitiendo")
        return []

    log.info(f"[REDDIT] Buscando: {name!r}")
    results = []

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        for sub in reddit.subreddit("all").search(name, limit=max_results):
            results.append({
                "titulo":     sub.title,
                "url":        f"https://reddit.com{sub.permalink}",
                "snippet":    sub.selftext[:300] if sub.selftext else "",
                "fuente":     "reddit",
                "plataforma": "Reddit",
            })
            time.sleep(0.2)
    except Exception as e:
        log.warning(f"[REDDIT] Error: {e}")

    log.info(f"[REDDIT] {len(results)} resultados")
    return results


def buscar_todo(name: str) -> dict[str, list[dict]]:
    """Ejecuta todas las fuentes y retorna dict agrupado."""
    return {
        "web":      search_web(name),
        "linkedin": search_linkedin_indexed(name),
        "github":   search_github(name),
        "reddit":   search_reddit(name),
    }
