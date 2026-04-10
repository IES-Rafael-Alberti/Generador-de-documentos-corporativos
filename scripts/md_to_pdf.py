#!/usr/bin/env python3
"""
Convierte archivos Markdown a PDF usando la plantilla corporativa del IES Rafael Alberti.
Uso: python scripts/md_to_pdf.py [archivo.md] [--all]
"""

import argparse
import os
import re
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright


DOCS_DIR = Path(__file__).parent.parent / "docs"
OUTPUT_DIR = Path(__file__).parent.parent / "output-pdf"
TEMPLATE_PATH = Path(__file__).parent.parent / "template" / "template.html"

MARKDOWN_EXTENSIONS = [
    "tables",
    "fenced_code",
    "footnotes",
    "attr_list",
]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta = {}
    if not text.startswith("---"):
        return meta, text
    end = text.find("\n---", 3)
    if end == -1:
        return meta, text
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4:].strip()


def preprocess_md(text: str) -> str:
    """Protege los guiones bajos en líneas de firma para que Markdown no los convierta en cursiva/negrita."""
    lines = text.splitlines()
    result = []
    for line in lines:
        # Si la línea contiene secuencias de guiones bajos (campos de firma)
        if re.search(r'_{2,}', line):
            # Reemplazar secuencias de __ por una versión protegida con HTML
            line = re.sub(r'_{3,}', lambda m: '<u>' + '&nbsp;' * len(m.group()) + '</u>', line)
        result.append(line)
    return '\n'.join(result)


def postprocess_html(html: str) -> str:
    """Transforma el HTML generado por Markdown para aplicar estilos corporativos."""

    # 1. Caja de ciclo
    html = re.sub(
        r'<p>(<strong>Ciclo:</strong>.*?)</p>',
        r'<div class="caja-info">\1</div>',
        html, flags=re.DOTALL
    )

    # 2. Convertir tablas de datos (col izquierda = label, col derecha = vacía)
    #    en campos estilo "label rojo + línea de relleno", igual que el HTML original
    def table_to_campos(m):
        table_html = m.group(0)
        thead = m.group(1) if m.group(1) else ''
        tbody = m.group(2)
        
        # Detectar si es tabla de datos: thead vacío o con "Campo", y celdas derechas vacías
        is_datos = bool(re.search(r'<th>\s*(Campo|)\s*</th>', thead)) or not thead
        if not is_datos:
            # Verificar si las celdas de la derecha están vacías en su mayoría
            right_cells = re.findall(r'<td>(.*?)</td>\s*</tr>', tbody, re.DOTALL)
            empty_right = sum(1 for c in right_cells if not c.strip())
            if empty_right < len(right_cells) * 0.5:
                return table_html  # tabla normal, no convertir
        
        # Extraer filas
        rows = re.findall(r'<tr>(.*?)</tr>', tbody, re.DOTALL)
        
        # Si las celdas están vacías, añadir espaciador para dar altura visual
        def add_spacer_to_empty_cells(row_html):
            return re.sub(
                r'<td>(\s*)</td>',
                '<td><div style="min-height:50px;"></div></td>',
                row_html
            )
        tbody_with_spacers = re.sub(
            r'<tr>(.*?)</tr>',
            lambda m: '<tr>' + add_spacer_to_empty_cells(m.group(1)) + '</tr>',
            tbody, flags=re.DOTALL
        )
        
        # Reconstruir tabla normal con spacers (solo si NO es tabla de datos)
        if not is_datos:
            return re.sub(r'<tbody>.*?</tbody>', f'<tbody>{tbody_with_spacers}</tbody>', 
                         table_html, flags=re.DOTALL)
        
        campos_html = '<div class="campos-grid">'
        
        for row in rows:
            cells = re.findall(r'<td>(.*?)</td>', row, re.DOTALL)
            if not cells:
                continue
            label = cells[0].strip()
            # Detectar campo doble: "Label1 | Label2" dentro de la misma celda
            pipe_match = re.match(r'^(.*?)\s*\|\s*(.*?)$', label, re.DOTALL)
            if pipe_match:
                label1 = pipe_match.group(1).strip()
                label2 = pipe_match.group(2).strip()
                campos_html += f'''<div class="campo-fila" style="grid-template-columns:1fr 1fr;">
              <div class="campo">
                <label>{label1}</label>
                <div class="linea-campo"></div>
              </div>
              <div class="campo">
                <label>{label2}</label>
                <div class="linea-campo"></div>
              </div>
            </div>'''
            else:
                campos_html += f'''<div class="campo-fila" style="grid-template-columns:1fr;">
              <div class="campo">
                <label>{label}</label>
                <div class="linea-campo"></div>
              </div>
            </div>'''
        
        campos_html += '</div>'
        return campos_html
    
    # Aplicar a todas las tablas que tengan thead vacío o "Campo"
    html = re.sub(
        r'<table>\s*(?:<thead>(.*?)</thead>)?\s*<tbody>(.*?)</tbody>\s*</table>',
        table_to_campos, html, flags=re.DOTALL
    )

    # 3. Listas de declaraciones → checkboxes
    html = re.sub(
        r'<ul>\s*(<li>.*?)</ul>',
        lambda m: '<ul class="declaracion-lista">\n' +
                  re.sub(r'<li>', '<li class="declaracion-item-md">', m.group(1)) + '</ul>',
        html, flags=re.DOTALL
    )

    # 4. h2 numerado → sec-titulo + envolver en seccion
    # Dividir el HTML por los h2
    parts = re.split(r'(<h2>.*?</h2>)', html, flags=re.DOTALL)
    
    result = parts[0]  # contenido antes del primer h2 (caja-info etc.)
    
    for i in range(1, len(parts), 2):
        h2_tag = parts[i]
        content = parts[i+1] if i+1 < len(parts) else ''
        
        # Extraer texto del h2
        h2_text = re.sub(r'<.*?>', '', h2_tag).strip()
        num_match = re.match(r'^(\d+)\.\s+(.*)', h2_text)
        
        if num_match:
            num = num_match.group(1)
            title = num_match.group(2)
            header_html = (
                f'<div class="sec-titulo">'
                f'<div class="sec-num">{num}</div>'
                f'<h3>{title.upper()}</h3>'
                f'</div>'
            )
        else:
            header_html = f'<div class="sec-titulo"><h3>{h2_text.upper()}</h3></div>'
        
        # Separar contenido de esta sección: todo hasta el próximo h2
        # El contenido ya está separado por el split
        # Envolver la firma con clase especial
        is_firma = num_match and num_match.group(1) == str(len(parts)//2)
        if 'Firma' in h2_text or 'firma' in h2_text:
            content_wrapped = f'<div class="firma-bloque-md">{content}</div>'
        else:
            content_wrapped = content
        
        result += f'<div class="seccion">{header_html}{content_wrapped}</div>'
    
    # Final step: inject spacer in empty <td> cells so they have visible height
    result = re.sub(
        r'<td>(\s*)</td>',
        '<td><div style="min-height:26px;display:block;"></div></td>',
        result
    )

    return result


def md_to_html_body(md_text: str) -> str:
    md_text = preprocess_md(md_text)
    raw = markdown.markdown(md_text, extensions=MARKDOWN_EXTENSIONS)
    return postprocess_html(raw)


def build_html(meta: dict, body_html: str, template: str) -> str:
    titulo = meta.get("titulo", "Documento").upper()
    subtitulo = meta.get("subtitulo", "")
    fecha = meta.get("fecha", "")
    subtitulo_html = f"\n    <h2>{subtitulo}</h2>" if subtitulo else ""
    fecha_header = f"<br>{fecha}" if fecha else ""
    html = template
    html = html.replace("{{TITULO}}", titulo)
    html = html.replace("{{SUBTITULO_HTML}}", subtitulo_html)
    html = html.replace("{{FECHA_HEADER}}", fecha_header)
    html = html.replace("{{CONTENIDO}}", body_html)
    return html


def html_to_pdf(html: str, output_path: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 794, "height": 2000})
        page.set_content(html, wait_until="networkidle")
        content_h = page.evaluate(
            "document.querySelector('.pagina').getBoundingClientRect().height"
        )
        a4_px = 297 / 25.4 * 96
        scale = round(min(a4_px / content_h, 1.0), 4)
        page.close()

        page = browser.new_page(viewport={"width": 794, "height": int(content_h) + 1})
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            scale=scale,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()


def convert_file(md_path: Path) -> Path:
    print(f"  Convirtiendo: {md_path.name}")
    text = md_path.read_text(encoding="utf-8")
    meta, content = parse_frontmatter(text)
    body_html = md_to_html_body(content)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = build_html(meta, body_html, template)
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / md_path.with_suffix(".pdf").name
    html_to_pdf(html, output_path)
    print(f"  → PDF generado: {output_path.name}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Convierte MD a PDF corporativo IESRA")
    parser.add_argument("files", nargs="*", help="Archivos .md a convertir")
    parser.add_argument("--all", action="store_true", help="Convierte todos los .md en /docs")
    args = parser.parse_args()

    if args.all:
        md_files = list(DOCS_DIR.glob("*.md"))
        if not md_files:
            print("No se encontraron archivos .md en /docs")
            sys.exit(0)
    elif args.files:
        md_files = [Path(f) for f in args.files]
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\nIES Rafael Alberti — Generador de documentos corporativos")
    print(f"{'─' * 52}")
    for md_file in md_files:
        if not md_file.exists():
            print(f"  ERROR: No existe {md_file}")
            continue
        convert_file(md_file)
    print(f"{'─' * 52}")
    print(f"Completado. {len(md_files)} documento(s) procesado(s).\n")


if __name__ == "__main__":
    main()
