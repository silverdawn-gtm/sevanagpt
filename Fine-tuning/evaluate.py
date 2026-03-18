"""Evaluate IndicTrans2 translation quality before and after fine-tuning.

Metrics:
  - BLEU and chrF++ via sacrebleu on val set
  - Terminology accuracy on glossary_test.jsonl (exact + fuzzy match)
  - Side-by-side HTML comparison of 50 sample translations

Usage:
  python evaluate.py --model base          # Evaluate base model
  python evaluate.py --model output/checkpoints/final/  # Evaluate fine-tuned
  python evaluate.py --compare             # Compare base vs fine-tuned
"""

import argparse
import json
import os
from pathlib import Path

import sacrebleu
import torch
from tqdm import tqdm
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRUST_REMOTE_CODE"] = "1"

import config

try:
    from IndicTransToolkit import IndicProcessor
except ImportError:
    IndicProcessor = None

try:
    from peft import PeftModel
except ImportError:
    PeftModel = None


def load_model(model_path: str):
    """Load base or fine-tuned model."""
    device = "cuda" if torch.cuda.is_available() else "cpu"

    tokenizer = AutoTokenizer.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
    )

    base_model = AutoModelForSeq2SeqLM.from_pretrained(
        config.MODEL_NAME,
        trust_remote_code=True,
        cache_dir=config.MODEL_CACHE_DIR,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device)

    if model_path != "base":
        adapter_path = Path(model_path)
        if adapter_path.is_dir() and PeftModel is not None:
            print(f"Loading LoRA adapter from {adapter_path}")
            base_model = PeftModel.from_pretrained(base_model, str(adapter_path))
        else:
            print(f"WARNING: Could not load adapter from {model_path}")

    base_model.eval()

    processor = None
    if IndicProcessor is not None:
        processor = IndicProcessor(inference=True)

    return base_model, tokenizer, processor, device


def translate_batch(model, tokenizer, processor, texts, device, batch_size=2):
    """Translate a batch of English texts to Malayalam."""
    results = []

    for i in tqdm(range(0, len(texts), batch_size), desc="Translating"):
        batch = texts[i:i + batch_size]

        if processor is not None:
            preprocessed = processor.preprocess_batch(
                batch, src_lang=config.SOURCE_LANG, tgt_lang=config.TARGET_LANG
            )
        else:
            preprocessed = batch

        inputs = tokenizer(
            preprocessed,
            truncation=True,
            padding="longest",
            max_length=config.MAX_SEQ_LENGTH,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            generated = model.generate(
                **inputs,
                num_beams=1,
                num_return_sequences=1,
                max_length=config.MAX_SEQ_LENGTH,
                use_cache=False,
            )

        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True,
                                         clean_up_tokenization_spaces=True)

        if processor is not None:
            decoded = processor.postprocess_batch(decoded, lang=config.TARGET_LANG)

        results.extend(decoded)

        # Free VRAM
        del inputs, generated
        if device == "cuda":
            torch.cuda.empty_cache()

    return results


def load_jsonl(path):
    data = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def compute_metrics(predictions, references):
    """Compute BLEU and chrF++ scores."""
    bleu = sacrebleu.corpus_bleu(predictions, [references])
    chrf = sacrebleu.corpus_chrf(predictions, [references], word_order=2)
    return {
        "bleu": round(bleu.score, 2),
        "bleu_details": str(bleu),
        "chrf++": round(chrf.score, 2),
        "chrf_details": str(chrf),
    }


def terminology_accuracy(predictions, references):
    """Compute exact and fuzzy match rates for terminology."""
    exact = 0
    fuzzy = 0  # reference term appears as substring in prediction
    total = len(references)

    for pred, ref in zip(predictions, references):
        pred_lower = pred.lower().strip()
        ref_lower = ref.lower().strip()

        if pred_lower == ref_lower:
            exact += 1
            fuzzy += 1
        elif ref_lower in pred_lower or pred_lower in ref_lower:
            fuzzy += 1

    return {
        "exact_match": round(100 * exact / max(total, 1), 2),
        "fuzzy_match": round(100 * fuzzy / max(total, 1), 2),
        "total": total,
    }


def generate_html_comparison(samples, output_path):
    """Generate side-by-side HTML comparison."""
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Translation Comparison</title>
<style>
body { font-family: sans-serif; margin: 20px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; vertical-align: top; }
th { background: #f5f5f5; }
tr:nth-child(even) { background: #fafafa; }
.improved { background: #e8f5e9; }
.degraded { background: #ffebee; }
</style>
</head><body>
<h1>IndicTrans2 Fine-tuning: Translation Comparison</h1>
<table>
<tr><th>#</th><th>English</th><th>Reference (ML)</th><th>Base Model</th><th>Fine-tuned</th></tr>
"""
    for i, s in enumerate(samples, 1):
        html += f"""<tr>
<td>{i}</td>
<td>{s['en']}</td>
<td>{s['ref']}</td>
<td>{s.get('base', 'N/A')}</td>
<td>{s.get('finetuned', 'N/A')}</td>
</tr>\n"""

    html += "</table></body></html>"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML comparison saved to {output_path}")


def evaluate(model_path: str):
    """Run evaluation on val set and glossary."""
    print(f"\n{'='*60}")
    print(f"Evaluating: {model_path}")
    print(f"{'='*60}")

    model, tokenizer, processor, device = load_model(model_path)

    results = {"model": model_path}

    # ── Val set evaluation ───────────────────────────────────────────────
    val_path = config.PROCESSED_DIR / "val.jsonl"
    if val_path.exists():
        val_data = load_jsonl(val_path)
        print(f"\nVal set: {len(val_data)} pairs")

        en_texts = [p["en"] for p in val_data]
        ml_refs = [p["ml"] for p in val_data]

        print("Translating val set...")
        predictions = translate_batch(model, tokenizer, processor, en_texts, device)

        metrics = compute_metrics(predictions, ml_refs)
        results["val_metrics"] = metrics
        print(f"  BLEU: {metrics['bleu']}")
        print(f"  chrF++: {metrics['chrf++']}")

    # ── Glossary evaluation ──────────────────────────────────────────────
    glossary_path = config.PROCESSED_DIR / "glossary_test.jsonl"
    if glossary_path.exists():
        glossary_data = load_jsonl(glossary_path)
        print(f"\nGlossary test: {len(glossary_data)} terms")

        en_terms = [p["en"] for p in glossary_data]
        ml_refs = [p["ml"] for p in glossary_data]

        predictions = translate_batch(model, tokenizer, processor, en_terms, device)

        term_acc = terminology_accuracy(predictions, ml_refs)
        results["terminology"] = term_acc
        print(f"  Exact match: {term_acc['exact_match']}%")
        print(f"  Fuzzy match: {term_acc['fuzzy_match']}%")

        # Store predictions for comparison
        results["glossary_predictions"] = [
            {"en": en, "ref": ref, "pred": pred}
            for en, ref, pred in zip(en_terms, ml_refs, predictions)
        ]

    # ── Save results ─────────────────────────────────────────────────────
    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    label = "base" if model_path == "base" else "finetuned"
    out_path = config.EVAL_DIR / f"eval_{label}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

    return results


def compare():
    """Compare base vs fine-tuned results and generate HTML report."""
    base_path = config.EVAL_DIR / "eval_base.json"
    ft_path = config.EVAL_DIR / "eval_finetuned.json"

    if not base_path.exists() or not ft_path.exists():
        print("Run evaluation for both base and fine-tuned models first:")
        print("  python evaluate.py --model base")
        print("  python evaluate.py --model output/checkpoints/final/")
        return

    with open(base_path, encoding="utf-8") as f:
        base = json.load(f)
    with open(ft_path, encoding="utf-8") as f:
        ft = json.load(f)

    print("\n" + "=" * 60)
    print("COMPARISON: Base vs Fine-tuned")
    print("=" * 60)

    if "val_metrics" in base and "val_metrics" in ft:
        print("\nVal Set Metrics:")
        print(f"  {'Metric':<15} {'Base':>10} {'Fine-tuned':>12} {'Delta':>10}")
        print(f"  {'-'*47}")
        for metric in ["bleu", "chrf++"]:
            b = base["val_metrics"][metric]
            f_val = ft["val_metrics"][metric]
            delta = f_val - b
            sign = "+" if delta > 0 else ""
            print(f"  {metric:<15} {b:>10.2f} {f_val:>12.2f} {sign}{delta:>9.2f}")

    if "terminology" in base and "terminology" in ft:
        print("\nTerminology Accuracy:")
        for metric in ["exact_match", "fuzzy_match"]:
            b = base["terminology"][metric]
            f_val = ft["terminology"][metric]
            delta = f_val - b
            sign = "+" if delta > 0 else ""
            print(f"  {metric:<15} {b:>9.1f}% {f_val:>11.1f}% {sign}{delta:>8.1f}%")

    # Generate HTML comparison from glossary predictions
    if "glossary_predictions" in base and "glossary_predictions" in ft:
        base_preds = {p["en"]: p["pred"] for p in base["glossary_predictions"]}
        ft_preds = {p["en"]: p["pred"] for p in ft["glossary_predictions"]}

        samples = []
        for p in ft["glossary_predictions"][:50]:
            samples.append({
                "en": p["en"],
                "ref": p["ref"],
                "base": base_preds.get(p["en"], "N/A"),
                "finetuned": p["pred"],
            })

        html_path = config.EVAL_DIR / "comparison.html"
        generate_html_comparison(samples, html_path)

    # Save comparison summary
    summary_path = config.EVAL_DIR / "comparison_summary.json"
    summary = {
        "base_val": base.get("val_metrics", {}),
        "finetuned_val": ft.get("val_metrics", {}),
        "base_terminology": base.get("terminology", {}),
        "finetuned_terminology": ft.get("terminology", {}),
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nComparison summary saved to {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate IndicTrans2 translation quality")
    parser.add_argument("--model", type=str, default="base",
                        help="'base' or path to LoRA adapter checkpoint")
    parser.add_argument("--compare", action="store_true",
                        help="Compare base vs fine-tuned results")
    args = parser.parse_args()

    if args.compare:
        compare()
    else:
        evaluate(args.model)
