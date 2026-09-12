# DIAGPROG5 updater automation

Este repositorio despliega automáticamente el Worker `diagprog5-updater`
cuando cambia el código de `cloudflare/worker.js`.

## Secrets necesarios en GitHub Actions

Crear una sola vez en:

Settings -> Secrets and variables -> Actions

- `CLOUDFLARE_API_TOKEN`: token de Cloudflare con permiso para editar Workers.
- `GITHUB_READ_TOKEN`: token Fine-grained de solo lectura para este repositorio.
- `UPDATE_KEY`: clave aleatoria larga usada para proteger la descarga privada.

Después de configurar los tres secrets, cada cambio del Worker en `main`
se despliega automáticamente a Cloudflare.

El endpoint `/version` es público y solo expone metadatos de versión.
El endpoint `/download` requiere la cabecera:

`X-DIAGPROG5-UPDATE-KEY`

El token privado de GitHub nunca se incluye en el bot.
