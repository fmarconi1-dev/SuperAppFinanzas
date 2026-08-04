# .github/workflows/ — CI/CD y batch

Workflows previstos (se implementan como `.yml` en su fase; hoy solo se documentan):

- **`batch-scoring.yml`** — cron EOD (lun-vie tras el cierre US). Corre `jobs/build_snapshot.py`, commitea el snapshot del scoring y (opcional) publica el tablero. Hereda el de Scoring-Inversiones. → Fase 2.
- **`tests.yml`** ✅ **IMPLEMENTADO (Fase 4, 4/8/2026)** — corre `pytest` en Python 3.11 (la del `Dockerfile`) en cada push y PR, en una máquina limpia. Segundo job **`sin-datos`**: revisa el árbol completo buscando `.xlsx`/`.db`/`.csv`/`.env` y claves privadas. El pre-commit hook ya lo bloquea, pero vive en la PC de Franco y se puede saltear con `--no-verify`: esta es la red que no se puede puentear.
- **`deploy.yml`** — despliegue al hosting elegido (Fly.io) en push a `main`. → Fase 1.

> Los batch corren en la nube de GitHub, no en la PC de Franco ni en el servidor web.
