# Extractor Credenciales TheCaseTracking

Script modular en Python para:

1. Autenticarse en `https://<subdomain>.thecasetracking.com/api/sign_in`.
2. Persistir `auth_token`.
3. Consultar credenciales.
4. Exportar `results` a Excel (`.xlsx`) por defecto.

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

Obtener todas las credenciales y guardar Excel en `output/`:

```bash
python main.py credentials --all --per-page 100 --force-new-token
```

Guardar en ruta especifica:

```bash
python main.py credentials --all --output output/credenciales_full.xlsx
```

Opcional: guardar JSON completo (incluye `pagination`):

```bash
python main.py credentials --all --output output/credenciales_full.json
```

## Variables de entorno

- `CT_SUBDOMAIN` (ejemplo: `beco`)
- `CT_EMAIL`
- `CT_PASSWORD`
- `CT_BASE_DOMAIN` (default: `thecasetracking.com`)
- `CT_TOKEN_FILE` (default: `.ct_token.json`)
- `CT_TIMEOUT_SECONDS` (default: `30`)

