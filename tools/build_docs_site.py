"""Construye docs/index.html a partir de Custom Maschine - All Operations.html,
dejándolo 100% enfocado en Ableton Push para GitHub Pages.
"""

import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'Custom Maschine - All Operations.html')
DEST = os.path.join(ROOT, 'docs', 'index.html')

with open(SRC, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Títulos y branding
html = html.replace('Maschine MK3 · Ableton + VirtualDJ', 'Maschine MK3 as Ableton Push')
html = html.replace('Maschine MK3: Ableton + VirtualDJ', 'Maschine MK3 as Ableton Push')
html = html.replace('<h1>Maschine MK3: Ableton + VirtualDJ</h1>', '<h1>Maschine MK3 as Ableton Push — All Operations</h1>')
html = html.replace(
    'Guía de uso del Maschine MK3 con Ableton Live 12 y VirtualDJ (script CustomMaschineMK3 modificado).',
    'Guía interactiva completa de todas las operaciones para Maschine MK3 como Ableton Push en Live 12.'
)

# 2. Eliminar el bloque mm-box completo (sección de VirtualDJ)
html = re.sub(r'<div class="mm-box">.*?</div>\s*(?=<p>Todas las funciones|<h2)', '', html, flags=re.DOTALL)

# 3. Limpiar el Table of Contents de la derecha
html = re.sub(
    r'<li><a href="#mi-maschine"[^>]*><b>Mi Maschine: Ableton \+ VirtualDJ</b></a><ul>.*?</ul></li>',
    '',
    html,
    flags=re.DOTALL
)
html = re.sub(r'<li><a href="#ableton"[^>]*><b>Ableton: todas las funciones</b></a></li>', '', html)

# 4. Limpiar notas residuales en tablas
html = re.sub(r'<span class="mm-note">Si los pads están fijados a VirtualDJ.*?</span>', '', html)
html = re.sub(r'<span class="mm-note">En mi setup, SAMPLING pasa el Maschine a VirtualDJ.*?</span>', '', html)
html = re.sub(r'<span class="mm-note">Ya no: SAMPLING ahora pasa el Maschine a VirtualDJ.*?</span>', '', html)
html = re.sub(r'<span class="mm-note">Sigue funcionando en modo VirtualDJ.*?</span>', '', html)
html = re.sub(r'<span class="mm-note">Ya no: FOLLOW ahora activa/desactiva Ableton Link.*?</span>', '', html)
html = re.sub(r'<p>Todas las funciones del script en Ableton \(en inglés\)\..*?</p>', '<p>Todas las funciones y combinaciones de controles del script para Ableton Live 12.</p>', html)

# 5. Pie de página
html = html.replace('Guía de uso local · actualizada el 5 de octubre de 2026', 'Maschine MK3 as Ableton Push · Manual de Operaciones')

# Verificación
rem = re.findall(r'.{0,40}(?:virtualdj|virtual dj|vdj).{0,40}', html, re.IGNORECASE)
print(f'Menciones restantes de VirtualDJ: {len(rem)}')
for r in rem:
    print(' ', r)

with open(DEST, 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Archivo generado exitosamente en: {DEST}')
