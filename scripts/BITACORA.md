# scripts/

<!-- huella: cb4c6eb70b4e -->

Resumen: Operación y mantenimiento: backups remotos (PowerShell + verificación), reset de contraseñas, chequeo de cobertura de Docta y el indexador del mapa.

## Buscar acá si

- backup remoto diario, restaurar, "¿este backup sirve de verdad?" → `backup_remoto.ps1`, `restaurar_backup.ps1`, `verificar_backup.py`, `estado_backup.ps1`, `programar_backup.ps1`
- resetear la contraseña de un usuario → `setup_password.py`
- ¿Docta cubre los bonos de la cartera? → `verificar_docta.py`
- reindexar el mapa del repo → `indexar.py` (ver `/MAPA.md`)

## Trampas

- Los `.ps1` corren en la máquina de Franco (Windows), no en Fly.
- `restaurar_backup` deja `pre-restore-*.db` (gitignored) como red de seguridad.

## Estado

- **Funciona:** backup remoto programado y verificado.

## Proximo paso

—
