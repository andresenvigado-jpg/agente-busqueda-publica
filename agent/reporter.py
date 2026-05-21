import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from agent.processor import ProcessedData


class Reporter:
    def __init__(self):
        templates_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.reportes_dir = Path(__file__).parent.parent / "reportes"
        self.reportes_dir.mkdir(exist_ok=True)

    def generar(
        self,
        nombre: str,
        data: ProcessedData,
        analisis: str | None = None,
    ) -> str:
        template = self.env.get_template("reporte.md.j2")

        contenido = template.render(
            nombre=nombre,
            fecha=data.fecha_busqueda,
            stats=data.stats,
            web=data.web,
            reddit=data.reddit,
            github=data.github,
            analisis=analisis,
        )

        ruta = self.reportes_dir / self._nombre_archivo(nombre)
        ruta.write_text(contenido, encoding="utf-8")
        return str(ruta)

    @staticmethod
    def _nombre_archivo(nombre: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", nombre.lower())
        slug = re.sub(r"\s+", "-", slug).strip("-")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{slug}_{timestamp}.md"
