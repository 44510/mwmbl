"""
Create a search index
"""
from collections import Counter
from typing import Iterable
from urllib.parse import unquote

import pandas as pd

from mwmbl.tinysearchengine.indexer import Document, TokenizedDocument, TinyIndex

DEFAULT_SCORE = 0

HTTP_START = 'http://'
HTTPS_START = 'https://'
BATCH_SIZE = 100


def is_content_token(nlp, token):
    lexeme = nlp.vocab[token.orth]
    return (lexeme.is_alpha or lexeme.is_digit) and not token.is_stop


def tokenize(nlp, input_text):
    cleaned_text = input_text.encode('utf8', 'replace').decode('utf8')
    tokens = nlp.tokenizer(cleaned_text)
    if input_text.endswith('…'):
        # Discard the last two tokens since there will likely be a word cut in two
        tokens = tokens[:-2]
    content_tokens = [token for token in tokens if is_content_token(nlp, token)]
    lowered = {nlp.vocab[token.orth].text.lower() for token in content_tokens}
    return lowered


def prepare_url_for_tokenizing(url: str):
    if url.startswith(HTTP_START):
        url = url[len(HTTP_START):]
    elif url.startswith(HTTPS_START):
        url = url[len(HTTPS_START):]
    for c in '/._':
        if c in url:
            url = url.replace(c, ' ')
    return url


def get_pages(nlp, titles_urls_and_extracts, link_counts) -> Iterable[TokenizedDocument]:
    for i, (title_cleaned, url, extract) in enumerate(titles_urls_and_extracts):
        title_tokens = tokenize(nlp, title_cleaned)
        prepared_url = prepare_url_for_tokenizing(unquote(url))
        url_tokens = tokenize(nlp, prepared_url)
        extract_tokens = tokenize(nlp, extract)
        print("Extract tokens", extract_tokens)
        tokens = title_tokens | url_tokens | extract_tokens
        score = link_counts.get(url, DEFAULT_SCORE)
        yield TokenizedDocument(tokens=list(tokens), url=url, title=title_cleaned, extract=extract, score=score)

        if i % 1000 == 0:
            print("Processed", i)


def index_titles_urls_and_extracts(indexer: TinyIndex, nlp, titles_urls_and_extracts, link_counts, terms_path):
    terms = Counter()
    pages = get_pages(nlp, titles_urls_and_extracts, link_counts)
    for page in pages:
        for token in page.tokens:
            indexer.index(token, Document(url=page.url, title=page.title, extract=page.extract, score=page.score))
        terms.update([t.lower() for t in page.tokens])

    term_df = pd.DataFrame({
        'term': terms.keys(),
        'count': terms.values(),
    })
    term_df.to_csv(terms_path)
