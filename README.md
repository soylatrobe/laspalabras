# laspalabras

Herramienta para consultar las definiciones del [Synthetic DEM
Corpus](https://huggingface.co/datasets/projecte-aina/synthetic_dem). Permite
buscar una palabra concreta y obtener todos sus significados, o exportar el
diccionario completo.

## Requisitos

- Python 3.9 o posterior.
- Acceso a Internet para leer el dataset de Hugging Face.
- Espacio para la caché local de metadatos y datos descargados por
  `datasets`. El programa no descarga ni procesa los audios.

## Instalación

Desde la raíz del proyecto, crea opcionalmente un entorno virtual e instala la
dependencia:

```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows PowerShell

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Consultar una palabra

`extract_words.py` lee el split `definiciones` en modo streaming. Solo usa los
campos `filename` y `text`, por lo que no descarga ni decodifica los archivos
de audio. La primera ejecución puede tardar porque debe recorrer las
definiciones del dataset; las ejecuciones posteriores aprovechan la caché de
Hugging Face.

Consulta una palabra con `--word`:

```bash
python extract_words.py --word "banco"
```

La respuesta se imprime como un objeto JSON con todos los significados:

```json
{"word": "banco", "meanings": ["Asiento para varias personas", "Institución financiera"], "meaning_count": 2}
```

La búsqueda no distingue mayúsculas ni minúsculas y acepta espacios alrededor
de la consulta:

```bash
python extract_words.py --word " BANCO "
```

Si no se encuentra la palabra, el programa escribe un mensaje en `stderr` y
termina con código de salida `1`.

Para guardar la respuesta:

```bash
python extract_words.py --word "banco" --output banco.jsonl
python extract_words.py --word "banco" --format csv --output banco.csv
```

## Exportar palabras

Sin `--word`, el programa agrupa todas las filas del split `definiciones` por
palabra y elimina definiciones duplicadas. Por defecto genera `words.jsonl`:

```bash
python extract_words.py --output words.jsonl
```

Cada línea representa una palabra:

```json
{"word": "¡ah!", "meanings": ["Manifiesta asombro, sorpresa o adoración", "Confirma con asombro alguna cosa"], "meaning_count": 2}
```

Para obtener únicamente palabras con al menos dos significados:

```bash
python extract_words.py \
  --min-meanings 2 \
  --output palabras_polisemicas.jsonl
```

El mismo resultado puede exportarse en CSV. La columna `meanings` contiene
todos los significados separados por ` | `:

```bash
python extract_words.py \
  --min-meanings 2 \
  --format csv \
  --output palabras_polisemicas.csv
```

`--min-meanings` también puede combinarse con `--word`:

```bash
python extract_words.py --word "banco" --min-meanings 2
```

## Opciones principales

```text
--word WORD              Palabra que se quiere consultar.
--output FILE, -o FILE   Archivo de salida. Sin esta opción, una consulta se
                         imprime en stdout y una exportación masiva usa
                         words.jsonl.
--format {jsonl,csv}     Formato de salida (por defecto: jsonl).
--min-meanings N         Número mínimo de significados (por defecto: 1).
```

El dataset y el split se pueden cambiar con `--dataset` y `--split` si se
necesita reutilizar el script con una estructura compatible:

```bash
python extract_words.py \
  --dataset projecte-aina/synthetic_dem \
  --split definiciones \
  --word "banco"
```

## Notas sobre los datos

La palabra se obtiene del campo `filename` del split `definiciones`, cuyo
formato es `<id>_<palabra>`. Cada fila aporta una definición. Las definiciones
repetidas para una misma palabra se conservan una sola vez. El dataset
Synthetic DEM está publicado bajo la licencia indicada en su ficha de
Hugging Face; consulta esa ficha antes de redistribuir resultados.
