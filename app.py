"""
app.py — Servidor Flask para el agente de búsqueda pública.
Compatible con cualquier versión de searcher.py del proyecto.
"""

import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)


def _importar_busquedas():
    import importlib
    searcher = importlib.import_module("agent.searcher")
    funciones = {}
    for nombre_fn, clave in [
        ("search_web",              "web"),
        ("buscar_web",              "web"),
        ("search_github",           "github"),
        ("buscar_github",           "github"),
        ("search_reddit",           "reddit"),
        ("buscar_reddit",           "reddit"),
        ("search_linkedin_indexed", "linkedin"),
        ("buscar_linkedin",         "linkedin"),
    ]:
        if hasattr(searcher, nombre_fn):
            funciones[clave] = getattr(searcher, nombre_fn)
    if hasattr(searcher, "buscar_todo"):
        funciones["_todo"] = searcher.buscar_todo
    if hasattr(searcher, "search_all"):
        funciones["_todo"] = searcher.search_all
    return funciones


def ejecutar_busqueda(nombre: str, min_score: int) -> dict:
    from agent.processor import procesar
    inicio = time.time()
    funciones = _importar_busquedas()
    resultados_crudos = {"web": [], "reddit": [], "github": [], "linkedin": []}

    if "_todo" in funciones:
        try:
            resultados_crudos = funciones["_todo"](nombre)
        except Exception as e:
            print(f"[ERROR] buscar_todo: {e}")
    else:
        tareas = {k: v for k, v in funciones.items() if not k.startswith("_")}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futuros = {executor.submit(fn, nombre): fuente
                       for fuente, fn in tareas.items()}
            for futuro in as_completed(futuros):
                fuente = futuros[futuro]
                try:
                    resultados_crudos[fuente] = futuro.result()
                except Exception as e:
                    print(f"[ERROR] {fuente}: {e}")
                    resultados_crudos[fuente] = []

    try:
        import inspect
        sig = inspect.signature(procesar)
        if "min_score" in sig.parameters:
            resultados = procesar(resultados_crudos, nombre, min_score=min_score)
        else:
            resultados = procesar(resultados_crudos, nombre)
            resultados = [r for r in resultados if r.get("score", 0) >= min_score]
    except Exception as e:
        print(f"[ERROR] procesar: {e}")
        resultados = []

    duracion = round(time.time() - inicio, 1)
    stats = {
        "total":     len(resultados),
        "alta":      sum(1 for r in resultados if r.get("confianza") == "alta"),
        "media":     sum(1 for r in resultados if r.get("confianza") == "media"),
        "baja":      sum(1 for r in resultados if r.get("confianza") == "baja"),
        "homonimos": sum(1 for r in resultados if r.get("posible_homonimo")),
        "duracion":  duracion,
        "fuentes":   list({r.get("plataforma", "") for r in resultados}),
    }
    return {"resultados": resultados, "stats": stats, "nombre": nombre}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/buscar", methods=["POST"])
def buscar():
    data      = request.get_json()
    nombre    = (data.get("nombre") or "").strip()
    min_score = int(data.get("min_score", 40))
    if not nombre or len(nombre) < 3:
        return jsonify({"error": "Ingresa un nombre válido (mínimo 3 caracteres)"}), 400
    try:
        resultado = ejecutar_busqueda(nombre, min_score)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/exportar", methods=["POST"])
def exportar():
    from agent.reporter import generate_report
    data       = request.get_json()
    nombre     = data.get("nombre", "desconocido")
    resultados = data.get("resultados", [])
    ruta = generate_report(
        name=nombre,
        results=resultados,
        sintesis="Reporte generado desde interfaz web.",
        advertencias="· Verificar fuentes originales antes de tomar decisiones.",
        duracion_seg=0,
        output_dir="./reportes",
    )
    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read()
    nombre_archivo = ruta.replace("\\", "/").split("/")[-1]
    return Response(
        contenido,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


# ── Puerto dinámico para Render y otros servicios cloud ──
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") != "production"
    print(f"\n  Agente de Reputación Pública")
    print(f"  Servidor en: http://0.0.0.0:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)