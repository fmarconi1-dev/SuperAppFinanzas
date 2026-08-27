"""Los paneles de la pantalla de Cartera, uno por archivo.

`view.py` quedó como **orquestador**: resuelve datos, arma los KPIs de arriba y
llama a estos paneles en orden. Cada panel se puede leer y tocar sin abrir los
otros — que era el problema: 1.990 líneas en un solo archivo, tocado por el 28%
de los commits del repo.

El split (27/8/2026) **movió código, no lo cambió**: los nombres de las
funciones son los mismos y `view.py` las reimporta, así que `render()` no
cambió una línea.
"""
