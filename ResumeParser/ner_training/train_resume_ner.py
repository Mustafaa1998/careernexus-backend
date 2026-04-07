# ner_training/train_resume_ner.py
# CLI-friendly spaCy NER trainer that reads DocBin files (train.spacy / dev.spacy)
# Usage:
#   python ner_training\train_resume_ner.py --train data\spacy_dataset\train.spacy --dev data\spacy_dataset\dev.spacy --out ner_training\models\resume_md_best --epochs 200 --batch 16 --dropout 0.25 --patience 1000

import argparse, random, spacy
from pathlib import Path
from spacy.training import Example
from spacy.util import minibatch
from spacy.tokens import DocBin

def load_examples(nlp, spacy_path: Path):
    db = DocBin().from_disk(spacy_path)
    return [Example(d, d) for d in db.get_docs(nlp.vocab)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--dev", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--dropout", type=float, default=0.25)
    ap.add_argument("--patience", type=int, default=1000)
    args = ap.parse_args()

    train_path = Path(args.train)
    dev_path = Path(args.dev)
    out_dir = Path(args.out)

    print("📘 Loading base model (en_core_web_md)...")
    nlp = spacy.load("en_core_web_md")
    if "ner" not in nlp.pipe_names:
        nlp.add_pipe("ner", last=True)
    ner = nlp.get_pipe("ner")

    # add labels from train DocBin
    tmp_blank = spacy.blank("en")
    for d in DocBin().from_disk(train_path).get_docs(tmp_blank.vocab):
        for e in d.ents:
            ner.add_label(e.label_)

    print(f"📂 Loading train/dev from {train_path} / {dev_path}")
    train_ex = load_examples(nlp, train_path)
    dev_ex   = load_examples(nlp, dev_path)

    other_pipes = [p for p in nlp.pipe_names if p != "ner"]
    best_f1 = 0.0
    stale = 0
    with nlp.disable_pipes(*other_pipes):
        optimizer = nlp.resume_training()
        for ep in range(1, args.epochs + 1):
            random.shuffle(train_ex)
            losses = {}
            for batch in minibatch(train_ex, size=args.batch):
                nlp.update(batch, sgd=optimizer, drop=args.dropout, losses=losses)

            # simple dev metrics
            tp = fp = fn = 0
            for ex in dev_ex:
                pred = nlp(ex.text)
                P = {(e.start_char, e.end_char, e.label_) for e in pred.ents}
                G = {(e.start_char, e.end_char, e.label_) for e in ex.reference.ents}
                tp += len(P & G)
                fp += len(P - G)
                fn += len(G - P)
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec  = tp / (tp + fn) if (tp + fn) else 0.0
            f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

            print(f"Epoch {ep:03d} | loss={losses.get('ner', 0):.2f} | dev P={prec:.3f} R={rec:.3f} F1={f1:.3f}")

            if f1 > best_f1 + 1e-4:
                best_f1 = f1
                stale = 0
                out_dir.mkdir(parents=True, exist_ok=True)
                nlp.to_disk(out_dir)
                print(f"  → saved best to {out_dir} (F1={best_f1:.3f})")
            else:
                stale += 1
                if stale >= args.patience:
                    print(f"Early stopping. Best F1={best_f1:.3f}")
                    break

if __name__ == "__main__":
    main()
