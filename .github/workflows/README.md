# .github/workflows/ — CI/CD y batch

Workflows previstos (se implementan como `.yml` en su fase; hoy solo se documentan):

- **`batch-scoring.yml`** — cron EOD (lun-vie tras el cierre US). Corre `jobs/build_snapshot.py`, commitea el snapshot del scoring y (opcional) publica el tablero. Hereda el de Scoring-Inversiones. → Fase 2.
- **`tests.yml`** — corre `pytest` en cada push/PR. **Gate:** si rojea, no se mergea. → Fase 1.
- **`deploy.yml`** — despliegue al hosting elegido (Fly.io) en push a `main`. → Fase 1.

> Los batch corren en la nube de GitHub, no en la PC de Franco ni en el servidor web.
