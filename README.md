# Generador de Documentos Corporativos — IES Rafael Alberti

Convierte automáticamente archivos Markdown en PDFs con la identidad corporativa del IES Rafael Alberti. Al subir o modificar un `.md` en la carpeta `/docs`, GitHub Actions genera el PDF correspondiente y lo guarda en `/output-pdf`.

## Estructura

```
/
├── .github/workflows/generate-pdf.yml  # Action que se dispara al modificar /docs
├── docs/                               # Aquí van tus documentos .md
├── output-pdf/                         # PDFs generados (se actualizan automáticamente)
├── template/template.html              # Plantilla HTML con estilos y fuentes embebidas
├── scripts/md_to_pdf.py                # Script de conversión
├── Dockerfile                          # Imagen con Playwright + Chromium
└── requirements.txt
```

## Cómo usar

### 1. Crear un documento

Crea un archivo `.md` en `/docs` con este frontmatter al inicio:

```markdown
---
titulo: Título del documento
subtitulo: Subtítulo opcional
fecha: Curso 2025–2026
---

Contenido en Markdown...
```

**Metadatos disponibles:**

| Campo | Obligatorio | Descripción |
|---|---|---|
| `titulo` | ✅ Sí | Aparece en la banda roja. Se escribe en mayúsculas automáticamente. |
| `subtitulo` | No | Línea secundaria bajo el título. |
| `fecha` | No | Aparece en la cabecera junto al logo. |

### 2. Subir al repositorio

```bash
git add docs/mi-documento.md
git commit -m "docs: añadir mi-documento"
git push
```

El Action se dispara automáticamente, genera el PDF y lo commitea en `/output-pdf`.

### 3. Descargar el PDF

Ve a `/output-pdf` en el repositorio y descarga el PDF generado.

## Uso local

```bash
# Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# Convertir un archivo
python scripts/md_to_pdf.py docs/mi-documento.md

# Convertir todos los archivos
python scripts/md_to_pdf.py --all
```

## Elementos Markdown soportados

- Títulos `#` `##` `###`
- Párrafos, **negrita**, *cursiva*
- Listas ordenadas y sin ordenar
- Tablas
- Bloques de código
- Citas `>`
- Líneas horizontales `---`

## Configuración del repositorio

Para que el Action pueda hacer commit de los PDFs generados, hay que dar permisos de escritura al token:

1. Ve a **Settings → Actions → General**
2. En *Workflow permissions* selecciona **Read and write permissions**
3. Guarda los cambios
