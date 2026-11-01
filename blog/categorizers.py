import os
import numpy as np
from functools import lru_cache
from fastembed import TextEmbedding

from .models import Category  

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

SIMILARITY_THRESHOLD = 0.30  # tune this (0.25 - 0.45)


@lru_cache(maxsize=1)
def _model():
    return TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")


def _embed(texts):
    vecs = np.array(list(_model().embed(texts)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)  # normalize


def _clean(keywords):
    seen, out = set(), []
    for k in keywords or []:
        k = str(k).strip().strip(".'\"")
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out


def predict_category(keywords, user):
    keywords = _clean(keywords)
    if not keywords:
        return None

    kw_vecs = _embed(keywords)                      # (K, D)
    categories = list(Category.objects.all())

    # 1) Try matching existing categories
    if categories:
        cat_vecs = _embed([c.name for c in categories])   # (C, D)
        scores = (kw_vecs @ cat_vecs.T).mean(axis=0)      # avg sim per category
        best = int(scores.argmax())
        if scores[best] >= SIMILARITY_THRESHOLD:
            return categories[best]

    # 2) No match -> create new category named after the most representative keyword
    centroid = kw_vecs.mean(axis=0)
    name = keywords[int((kw_vecs @ centroid).argmax())].title()

    existing = Category.objects.filter(name__iexact=name).first()
    return existing or Category.objects.create(name=name, created_by=user)