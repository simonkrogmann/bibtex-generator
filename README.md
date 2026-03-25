# bibtex-generator
Takes citations (formatted in e.g. APA) and generates a bibtex file using DOI lookups and optionally an LLM.

## Preparation


If the bibtex is supposed to be pretty:
```
pip install bibtexparser
```

If citations without a DOI should receive a bibtex entry, install ollama using your favorite package manager, then:

```
ollama pull mistral
pip install ollama
```

Alternatively you can use another model. The default model mistral runs locally on your computer. It is relatively quick and reasonably accurate.

## Usage

Create a file where each citation is on its own line (e.g. by copying the citations from a word file to a text file). Then run:

```
python3 bibtex-generator.py -i references.txt -o references.bib
```

Or with an LLM:

```
python3 bibtex-generator.py -i references.txt -o references.bib -llm
```

Specify a model with `-m <model_name>`. LLM-generated entries will have a note on them.

A file called `bibtex-generator-cache.pickle` is generated that caches web requests.
