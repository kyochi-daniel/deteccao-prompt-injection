"""Treinamento CPU reproduzível; configuração fixa, sem ajuste pelo teste."""
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import time

import numpy as np
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from dataset import build_dataset
from infer import classify, normalize, tokenize

ROOT = Path(__file__).resolve().parent
THRESHOLD = 0.5
BASELINE = r"\b(ignore|desconsidere|esqueca|revele|senhas|segredos|system)\b|sem filtros|prompt interno"


def evaluate(rows, probabilities):
    y = [row["label"] for row in rows]
    predicted = [int(p >= THRESHOLD) for p in probabilities]
    precision, recall, f1, _ = precision_recall_fscore_support(y, predicted, average="binary", zero_division=0)
    errors = [{"id": row["id"], "text": row["text"], "group": row["group"],
               "label": row["label"], "predicted": pred, "probability": float(prob)}
              for row, pred, prob in zip(rows, predicted, probabilities) if row["label"] != pred]
    return {"n": len(rows), "precision": float(precision), "recall": float(recall), "f1": float(f1),
            "accuracy": float(accuracy_score(y, predicted)), "confusion_matrix": confusion_matrix(y, predicted, labels=[0, 1]).tolist(),
            "support": {"benigno": y.count(0), "injecao": y.count(1)},
            "false_positives": [error for error in errors if error["label"] == 0],
            "false_negatives": [error for error in errors if error["label"] == 1]}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def train():
    rows = build_dataset()
    splits = {name: [row for row in rows if row["split"] == name]
              for name in ["train", "validation", "test", "challenge"]}
    assert len({row["text"] for row in rows}) == len(rows), "Textos duplicados no corpus"
    groups = {name: {row["group"] for row in subset} for name, subset in splits.items()}
    for i, name in enumerate(groups):
        for other in list(groups)[i + 1:]:
            assert groups[name].isdisjoint(groups[other]), "Famílias sobrepostas"
    dataset_text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "dataset.jsonl").write_text(dataset_text, encoding="utf-8")
    training = splits["train"]
    vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False,
                                 ngram_range=(1, 2), sublinear_tf=True, smooth_idf=True, norm="l2", min_df=1)
    start = time.perf_counter()
    x = vectorizer.fit_transform([row["text"] for row in training])
    classifier = LogisticRegression(C=4.0, solver="liblinear", max_iter=1000, random_state=42)
    classifier.fit(x, [row["label"] for row in training])
    elapsed = time.perf_counter() - start
    model = {"schema_version": 1, "name": "Modelo para detecção de prompt injection", "version": "1.0.0",
             "classes": ["benigno", "injecao"], "threshold": THRESHOLD,
             "pipeline": {"normalization": "NFKD_remove_marks_lowercase", "token_pattern": "[a-z0-9_]{2,}",
                          "ngram_range": [1, 2], "sublinear_tf": True, "smooth_idf": True, "norm": "l2"},
             "vocabulary": {term: int(index) for term, index in vectorizer.vocabulary_.items()},
             "idf": vectorizer.idf_.tolist(), "coefficients": classifier.coef_[0].tolist(),
             "intercept": float(classifier.intercept_[0]),
             "training": {"algorithm": "LogisticRegression", "C": 4.0, "solver": "liblinear", "random_state": 42,
                          "samples": len(training), "dataset_sha256": hashlib.sha256(dataset_text.encode()).hexdigest()}}
    write_json(ROOT / "model" / "model.json", model)
    shutil.copyfile(ROOT / "model" / "model.json", ROOT / "space" / "model.json")
    inference_source = (ROOT / "infer.py").read_text(encoding="utf-8")
    (ROOT / "model" / "infer.py").write_text(inference_source.replace('ROOT / "model" / "model.json"', 'ROOT / "model.json"'), encoding="utf-8")
    shutil.copyfile(ROOT / "LICENSE", ROOT / "model" / "LICENSE")
    evaluations = {}
    for name in ["validation", "test", "challenge"]:
        subset = splits[name]
        probabilities = classifier.predict_proba(vectorizer.transform([row["text"] for row in subset]))[:, 1]
        portable = np.array([classify(row["text"], model)["probability"] for row in subset])
        assert np.max(np.abs(probabilities - portable)) < 1e-12, "Exportação diverge do scikit-learn"
        baseline = [float(bool(re.search(BASELINE, normalize(row["text"])))) for row in subset]
        evaluations[name] = {"model": evaluate(subset, probabilities), "baseline": evaluate(subset, baseline)}
    metrics = {"dataset": {"total": len(rows), **{name: len(subset) for name, subset in splits.items()},
                           "groups": {name: sorted(value) for name, value in groups.items()}},
               "threshold": THRESHOLD, "positive_class": "injecao", "confusion_order": [["TN", "FP"], ["FN", "TP"]],
               "evaluations": evaluations,
               "training": {"seconds": elapsed, "features": len(vectorizer.vocabulary_), "python": platform.python_version(),
                            "scikit_learn": sklearn.__version__, "dataset_sha256": model["training"]["dataset_sha256"]},
               "baseline": {"type": "regex_fixed_before_training", "pattern": BASELINE},
               "limitations": ["Corpus sintético autoral; não mede desempenho em tráfego real.",
                               "Variantes de uma família são correlacionadas; a unidade de separação é a família.",
                               "Poucas famílias de teste; não há estimativa robusta de generalização.",
                               "Escore do classificador não é probabilidade de segurança calibrada.",
                               "Não executa, protege ou valida um LLM. Não é firewall de produção."]}
    write_json(ROOT / "reports" / "metrics.json", metrics)
    shutil.copyfile(ROOT / "reports" / "metrics.json", ROOT / "space" / "metrics.json")
    fixture_texts = [row["text"] for row in splits["challenge"]] + [
        "AÇÃO ação AÇÃO café, versão 2.0 e API_TOKEN", "🙂 漢字 🔐", "___ prompt prompt prompt",
        "SYSTEM\n\nignore\tREGRAS", "İıß Æ Ç a x 42", "e\u0301 cafe\u0301", "Ⓐ ① ﬁ ＡＢＣ",
        "constructor __proto__ toString hasOwnProperty"]
    fixtures = [{"text": text, **classify(text, model)} for text in fixture_texts]
    write_json(ROOT / "tests" / "parity-fixtures.json", fixtures)
    shutil.copyfile(ROOT / "tests" / "parity-fixtures.json", ROOT / "space" / "parity-fixtures.json")
    lines = ["# Avaliação congelada", "", "Classe positiva: tentativa de injeção. Limiar fixo: 0,50.", "",
             "Famílias inteiras foram separadas antes do treino; TF-IDF foi ajustado somente no treino.",
             "C=4, solver liblinear e limiar 0,50 foram fixados antes de avaliar. Nenhum ajuste pelo teste.", "",
             "| Partição | Método | N | Precisão | Recall | F1 | TN / FP / FN / TP |", "|---|---|---:|---:|---:|---:|---|"]
    for name, methods in evaluations.items():
        for method, result in methods.items():
            tn, fp, fn, tp = np.array(result["confusion_matrix"]).ravel()
            lines.append(f"| {name} | {method} | {result['n']} | {result['precision']:.3f} | {result['recall']:.3f} | {result['f1']:.3f} | {tn} / {fp} / {fn} / {tp} |")
    lines += ["", "## Interpretação", "", *[f"- {limit}" for limit in metrics["limitations"]], "",
              "As 32 variantes por família não são 32 observações independentes. Temas são compartilhados entre classes; templates e famílias não cruzam partições.",
              "O desafio manual separado contém casos adversariais e palavras suspeitas em pedidos benignos. Não foi usado para selecionar parâmetros.",
              "A validação foi apenas reportada: esta versão não faz busca de hiperparâmetros nem escolhe limiar.", "",
              f"Treino medido: {elapsed:.4f} s (somente vetorização e ajuste, nesta máquina). Vocabulário: {len(vectorizer.vocabulary_)} features.",
              "", "## Erros observados", "", "Todos os falsos positivos e negativos, textos e escores estão em `metrics.json`. Exemplos:", ""]
    for name in ["test", "challenge"]:
        for kind in ["false_positives", "false_negatives"]:
            lines.append(f"### {name}: {kind}")
            lines.append("")
            errors = evaluations[name]["model"][kind]
            lines.extend([f"- {error['text']} (escore: {error['probability']:.3f})" for error in errors[:5]] or ["Nenhum neste conjunto sintético."])
            lines.append("")
    (ROOT / "reports" / "evaluation.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"samples": metrics["dataset"], "features": len(vectorizer.vocabulary_),
                      "test": evaluations["test"]["model"], "challenge": evaluations["challenge"]["model"]}, ensure_ascii=False, indent=2))
    return model, metrics


if __name__ == "__main__":
    train()
