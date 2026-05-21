import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from agent.searcher import Searcher
from agent.processor import Processor
from agent.llm import LLMAnalyzer
from agent.reporter import Reporter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agente de búsqueda pública — encuentra menciones de una persona en web, Reddit y GitHub."
    )
    parser.add_argument("nombre", help="Nombre completo o usuario a buscar")
    parser.add_argument(
        "--max-resultados",
        type=int,
        default=10,
        metavar="N",
        help="Máximo de resultados por fuente (default: 10)",
    )
    parser.add_argument(
        "--sin-llm",
        action="store_true",
        help="Omitir el análisis con Claude (útil si no hay ANTHROPIC_API_KEY)",
    )
    args = parser.parse_args()

    print(f"\n[*] Iniciando búsqueda pública de: «{args.nombre}»")
    print("-" * 50)

    searcher = Searcher(max_results=args.max_resultados)
    raw = searcher.buscar_todo(args.nombre)

    processor = Processor()
    data = processor.procesar(args.nombre, raw)

    print(f"\n[+] Resultados encontrados: {data.total_resultados}")
    stats = data.stats
    print(f"    Web: {stats['web']}  |  Reddit: {stats['reddit']}  |  GitHub: {stats['github_usuarios'] + stats['github_repositorios']}")

    analisis: str | None = None
    if not args.sin_llm:
        print("\n[*] Analizando con Claude...")
        try:
            llm = LLMAnalyzer()
            analisis = llm.analizar(args.nombre, data)
        except Exception as e:
            print(f"[!] LLM no disponible: {e}")

    reporter = Reporter()
    ruta = reporter.generar(args.nombre, data, analisis)

    print(f"\n[✓] Reporte guardado en: {ruta}\n")


if __name__ == "__main__":
    main()
