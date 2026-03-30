# Extractor Credenciales TheCaseTracking

Script modular en Python para:

1. Autenticarse en `https://<subdomain>.thecasetracking.com/api/sign_in`.
2. Persistir `auth_token`.
3. Consultar credenciales.
4. Exportar `results` en modo incremental por bloques (`.xlsx` o `.csv`) sin cargar todo en RAM.
5. Generar reporte de `causas sin titulo` desde `ct/cases`.

## Preparacion

1. Activar el entorno virtual:
   - PowerShell: `.\env\Scripts\Activate.ps1`
2. Instalar dependencias:
   - `pip install -r requirements.txt`
3. Crear `.env` desde `.env.example` y completar:
   - `CT_SUBDOMAIN`
   - `CT_EMAIL`
   - `CT_PASSWORD`

## Uso

Generar token:

```bash
python main.py token
```

Obtener todas las credenciales y guardar Excel incremental en `output/`:

```bash
python main.py credentials --all --per-page 100 --force-new-token
```

Guardar en ruta especifica:

```bash
python main.py credentials --all --output output/credenciales_full.xlsx
```

Usar modo async para fetch de paginas:

```bash
python main.py credentials --all --per-page 100 --async-fetch --output output/credenciales_full.csv
```

Opcional: guardar JSON completo (incluye `pagination`):

```bash
python main.py credentials --all --output output/credenciales_full.json
```

Reporte de causas sin titulo:

```bash
python main.py untitled-cases --per-page 100 --async-fetch --output output/causas_sin_titulo.xlsx
```

## CLI disponible

| Comando | Descripcion | Ejemplo |
|---|---|---|
| `python main.py token` | Genera y guarda token en `CT_TOKEN_FILE`. | `python main.py token` |
| `python main.py token --force` | Fuerza regeneracion del token. | `python main.py token --force` |
| `python main.py credentials --page N --per-page M` | Descarga una sola pagina. | `python main.py credentials --page 1 --per-page 100` |
| `python main.py credentials --all --per-page M` | Descarga todas las paginas. | `python main.py credentials --all --per-page 100` |
| `python main.py credentials --all --async-fetch` | Descarga todas las paginas con cliente async. | `python main.py credentials --all --async-fetch --output output/credenciales.csv` |
| `python main.py credentials --output archivo.xlsx` | Exporta incremental a Excel (`results`). | `python main.py credentials --all --output output/credenciales.xlsx` |
| `python main.py credentials --output archivo.csv` | Exporta incremental a CSV (`results`). | `python main.py credentials --all --output output/credenciales.csv` |
| `python main.py credentials --output archivo.json` | Exporta JSON completo (`results` + `pagination`). | `python main.py credentials --all --output output/credenciales.json` |
| `python main.py untitled-cases --per-page M` | Exporta causas sin titulo (todas las paginas). | `python main.py untitled-cases --per-page 100` |
| `python main.py untitled-cases --async-fetch` | Exporta causas sin titulo con cliente async. | `python main.py untitled-cases --per-page 100 --async-fetch --output output/causas_sin_titulo.csv` |

Parametros utiles de `credentials`:

- `--sort-by` campo de orden (default `created_at`)
- `--order` ordenamiento `asc` o `desc` (default `desc`)
- `--force-new-token` regenera token antes de consultar

## Variables de entorno

- `CT_SUBDOMAIN` (ejemplo: `beco`)
- `CT_EMAIL`
- `CT_PASSWORD`
- `CT_BASE_DOMAIN` (default: `thecasetracking.com`)
- `CT_TOKEN_FILE` (default: `.ct_token.json`)
- `CT_TIMEOUT_SECONDS` (default: `30`)
