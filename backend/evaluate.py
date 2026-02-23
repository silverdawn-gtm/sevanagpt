"""
SevanaGPT — Comprehensive Evaluation & Performance Metrics
==========================================================
Runs against the live backend (http://localhost:8000) and IndicTrans (port 7860).
Produces metrics + matplotlib graphs saved to backend/eval_results/.

Usage:
    cd backend && source venv/Scripts/activate
    python evaluate.py
"""

import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding for Indic scripts
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "http://localhost:8000"
INDICTRANS_URL = "http://localhost:7860"
OUT_DIR = Path(__file__).parent / "eval_results"
OUT_DIR.mkdir(exist_ok=True)

client = httpx.Client(timeout=30.0)

# Colour palette
COLORS = ["#4361ee", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0",
          "#06d6a0", "#ffd166", "#ef476f", "#118ab2", "#073b4c"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
})


def section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ===================================================================
# 1. API RESPONSE TIME BENCHMARKS
# ===================================================================
ENDPOINTS = [
    ("GET",  "/health",                              {}),
    ("GET",  "/api/v1/schemes",                      {}),
    ("GET",  "/api/v1/schemes?lang=hi",              {}),
    ("GET",  "/api/v1/categories",                   {}),
    ("GET",  "/api/v1/categories?lang=hi",           {}),
    ("GET",  "/api/v1/eligibility/options",           {}),
    ("POST", "/api/v1/search",                       {"query": "education scholarship"}),
    ("POST", "/api/v1/eligibility/check",            {"gender": "Female", "age": 25, "state_code": "KA", "social_category": "SC"}),
]

TARGET_LATENCIES = {
    "/health": 0.1,
    "/api/v1/schemes": 2.0,
    "/api/v1/schemes?lang=hi": 5.0,
    "/api/v1/categories": 0.5,
    "/api/v1/categories?lang=hi": 2.0,
    "/api/v1/eligibility/options": 0.5,
    "/api/v1/search": 3.0,
    "/api/v1/eligibility/check": 1.0,
}

RUNS_PER_ENDPOINT = 3  # average over N runs


def benchmark_apis():
    section("1. API Response Time Benchmarks")
    results = {}

    for method, path, body in ENDPOINTS:
        times = []
        status = None
        for _ in range(RUNS_PER_ENDPOINT):
            start = time.perf_counter()
            try:
                if method == "GET":
                    resp = client.get(f"{BASE_URL}{path}")
                else:
                    resp = client.post(f"{BASE_URL}{path}", json=body)
                elapsed = time.perf_counter() - start
                status = resp.status_code
                times.append(elapsed)
            except Exception as e:
                print(f"  ERROR {method} {path}: {e}")
                times.append(float("nan"))

        avg = statistics.mean([t for t in times if not np.isnan(t)]) if times else 0
        target = TARGET_LATENCIES.get(path.split("?")[0], TARGET_LATENCIES.get(path, 5.0))
        passed = avg < target
        label = f"{method} {path}"
        results[label] = {"avg_ms": round(avg * 1000, 1), "status": status, "target_ms": target * 1000, "pass": passed}
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {label:50s}  {avg*1000:7.1f}ms  (target < {target*1000:.0f}ms)  HTTP {status}")

    # --- Graph ---
    labels = list(results.keys())
    avgs = [results[l]["avg_ms"] for l in labels]
    targets = [results[l]["target_ms"] for l in labels]
    passes = [results[l]["pass"] for l in labels]
    short_labels = [l.replace("/api/v1/", "/") for l in labels]

    fig, ax = plt.subplots(figsize=(12, 6))
    y = np.arange(len(labels))
    bar_colors = ["#06d6a0" if p else "#ef476f" for p in passes]
    bars = ax.barh(y, avgs, color=bar_colors, edgecolor="white", height=0.6)
    ax.barh(y, targets, color="none", edgecolor="#073b4c", linewidth=1.5, linestyle="--", height=0.6, label="Target")
    ax.set_yticks(y)
    ax.set_yticklabels(short_labels, fontsize=9)
    ax.set_xlabel("Response Time (ms)")
    ax.set_title("API Response Time Benchmarks", fontsize=14, fontweight="bold")
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    for bar, val in zip(bars, avgs):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height()/2, f"{val:.0f}ms", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "api_response_times.png", dpi=150)
    plt.close()
    print(f"\n  -> Graph saved: eval_results/api_response_times.png")
    return results


# ===================================================================
# 2. SEARCH QUALITY METRICS  (Precision@K, Recall@K, MRR, F1)
# ===================================================================
SEARCH_TEST_CASES = [
    {"query": "education scholarship for students",
     "expected_slugs": ["national-scholarship-portal-schemes",
                        "national-education-policy-scholarship-for-higher-education",
                        "post-matric-scholarship-for-sc-students",
                        "sukanya-samriddhi-yojana"]},
    {"query": "health insurance for poor families",
     "expected_slugs": ["ayushman-bharat-pradhan-mantri-jan-arogya-yojana-ab-pmjay",
                        "pradhan-mantri-jan-dhan-yojana-pmjdy",
                        "pradhan-mantri-fasal-bima-yojana-pmfby"]},
    {"query": "housing scheme for BPL",
     "expected_slugs": ["ayushman-bharat-pradhan-mantri-jan-arogya-yojana-ab-pmjay",
                        "atal-pension-yojana-apy",
                        "pradhan-mantri-awas-yojana-pmay"]},
    {"query": "farmer loan waiver agriculture",
     "expected_slugs": ["mahatma-phule-shetkari-karj-mukti-yojana",
                        "pradhan-mantri-fasal-bima-yojana-pmfby",
                        "pradhan-mantri-kisan-samman-nidhi-pm-kisan"]},
    {"query": "women empowerment self help group",
     "expected_slugs": ["deendayal-antyodaya-yojana-national-rural-livelihoods-mission-day-nrlm",
                        "mukhyamantri-majhi-ladki-bahin-yojana",
                        "pradhan-mantri-ujjwala-yojana-pmuy"]},
]


def _search(query: str, limit: int = 10):
    try:
        resp = client.post(f"{BASE_URL}/api/v1/search", json={"query": query, "limit": limit})
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else data.get("results", data.get("items", []))
    except Exception:
        return []


def evaluate_search():
    section("2. Search Quality Metrics")
    all_precisions = {5: [], 10: []}
    all_recalls = {5: [], 10: []}
    all_rrs = []
    per_query = []

    for case in SEARCH_TEST_CASES:
        results = _search(case["query"], limit=10)
        result_slugs = []
        for r in results[:10]:
            slug = r.get("slug", "")
            if not slug and isinstance(r, dict):
                scheme = r.get("scheme", {})
                slug = scheme.get("slug", "") if isinstance(scheme, dict) else ""
            result_slugs.append(slug)

        expected = set(case["expected_slugs"])

        # Per-K metrics
        for k in [5, 10]:
            retrieved = set(result_slugs[:k])
            relevant = retrieved & expected
            precision = len(relevant) / k if k > 0 else 0
            recall = len(relevant) / len(expected) if expected else 0
            all_precisions[k].append(precision)
            all_recalls[k].append(recall)

        # MRR
        rr = 0.0
        for rank, slug in enumerate(result_slugs, 1):
            if slug in expected:
                rr = 1.0 / rank
                break
        all_rrs.append(rr)

        # F1 for k=10
        p10 = all_precisions[10][-1]
        r10 = all_recalls[10][-1]
        f1 = 2 * p10 * r10 / (p10 + r10) if (p10 + r10) > 0 else 0.0

        per_query.append({
            "query": case["query"],
            "results_returned": len(results),
            "precision@5": round(all_precisions[5][-1], 3),
            "precision@10": round(p10, 3),
            "recall@10": round(r10, 3),
            "mrr": round(rr, 3),
            "f1@10": round(f1, 3),
        })

    # Aggregate
    avg_p5 = statistics.mean(all_precisions[5]) if all_precisions[5] else 0
    avg_p10 = statistics.mean(all_precisions[10]) if all_precisions[10] else 0
    avg_r5 = statistics.mean(all_recalls[5]) if all_recalls[5] else 0
    avg_r10 = statistics.mean(all_recalls[10]) if all_recalls[10] else 0
    avg_mrr = statistics.mean(all_rrs) if all_rrs else 0
    avg_f1 = 2 * avg_p10 * avg_r10 / (avg_p10 + avg_r10) if (avg_p10 + avg_r10) > 0 else 0

    print(f"\n  {'Query':<45s} {'P@5':>6s} {'P@10':>6s} {'R@10':>6s} {'MRR':>6s} {'F1@10':>6s}")
    print(f"  {'-'*45} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for pq in per_query:
        print(f"  {pq['query']:<45s} {pq['precision@5']:6.3f} {pq['precision@10']:6.3f} {pq['recall@10']:6.3f} {pq['mrr']:6.3f} {pq['f1@10']:6.3f}")
    print(f"  {'-'*45} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    print(f"  {'AVERAGE':<45s} {avg_p5:6.3f} {avg_p10:6.3f} {avg_r10:6.3f} {avg_mrr:6.3f} {avg_f1:6.3f}")

    aggregate = {
        "precision@5": round(avg_p5, 4),
        "precision@10": round(avg_p10, 4),
        "recall@5": round(avg_r5, 4),
        "recall@10": round(avg_r10, 4),
        "mrr": round(avg_mrr, 4),
        "f1@10": round(avg_f1, 4),
    }

    # --- Graph 1: Aggregate bar chart ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    metrics_names = ["Precision@5", "Precision@10", "Recall@5", "Recall@10", "MRR", "F1@10"]
    metrics_vals = [avg_p5, avg_p10, avg_r5, avg_r10, avg_mrr, avg_f1]
    bars = axes[0].bar(metrics_names, metrics_vals, color=COLORS[:6], edgecolor="white", width=0.6)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("Score")
    axes[0].set_title("Search Quality — Aggregate Metrics", fontsize=13, fontweight="bold")
    axes[0].yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    for bar, val in zip(bars, metrics_vals):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, f"{val:.1%}", ha="center", fontsize=9)

    # --- Graph 2: Per-query grouped bar ---
    queries_short = [pq["query"][:25] + "..." for pq in per_query]
    x = np.arange(len(queries_short))
    w = 0.18
    axes[1].bar(x - 1.5*w, [pq["precision@5"] for pq in per_query], w, label="P@5", color=COLORS[0])
    axes[1].bar(x - 0.5*w, [pq["precision@10"] for pq in per_query], w, label="P@10", color=COLORS[1])
    axes[1].bar(x + 0.5*w, [pq["recall@10"] for pq in per_query], w, label="R@10", color=COLORS[2])
    axes[1].bar(x + 1.5*w, [pq["f1@10"] for pq in per_query], w, label="F1@10", color=COLORS[3])
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(queries_short, rotation=25, ha="right", fontsize=8)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Score")
    axes[1].set_title("Search Quality — Per Query", fontsize=13, fontweight="bold")
    axes[1].legend(fontsize=8, loc="upper right")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "search_quality.png", dpi=150)
    plt.close()
    print(f"\n  -> Graph saved: eval_results/search_quality.png")
    return aggregate, per_query


# ===================================================================
# 3. TRANSLATION QUALITY — BLEU Scores
# ===================================================================
REFERENCE_TRANSLATIONS_HI = [
    ("National Scholarship for Students", "छात्रों के लिए राष्ट्रीय छात्रवृत्ति"),
    ("Women Empowerment Programme", "महिला सशक्तिकरण कार्यक्रम"),
    ("Housing for All", "सबके लिए आवास"),
    ("Farmer Income Support Scheme", "किसान आय सहायता योजना"),
    ("Health Insurance Scheme", "स्वास्थ्य बीमा योजना"),
    ("Digital India Programme", "डिजिटल भारत कार्यक्रम"),
    ("Clean Water Mission", "स्वच्छ जल मिशन"),
    ("Rural Employment Guarantee", "ग्रामीण रोजगार गारंटी"),
]


def evaluate_translation():
    section("3. Translation Quality Metrics (BLEU)")

    try:
        import sacrebleu
    except ImportError:
        print("  sacrebleu not installed — skipping BLEU evaluation")
        return {}

    results = {}

    # Try IndicTrans2 directly first, then fall back to backend translate endpoint
    indictrans_ok = False
    try:
        r = client.get(f"{INDICTRANS_URL}/health")
        if r.status_code == 200 and r.json().get("ready", False):
            # Quick smoke test
            r2 = client.post(f"{INDICTRANS_URL}/translate",
                             json={"text": "hello", "source_lang": "en", "target_lang": "hi"}, timeout=15)
            indictrans_ok = r2.status_code == 200
    except Exception:
        pass

    engine = "IndicTrans2" if indictrans_ok else "Backend (Google Translate fallback)"
    print(f"  Translation engine: {engine}")

    hypotheses = []
    references = []
    individual_bleu = []

    for en_text, hi_ref in REFERENCE_TRANSLATIONS_HI:
        try:
            if indictrans_ok:
                resp = client.post(f"{INDICTRANS_URL}/translate", json={
                    "text": en_text, "source_lang": "en", "target_lang": "hi"
                }, timeout=15)
            else:
                resp = client.post(f"{BASE_URL}/api/v1/translate", json={
                    "text": en_text, "target_lang": "hi"
                }, timeout=15)

            if resp.status_code == 200:
                translated = resp.json().get("translated_text", resp.json().get("text", ""))
                if translated and translated != en_text:
                    hypotheses.append(translated)
                    references.append(hi_ref)
                    s_bleu = sacrebleu.sentence_bleu(translated, [hi_ref])
                    individual_bleu.append({"source": en_text, "reference": hi_ref,
                                            "hypothesis": translated, "bleu": round(s_bleu.score, 2)})
        except Exception as e:
            print(f"    Error translating '{en_text}': {e}")

    if hypotheses:
        corpus_bleu = sacrebleu.corpus_bleu(hypotheses, [references])
        key_prefix = "indictrans" if indictrans_ok else "google"
        results[f"{key_prefix}_corpus_bleu"] = round(corpus_bleu.score, 2)
        results[f"{key_prefix}_brevity_penalty"] = round(corpus_bleu.bp, 4)
        results[f"{key_prefix}_sentences_tested"] = len(hypotheses)
        results[f"{key_prefix}_individual"] = individual_bleu

        print(f"\n  {engine} BLEU Results:")
        print(f"    Corpus BLEU:      {corpus_bleu.score:.2f}")
        print(f"    Brevity Penalty:  {corpus_bleu.bp:.4f}")
        print(f"    Sentences tested: {len(hypotheses)}/{len(REFERENCE_TRANSLATIONS_HI)}")
        print(f"\n    {'Source':<35s} {'BLEU':>6s}  Hypothesis")
        print(f"    {'-'*35} {'-'*6}  {'-'*40}")
        for ib in individual_bleu:
            print(f"    {ib['source']:<35s} {ib['bleu']:6.1f}  {ib['hypothesis'][:40]}")
    else:
        print("  No translations obtained — cannot compute BLEU.")

    # --- BLEU Graph ---
    indiv = results.get("indictrans_individual", results.get("google_individual", []))
    if indiv:
        engine = "IndicTrans2" if "indictrans_individual" in results else "Google Translate"
        corpus = results.get("indictrans_corpus_bleu", results.get("google_corpus_bleu", 0))

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Per-sentence BLEU
        src_labels = [ib["source"][:25] + "..." for ib in indiv]
        bleus = [ib["bleu"] for ib in indiv]
        bars = axes[0].barh(range(len(indiv)), bleus, color=COLORS[2], edgecolor="white", height=0.6)
        axes[0].set_yticks(range(len(indiv)))
        axes[0].set_yticklabels(src_labels, fontsize=9)
        axes[0].set_xlabel("BLEU Score")
        axes[0].set_title(f"Sentence-level BLEU ({engine})", fontsize=13, fontweight="bold")
        axes[0].invert_yaxis()
        for bar, val in zip(bars, bleus):
            axes[0].text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                         f"{val:.1f}", va="center", fontsize=9)

        # Summary gauge
        categories = ["Corpus\nBLEU", "Avg Sentence\nBLEU"]
        values = [corpus, statistics.mean(bleus) if bleus else 0]
        bar_colors = [COLORS[0], COLORS[4]]
        bars2 = axes[1].bar(categories, values, color=bar_colors, edgecolor="white", width=0.5)
        axes[1].set_ylim(0, max(100, max(values) * 1.3))
        axes[1].set_ylabel("BLEU Score")
        axes[1].set_title(f"Translation Quality Summary ({engine})", fontsize=13, fontweight="bold")
        for bar, val in zip(bars2, values):
            axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                         f"{val:.1f}", ha="center", fontsize=12, fontweight="bold")

        plt.tight_layout()
        plt.savefig(OUT_DIR / "translation_bleu.png", dpi=150)
        plt.close()
        print(f"\n  -> Graph saved: eval_results/translation_bleu.png")

    return results


# ===================================================================
# 4. TRANSLATION COVERAGE & LANGUAGE SUPPORT
# ===================================================================
def evaluate_translation_coverage():
    section("4. Translation Coverage")

    SUPPORTED_LANGS = [
        "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or", "ur",
        "as", "ne", "sa", "sd", "mai", "doi", "kok", "sat", "mni", "bodo", "lus",
    ]

    test_text = "National Scholarship for Students"
    lang_results = {}

    for lang in SUPPORTED_LANGS:
        try:
            resp = client.post(f"{BASE_URL}/api/v1/translate",
                               json={"text": test_text, "target_lang": lang}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                translated = data.get("translated_text", data.get("text", ""))
                success = translated and translated != test_text
                lang_results[lang] = {"status": "OK" if success else "PASSTHROUGH", "text": translated[:50]}
            else:
                lang_results[lang] = {"status": "ERROR", "text": f"HTTP {resp.status_code}"}
        except Exception as e:
            lang_results[lang] = {"status": "ERROR", "text": str(e)[:50]}

    ok = sum(1 for v in lang_results.values() if v["status"] == "OK")
    total = len(SUPPORTED_LANGS)
    coverage = ok / total * 100

    print(f"\n  Translation Coverage: {ok}/{total} ({coverage:.0f}%)")
    print(f"\n  {'Language':<10s} {'Status':<12s} {'Output'}")
    print(f"  {'-'*10} {'-'*12} {'-'*50}")
    for lang in SUPPORTED_LANGS:
        r = lang_results[lang]
        print(f"  {lang:<10s} {r['status']:<12s} {r['text']}")

    # --- Graph ---
    statuses = [lang_results[l]["status"] for l in SUPPORTED_LANGS]
    colors = ["#06d6a0" if s == "OK" else "#ffd166" if s == "PASSTHROUGH" else "#ef476f" for s in statuses]

    fig, ax = plt.subplots(figsize=(12, 5))
    x = range(len(SUPPORTED_LANGS))
    ax.bar(x, [1]*len(SUPPORTED_LANGS), color=colors, edgecolor="white", width=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(SUPPORTED_LANGS, rotation=45, ha="right", fontsize=9)
    ax.set_yticks([])
    ax.set_title(f"Language Translation Coverage ({ok}/{total} = {coverage:.0f}%)", fontsize=14, fontweight="bold")

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#06d6a0", label=f"Translated ({ok})"),
        Patch(facecolor="#ffd166", label=f"Passthrough ({sum(1 for s in statuses if s == 'PASSTHROUGH')})"),
        Patch(facecolor="#ef476f", label=f"Error ({sum(1 for s in statuses if s == 'ERROR')})"),
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "translation_coverage.png", dpi=150)
    plt.close()
    print(f"\n  -> Graph saved: eval_results/translation_coverage.png")

    return {"coverage_pct": round(coverage, 1), "ok": ok, "total": total, "per_lang": lang_results}


# ===================================================================
# 5. ENDPOINT THROUGHPUT (requests/sec)
# ===================================================================
def benchmark_throughput():
    section("5. Endpoint Throughput (req/s)")

    test_endpoints = [
        ("GET",  "/health",                   {}),
        ("GET",  "/api/v1/schemes",           {}),
        ("GET",  "/api/v1/categories",        {}),
        ("POST", "/api/v1/search",            {"query": "education"}),
        ("POST", "/api/v1/eligibility/check", {"gender": "Male", "age": 30}),
    ]

    N = 10  # requests per endpoint
    results = {}

    for method, path, body in test_endpoints:
        start = time.perf_counter()
        successes = 0
        for _ in range(N):
            try:
                if method == "GET":
                    r = client.get(f"{BASE_URL}{path}")
                else:
                    r = client.post(f"{BASE_URL}{path}", json=body)
                if r.status_code == 200:
                    successes += 1
            except Exception:
                pass
        elapsed = time.perf_counter() - start
        rps = N / elapsed if elapsed > 0 else 0
        label = f"{method} {path}"
        results[label] = {"rps": round(rps, 1), "success_rate": round(successes / N * 100, 1)}
        print(f"  {label:<45s}  {rps:6.1f} req/s  ({successes}/{N} success)")

    # --- Graph ---
    labels = [l.replace("/api/v1/", "/") for l in results.keys()]
    rps_vals = [results[k]["rps"] for k in results]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(range(len(labels)), rps_vals, color=COLORS[4], edgecolor="white", width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Requests / Second")
    ax.set_title("Endpoint Throughput", fontsize=14, fontweight="bold")
    for bar, val in zip(bars, rps_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{val:.1f}", ha="center", fontsize=10)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "throughput.png", dpi=150)
    plt.close()
    print(f"\n  -> Graph saved: eval_results/throughput.png")
    return results


# ===================================================================
# 6. ELIGIBILITY ENGINE ACCURACY
# ===================================================================
def evaluate_eligibility():
    section("6. Eligibility Engine Evaluation")

    test_profiles = [
        {"label": "Female SC student, 20, KA", "profile": {"gender": "Female", "age": 20, "state_code": "KA", "social_category": "SC", "is_student": True}},
        {"label": "Male General, 35", "profile": {"gender": "Male", "age": 35, "social_category": "General"}},
        {"label": "Female OBC, 45, BPL", "profile": {"gender": "Female", "age": 45, "social_category": "OBC", "is_bpl": True}},
        {"label": "Male ST, 25, disability", "profile": {"gender": "Male", "age": 25, "social_category": "ST", "is_disability": True}},
        {"label": "Female, 60, senior", "profile": {"gender": "Female", "age": 60}},
        {"label": "Male farmer, 40", "profile": {"gender": "Male", "age": 40, "occupation": "farmer"}},
    ]

    results = []
    for tp in test_profiles:
        try:
            resp = client.post(f"{BASE_URL}/api/v1/eligibility/check", json=tp["profile"])
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("total", 0)
                scores = [r.get("match_score", 0) for r in data.get("results", [])]
                avg_score = statistics.mean(scores) if scores else 0
                results.append({"label": tp["label"], "matched": total, "avg_score": round(avg_score, 2)})
                print(f"  {tp['label']:<35s}  {total:3d} schemes matched  (avg score: {avg_score:.2f})")
            else:
                results.append({"label": tp["label"], "matched": 0, "avg_score": 0})
                print(f"  {tp['label']:<35s}  ERROR HTTP {resp.status_code}")
        except Exception as e:
            results.append({"label": tp["label"], "matched": 0, "avg_score": 0})
            print(f"  {tp['label']:<35s}  ERROR: {e}")

    # --- Graph ---
    if results:
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        labels = [r["label"][:25] for r in results]
        matched = [r["matched"] for r in results]
        avg_scores = [r["avg_score"] for r in results]

        axes[0].barh(range(len(results)), matched, color=COLORS[5], edgecolor="white", height=0.6)
        axes[0].set_yticks(range(len(results)))
        axes[0].set_yticklabels(labels, fontsize=9)
        axes[0].set_xlabel("Schemes Matched")
        axes[0].set_title("Eligibility — Schemes Matched per Profile", fontsize=13, fontweight="bold")
        axes[0].invert_yaxis()
        for i, val in enumerate(matched):
            axes[0].text(val + 0.3, i, str(val), va="center", fontsize=10)

        axes[1].barh(range(len(results)), avg_scores, color=COLORS[6], edgecolor="white", height=0.6)
        axes[1].set_yticks(range(len(results)))
        axes[1].set_yticklabels(labels, fontsize=9)
        axes[1].set_xlabel("Average Match Score")
        axes[1].set_title("Eligibility — Avg Match Score per Profile", fontsize=13, fontweight="bold")
        axes[1].invert_yaxis()
        for i, val in enumerate(avg_scores):
            axes[1].text(val + 0.01, i, f"{val:.2f}", va="center", fontsize=10)

        plt.tight_layout()
        plt.savefig(OUT_DIR / "eligibility.png", dpi=150)
        plt.close()
        print(f"\n  -> Graph saved: eval_results/eligibility.png")

    return results


# ===================================================================
# MAIN — Run all evaluations
# ===================================================================
def main():
    print(f"\nSevanaGPT Evaluation Report")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend:   {BASE_URL}")
    print(f"IndicTrans: {INDICTRANS_URL}")

    # Verify backend is up
    try:
        r = client.get(f"{BASE_URL}/health")
        assert r.status_code == 200
        print(f"Backend:   HEALTHY")
    except Exception:
        print(f"\nERROR: Backend not reachable at {BASE_URL}. Start it first!")
        return

    all_results = {}

    all_results["api_benchmarks"] = benchmark_apis()
    all_results["search_quality_aggregate"], all_results["search_quality_per_query"] = evaluate_search()
    all_results["translation_bleu"] = evaluate_translation()
    all_results["translation_coverage"] = evaluate_translation_coverage()
    all_results["throughput"] = benchmark_throughput()
    all_results["eligibility"] = evaluate_eligibility()

    # Save JSON report
    # Clean non-serializable data
    report = json.loads(json.dumps(all_results, default=str))
    with open(OUT_DIR / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # --- SUMMARY DASHBOARD ---
    section("SUMMARY DASHBOARD")
    sq = all_results.get("search_quality_aggregate", {})
    tc = all_results.get("translation_coverage", {})
    bleu_data = all_results.get("translation_bleu", {})
    corpus_bleu = bleu_data.get("indictrans_corpus_bleu", bleu_data.get("google_corpus_bleu", "N/A"))

    print(f"""
  Search Quality:
    Precision@5:   {sq.get('precision@5', 'N/A')}
    Precision@10:  {sq.get('precision@10', 'N/A')}
    Recall@10:     {sq.get('recall@10', 'N/A')}
    MRR:           {sq.get('mrr', 'N/A')}
    F1@10:         {sq.get('f1@10', 'N/A')}

  Translation:
    Corpus BLEU:   {corpus_bleu}
    Coverage:      {tc.get('ok', '?')}/{tc.get('total', '?')} languages ({tc.get('coverage_pct', '?')}%)

  All graphs saved to: {OUT_DIR.resolve()}
  Full report saved to: eval_results/report.json
""")

    # --- Combined summary figure ---
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("SevanaGPT — Evaluation Dashboard", fontsize=18, fontweight="bold", y=0.98)

    # Quadrant 1: Search quality radar
    ax1 = axes[0][0]
    if sq:
        cats = list(sq.keys())
        vals = [sq[c] for c in cats]
        vals.append(vals[0])  # close the loop
        angles = np.linspace(0, 2 * np.pi, len(cats), endpoint=False).tolist()
        angles.append(angles[0])
        ax1.clear()
        ax1 = fig.add_subplot(2, 2, 1, polar=True)
        ax1.fill(angles, vals, color=COLORS[0], alpha=0.25)
        ax1.plot(angles, vals, color=COLORS[0], linewidth=2)
        ax1.set_xticks(angles[:-1])
        ax1.set_xticklabels([c.replace("@", "\n@") for c in cats], fontsize=8)
        ax1.set_ylim(0, 1)
        ax1.set_title("Search Quality", fontsize=13, fontweight="bold", pad=20)

    # Quadrant 2: API latency summary
    ax2 = axes[0][1]
    api = all_results.get("api_benchmarks", {})
    if api:
        ep_labels = [k.replace("/api/v1/", "/") for k in api.keys()]
        ep_vals = [api[k]["avg_ms"] for k in api]
        ep_pass = [api[k]["pass"] for k in api]
        colors2 = ["#06d6a0" if p else "#ef476f" for p in ep_pass]
        ax2.barh(range(len(ep_labels)), ep_vals, color=colors2, height=0.6)
        ax2.set_yticks(range(len(ep_labels)))
        ax2.set_yticklabels(ep_labels, fontsize=8)
        ax2.set_xlabel("ms")
        ax2.set_title("API Latency", fontsize=13, fontweight="bold")
        ax2.invert_yaxis()

    # Quadrant 3: Translation coverage
    ax3 = axes[1][0]
    if tc and "per_lang" in tc:
        langs = list(tc["per_lang"].keys())
        statuses = [tc["per_lang"][l]["status"] for l in langs]
        colors3 = ["#06d6a0" if s == "OK" else "#ffd166" if s == "PASSTHROUGH" else "#ef476f" for s in statuses]
        ax3.bar(range(len(langs)), [1]*len(langs), color=colors3, width=0.8)
        ax3.set_xticks(range(len(langs)))
        ax3.set_xticklabels(langs, rotation=45, fontsize=7)
        ax3.set_yticks([])
        ax3.set_title(f"Translation Coverage ({tc.get('coverage_pct', 0)}%)", fontsize=13, fontweight="bold")

    # Quadrant 4: Eligibility results
    ax4 = axes[1][1]
    elig = all_results.get("eligibility", [])
    if elig:
        el_labels = [e["label"][:22] for e in elig]
        el_vals = [e["matched"] for e in elig]
        ax4.barh(range(len(elig)), el_vals, color=COLORS[5], height=0.6)
        ax4.set_yticks(range(len(elig)))
        ax4.set_yticklabels(el_labels, fontsize=8)
        ax4.set_xlabel("Schemes Matched")
        ax4.set_title("Eligibility Engine", fontsize=13, fontweight="bold")
        ax4.invert_yaxis()

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(OUT_DIR / "dashboard.png", dpi=150)
    plt.close()
    print(f"  -> Dashboard saved: eval_results/dashboard.png")


if __name__ == "__main__":
    main()
