# scripts/perf/

<!-- huella: 891ce3bfba21 -->

Resumen: Herramientas de la auditoría de rendimiento (21–26/10/2026): base sintética, medición de backend (AppTest), del navegador (Chrome por CDP), del arranque en frío, y pruebas en el runtime real. Corren en la PC de Franco, contra la app local: no tocan producción ni la base real. Resultados en `docs/perf/`.

## Buscar acá si

- "¿la app está más lenta que antes?" o hay que repetir la medición → `REPORTE-IMPACTO.md` (cómo se midió) y estos scripts, con el código viejo y el nuevo **intercalados**
- una base de prueba del tamaño de la real sin datos de Franco → `generar_base.py` (seed 42, 4 años, ~5.300 movimientos)
- cuánto cuesta cada click, cuántas consultas hace, qué consulta pesa → `medir_backend.py` (AppTest; click sin cambios, click después de una escritura, primer render, SQL reproducido, planes)
- dónde se va el tiempo de un render de Finanzas → `perfil_finanzas.py` (cProfile; solo proporciones: infla ~2,5×)
- FCP, LCP, CLS, TBT, bytes, requests, frames del websocket → `medir_frontend.py` (Chrome headless, caché fría, `desktop` y `movil_lighthouse`)
- cuánto tarda en despertarse la app o el bot después de que Fly apaga la máquina → `medir_arranque.py` (cada escenario en un proceso nuevo, A/B intercalado)
- ¿anda de verdad en Streamlit (no en AppTest)? → `probar_runtime.py` (pestañas, fragmentos, Excel diferido), `probar_cache_runtime.py` (un gasto de otro proceso aparece al recargar)
- qué fuente se baja y con cuál se dibuja cada texto → `probar_fuentes.py`; qué mueve el layout → `probar_cls.py`

## Trampas

- **Medir antes y después en el mismo momento, intercalados.** Entre días la carga de la PC varió hasta 3× y Chrome se actualizó solo: comparar contra números de otro día mezcla eso con las mejoras. El "antes" se arma con `git archive <commit>` en una carpeta aparte, y los scripts reciben la carpeta del código como argumento.
- **El token de sesión de prueba vence** (`issue_token(1, ttl=...)` con el `SESSION_SECRET` de la app local). Vencido, se mide la pantalla de login sin darse cuenta: pasó el 26/10. Desde entonces `medir_frontend.py` falla si la pantalla no es la pedida.
- **Un escenario tiene que verificar su resultado**: `medir_arranque.py` mandaba `café 3500`, que el bot rechaza. Ahora manda `3500, Compras` y exige el "Cargado".
- **En Windows, cerrar la página antes de matar Chrome** (los scripts navegan a `about:blank`): si no, el `accept` de asyncio tira `WinError 64` y el servidor local deja de atender.
- **No correr `chrome.exe --version`**: en Windows abre una ventana en el Chrome de Franco. La versión sale de las propiedades del archivo.
- Frontend y backend **no en paralelo**: se ensucian entre sí.
- La app local va con `--server.address 127.0.0.1` (sin eso, Streamlit escucha en toda la red).
- Local, Streamlit **no comprime**: los KB son sin comprimir; producción sirve Brotli.
- `probar_runtime.py` lo importan otros scripts: su prueba corre solo con `__main__`.

## Estado

- **26/10/2026:** usadas en la Fase 1 (línea base), en los cinco frentes y en la medición final (`docs/perf/REPORTE-IMPACTO.md`).

## Proximo paso

Repetir `medir_arranque.py` y un click real en Fly después de desplegar (ver `/ESTADO.md`).
