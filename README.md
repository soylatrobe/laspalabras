# laspalabras
https://huggingface.co/datasets/projecte-aina/synthetic_dem

## Extraer palabras y significados

`extract_words.py` lee el split `definiciones` del dataset en modo streaming.
No descarga los archivos de audio: solo usa `filename` y `text`. Agrupa las
filas por palabra y conserva sus significados distintos, incluyendo las
palabras con más de un significado.

```bash
python -m pip install -r requirements.txt

# Todas las palabras, en JSON Lines
python extract_words.py --output words.jsonl

# Solo palabras con dos o más significados
python extract_words.py --min-meanings 2 --output palabras_polisemicas.jsonl

# La misma extracción en CSV
python extract_words.py --min-meanings 2 --format csv --output palabras_polisemicas.csv
```

Cada línea JSON tiene esta forma:

```json
{"word": "¡ah!", "meanings": ["Manifiesta asombro, sorpresa o adoración", "Confirma con asombro alguna cosa"], "meaning_count": 2}
```
