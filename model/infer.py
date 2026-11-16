"""Inferência do artefato JSON, usando somente a biblioteca padrão do Python."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parent
MAX_LENGTH = 12000


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.category(c).startswith("M")).lower()


def tokenize(text):
    return re.findall(r"[a-z0-9_]{2,}", normalize(text))


def classify(text, model):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Informe um texto não vazio.")
    if len(text) > MAX_LENGTH:
        raise ValueError(f"O limite é {MAX_LENGTH} caracteres.")
    if model.get("schema_version") != 1:
        raise ValueError("Versão de modelo não suportada.")
    tokens = tokenize(text)
    counts = Counter(tokens + [f"{a} {b}" for a, b in zip(tokens, tokens[1:])])
    features = []
    for term, count in counts.items():
        index = model["vocabulary"].get(term)
        if index is not None:
            features.append((term, index, (1 + math.log(count)) * model["idf"][index]))
    norm = math.sqrt(sum(value * value for _, _, value in features)) or 1
    signals = [{"term": term, "contribution": value / norm * model["coefficients"][index]}
               for term, index, value in features]
    score = model["intercept"] + sum(item["contribution"] for item in signals)
    probability = 1 / (1 + math.exp(-score)) if score >= 0 else math.exp(score) / (1 + math.exp(score))
    return {"probability": probability, "score": score,
            "label": "injecao" if probability >= model["threshold"] else "benigno",
            "signals": sorted(signals, key=lambda item: -abs(item["contribution"]))[:10],
            "knownTerms": len(features), "tokenCount": len(tokens),
            "knownTokens": sum(token in model["vocabulary"] for token in tokens)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Classificador acadêmico de textos PT-BR")
    parser.add_argument("text")
    parser.add_argument("--model", type=Path, default=ROOT / "model.json")
    args = parser.parse_args()
    print(json.dumps(classify(args.text, json.loads(args.model.read_text(encoding="utf-8"))),
                     ensure_ascii=False, indent=2))
