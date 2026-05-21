import os

import anthropic

from agent.processor import ProcessedData


class LLMAnalyzer:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-6"

    def analizar(self, nombre: str, data: ProcessedData) -> str:
        contexto = self._preparar_contexto(data)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=[
                {
                    "type": "text",
                    "text": (
                        "Eres un analista de presencia pública en internet. "
                        "Analiza los resultados de búsqueda sobre una persona y genera un análisis "
                        "conciso de su huella digital. Sé objetivo, profesional y neutral. "
                        "No hagas suposiciones más allá de lo que los datos indican. "
                        "Responde siempre en español."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Analiza la presencia pública de "{nombre}" basándote en estos resultados:\n\n'
                        f"{contexto}\n\n"
                        "Proporciona un análisis estructurado con:\n"
                        "1. **Resumen ejecutivo** (2-3 oraciones)\n"
                        "2. **Presencia por plataforma** (qué se encontró en cada fuente)\n"
                        "3. **Patrones identificados** (temas recurrentes, intereses, áreas de actividad)\n"
                        "4. **Nivel de visibilidad pública** (Alta / Media / Baja — justifica)\n"
                        "5. **Observaciones adicionales**\n\n"
                        "Sé conciso y factual. Si hay pocos resultados, indícalo claramente."
                    ),
                }
            ],
        )

        return response.content[0].text

    def _preparar_contexto(self, data: ProcessedData) -> str:
        partes: list[str] = []

        if data.web:
            partes.append("=== WEB ===")
            for r in data.web[:5]:
                partes.append(f"- {r.title}\n  {r.snippet[:200]}\n  URL: {r.url}")

        if data.reddit:
            partes.append("\n=== REDDIT ===")
            for r in data.reddit[:5]:
                partes.append(
                    f"- [{r.subreddit}] {r.title} (score: {r.score}, autor: {r.author})"
                )
                if r.body:
                    partes.append(f"  {r.body[:150]}")

        if data.github:
            partes.append("\n=== GITHUB ===")
            for r in data.github[:6]:
                extra = ""
                if r.tipo == "usuario":
                    e = r.extras
                    extra = f" | repos: {e.get('repos_publicos', 0)}, seguidores: {e.get('seguidores', 0)}"
                elif r.tipo == "repositorio":
                    e = r.extras
                    extra = f" | ⭐ {e.get('estrellas', 0)}, lenguaje: {e.get('lenguaje', 'N/A')}"
                partes.append(f"- [{r.tipo.upper()}] {r.nombre}{extra}: {r.descripcion[:150]}")

        return "\n".join(partes) if partes else "No se encontraron resultados en ninguna fuente."
