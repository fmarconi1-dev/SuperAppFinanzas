# scripts/

<!-- huella: 8aae5206463b -->

Resumen: Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas, chequeo de cobertura de Docta y el indexador del mapa.

## Buscar acá si

- backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1`
- resetear la contraseña de un usuario → `setup_password.py`
- ¿Docta cubre los bonos de la cartera? → `verificar_docta.py`
- reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`)

## Trampas

- Los `.ps1` corren en la máquina de Franco (Windows), no en Fly.
- `restaurar_backup` deja `pre-restore-*.db` (gitignored) como red de seguridad.
- ⚠️ **`indexar.py` en Windows (22/9/2026):** las rutas llegan con `\` y los patrones del `.gitignore` usan `/`. Sin normalizar, `ignorado()` no reconocía ninguna carpeta ignorada: el `MAPA.md` commiteado listaba `Borrar/` y el indexador **leía los `.db-shm` de los backups de producción** buscando URLs. Normalizado, y `*.db-shm`/`*.db-wal`/`*.db-journal` ignorados por nombre. Test: `tests/test_indexar.py`.
- `git()` de `indexar.py` devuelve `""` si git no responde: cada llamador tiene que tolerarlo **con el tipo correcto** (el `{}` en vez de `Counter()` del 27/8 rompía el hook pre-commit).

## Estado

- **Funciona:** backup remoto programado y verificado.

## Proximo paso

—
