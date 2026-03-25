#!/usr/bin/python3
import re
import urllib.request
import pickle
from urllib.error import HTTPError
import argparse
import sys
try:
    import bibtexparser
    PRETTIFY = True
except ImportError:
    PRETTIFY = False
try:
    from ollama import chat, ResponseError
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
from collections.abc import Sequence

CACHE_FILE = 'bibtex-generator-cache.pickle'


class Reference:
    def __init__(self, text: str, doi: str | bool = False, bibtex: str | bool = False) -> None:
        self.text = text
        self.doi = doi
        self.bibtex = bibtex


def parse_references(references: Sequence[str]) -> Sequence[Reference]:
    parsed = []
    for line in references:
        if not line:
            continue
        res = re.search(r'https?://(dx.)?doi.org/([^\s]+)', line)
        res2 = re.search(r'doi: ?([^\s]+)', line)
        if res:
            doi = res.group(2)
        elif res2:
            doi = res2.group(1)
        else:
            doi = False
        if doi and doi[-1] == '.':
            doi = doi[:-1]
        parsed.append(Reference(line, doi))

    return parsed


def sort_and_deduplicate(parsed: Sequence[Reference], verbose: bool = False) -> Sequence[Reference]:
    parsed.sort(key=lambda x: (x.doi is False, x.doi))
    filtered = []
    for i, ref in enumerate(parsed):
        if i > 0 and ref.doi and ref.doi == parsed[i - 1].doi:
            if verbose:
                print('Warning: duplicate removed: ', ref.text)
            continue
        filtered.append(ref)
    return filtered


def prepare_cache() -> dict[str, str]:
    try:
        with open(CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
    except FileNotFoundError:
        return {}
    return cache


def save_cache(cache):
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(cache, f)


def prettify_bibtex(string:  dict[str, str]):
    if not PRETTIFY:
        return string
    # The round-trip through bibtexparser adds line endings.
    bibtex = bibtexparser.loads(string)
    return bibtexparser.dumps(bibtex)


# prepare doi resolution
BASE_URL = 'http://dx.doi.org/'


def resolve_doi(doi: str, cache:  dict[str, str]) -> str | bool:
    if doi in cache:
        return prettify_bibtex(cache[doi])
    url = BASE_URL + doi
    req = urllib.request.Request(url)
    req.add_header('Accept', 'application/x-bibtex')
    try:
        with urllib.request.urlopen(req) as f:
            bibtex = f.read().decode()
        cache[doi] = bibtex
        save_cache(cache)
        return prettify_bibtex(bibtex)
    except HTTPError as e:
        if e.code == 404:
            print(f'DOI not found: {doi}')
            return False
        print('Service unavailable.')
        sys.exit(0)


def create_ref_llm(text: str, model: str, verbose: bool = False) -> str | bool:
    stream = chat(
        model=model,
        messages=[{'role': 'system', 'content': 'You are very knowledgeable. An expert. Think and respond with confidence.'},
                  {'role': 'user', 'content': f'Can you create a bibtex entry for the following citation? Give no context, only the entry: {text}'}],
        stream=True,
    )
    thinking = False

    response = ''

    try:
        for chunk in stream:
            response += chunk.message.content
            if not verbose:
                continue
            if chunk.message.thinking and not thinking:
                thinking = True
                print('Thinking:\n', end='')
            if chunk.message.thinking:
                print(chunk.message.thinking, end='', flush=True)
            elif chunk.message.content:
                if thinking:
                    print('\n\nAnswer:\n', end='')
                    thinking = False
                print(chunk.message.content, end='', flush=True)
    except ResponseError as e:
        print(f'The model "{model}" is not available: {e}')
        sys.exit(2)
    # extract bibtex entry from AI response
    entry = re.search(r'@[a-z]+(.|\n)+?(\n})', response)
    if entry:
        return entry.group(0)
    return False


def printable(ref: str) -> str:
    if not ref.bibtex:
        return '% missing: ' + ref.text
    description = 'online lookup' if ref.doi else 'AI-generated, please check correctness'
    return f'% {ref.text}\n% {description}\n{ref.bibtex}'


def main() -> None:
    parser = argparse.ArgumentParser(description='Description of your program')
    parser.add_argument('-i', '--input', help='input file', required=True)
    parser.add_argument('-o', '--output', help='output file', required=True)
    parser.add_argument('-llm', '--llm', action='store_true', help='use llm to generate references?', required=False)
    parser.add_argument('-v', '--verbose', action='store_true', help='print warnings and llm output', required=False)
    parser.add_argument('-m', '--model', help='model to use to generate references without DOI, default: mistral', default='mistral', required=False)
    args = parser.parse_args()

    if not PRETTIFY:
        print('Warning: library "bibtexparser" not found. The bibtex references will not be formatted and instead print in one line.')

    with open(args.input, 'r') as f:
        text = f.read()
    parsed = parse_references(text.splitlines())
    filtered = sort_and_deduplicate(parsed, args.verbose)
    cache = prepare_cache()
    for i, ref in enumerate(filtered):
        print(f'Reference {i} of {len(filtered)}')
        if ref.doi:
            ref.bibtex = resolve_doi(ref.doi, cache)
            if not ref.bibtex:
                print(f'Error: Broken DOI {ref.doi} in ', ref.text)
        elif LLM_AVAILABLE and args.llm:
            ref.bibtex = create_ref_llm(ref.text, args.model, args.verbose)
            if not ref.bibtex:
                print("Error: The LLM failed to generate a reference for ", ref.text)
        else:
            print("Missing DOI for ", ref.text)

    with open(args.output, 'w') as f:
        print_ai_entries = [printable(ref) for ref in filtered]
        f.write('\n\n'.join(print_ai_entries))


if __name__ == '__main__':
    main()
