"""
SevanaGPT Translation BLEU Score Evaluation & Graph
=====================================================
Evaluates translation quality against human-reference translations
across multiple Indian languages.
Tries IndicTrans2 first; falls back to backend translate endpoint.
Produces detailed per-sentence and per-language BLEU graphs.

Usage:
    cd backend
    python eval_indictrans_bleu.py
"""

import json
import statistics
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
import sacrebleu
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
INDICTRANS_URL = "http://localhost:7860"
BACKEND_URL = "http://localhost:8000"
OUT_DIR = Path(__file__).parent / "eval_results"
OUT_DIR.mkdir(exist_ok=True)

client = httpx.Client(timeout=30.0)

# Determine which translation engine is available
ENGINE = "unknown"

COLORS = ["#4361ee", "#3a0ca3", "#7209b7", "#f72585", "#4cc9f0",
          "#06d6a0", "#ffd166", "#ef476f", "#118ab2", "#073b4c"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "#f8f9fa",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
})

# ---------------------------------------------------------------------------
# Reference translations: (English source, {lang: reference})
# These are human-verified reference translations for BLEU evaluation.
# ---------------------------------------------------------------------------
REFERENCE_DATA = [
    {
        "en": "National Scholarship for Students",
        "hi": "छात्रों के लिए राष्ट्रीय छात्रवृत्ति",
        "bn": "ছাত্রদের জন্য জাতীয় বৃত্তি",
        "ta": "மாணவர்களுக்கான தேசிய உதவித்தொகை",
        "te": "విద్యార్థులకు జాతీయ స్కాలర్‌షిప్",
        "mr": "विद्यार्थ्यांसाठी राष्ट्रीय शिष्यवृत्ती",
        "gu": "વિદ્યાર્થીઓ માટે રાષ્ટ્રીય શિષ્યવૃત્તિ",
    },
    {
        "en": "Women Empowerment Programme",
        "hi": "महिला सशक्तिकरण कार्यक्रम",
        "bn": "নারী ক্ষমতায়ন কর্মসূচি",
        "ta": "பெண்கள் அதிகாரமளிக்கும் திட்டம்",
        "te": "మహిళా సాధికారత కార్యక్రమం",
        "mr": "महिला सशक्तिकरण कार्यक्रम",
        "gu": "મહિલા સશક્તિકરણ કાર્યક્રમ",
    },
    {
        "en": "Housing for All",
        "hi": "सबके लिए आवास",
        "bn": "সকলের জন্য আবাসন",
        "ta": "அனைவருக்கும் வீடு",
        "te": "అందరికీ ఇళ్ళు",
        "mr": "सर्वांसाठी घरे",
        "gu": "બધા માટે આવાસ",
    },
    {
        "en": "Farmer Income Support Scheme",
        "hi": "किसान आय सहायता योजना",
        "bn": "কৃষক আয় সহায়তা প্রকল্প",
        "ta": "விவசாயிகள் வருமான உதவித் திட்டம்",
        "te": "రైతు ఆదాయ సహాయ పథకం",
        "mr": "शेतकरी उत्पन्न सहाय्य योजना",
        "gu": "ખેડૂત આવક સહાય યોજના",
    },
    {
        "en": "Health Insurance Scheme",
        "hi": "स्वास्थ्य बीमा योजना",
        "bn": "স্বাস্থ্য বীমা প্রকল্প",
        "ta": "சுகாதார காப்பீட்டுத் திட்டம்",
        "te": "ఆరోగ్య బీమా పథకం",
        "mr": "आरोग्य विमा योजना",
        "gu": "આરોગ્ય વીમા યોજના",
    },
    {
        "en": "Digital India Programme",
        "hi": "डिजिटल भारत कार्यक्रम",
        "bn": "ডিজিটাল ভারত কর্মসূচি",
        "ta": "டிஜிட்டல் இந்தியா திட்டம்",
        "te": "డిజిటల్ ఇండియా కార్యక్రమం",
        "mr": "डिजिटल भारत कार्यक्रम",
        "gu": "ડિજિટલ ભારત કાર્યક્રમ",
    },
    {
        "en": "Clean Water Mission",
        "hi": "स्वच्छ जल मिशन",
        "bn": "পরিষ্কার জল মিশন",
        "ta": "சுத்தமான நீர் இயக்கம்",
        "te": "స్వచ్ఛ జల మిషన్",
        "mr": "स्वच्छ जल मिशन",
        "gu": "સ્વચ્છ જળ મિશન",
    },
    {
        "en": "Rural Employment Guarantee",
        "hi": "ग्रामीण रोजगार गारंटी",
        "bn": "গ্রামীণ কর্মসংস্থান গ্যারান্টি",
        "ta": "கிராமப்புற வேலைவாய்ப்பு உத்தரவாதம்",
        "te": "గ్రామీణ ఉపాధి హామీ",
        "mr": "ग्रामीण रोजगार हमी",
        "gu": "ગ્રામીણ રોજગાર ગેરંટી",
    },
    {
        "en": "Pradhan Mantri Awas Yojana provides affordable housing to urban poor",
        "hi": "प्रधानमंत्री आवास योजना शहरी गरीबों को सस्ते आवास प्रदान करती है",
        "bn": "প্রধানমন্ত্রী আবাস যোজনা শহরের দরিদ্রদের সাশ্রয়ী মূল্যে আবাসন প্রদান করে",
        "ta": "பிரதமர் வீட்டுத்திட்டம் நகர்ப்புற ஏழைகளுக்கு மலிவு வீடு வழங்குகிறது",
        "te": "ప్రధాన మంత్రి ఆవాస్ యోజన పట్టణ పేదలకు సరసమైన గృహాలను అందిస్తుంది",
        "mr": "प्रधानमंत्री आवास योजना शहरी गरिबांना परवडणारी घरे पुरवते",
        "gu": "પ્રધાનમંત્રી આવાસ યોજના શહેરી ગરીબોને સસ્તા આવાસ પૂરા પાડે છે",
    },
    {
        "en": "The government launched a new scheme for skill development of youth",
        "hi": "सरकार ने युवाओं के कौशल विकास के लिए एक नई योजना शुरू की",
        "bn": "সরকার যুবকদের দক্ষতা উন্নয়নের জন্য একটি নতুন প্রকল্প চালু করেছে",
        "ta": "இளைஞர்களின் திறன் மேம்பாட்டிற்காக அரசு புதிய திட்டம் தொடங்கியது",
        "te": "ప్రభుత్వం యువత నైపుణ్య అభివృద్ధి కోసం కొత్త పథకాన్ని ప్రారంభించింది",
        "mr": "सरकारने तरुणांच्या कौशल्य विकासासाठी नवीन योजना सुरू केली",
        "gu": "સરકારે યુવાનોના કૌશલ્ય વિકાસ માટે નવી યોજના શરૂ કરી",
    },
    {
        "en": "Free education for children below fourteen years of age",
        "hi": "चौदह वर्ष से कम आयु के बच्चों के लिए मुफ्त शिक्षा",
        "bn": "চৌদ্দ বছরের কম বয়সী শিশুদের জন্য বিনামূল্যে শিক্ষা",
        "ta": "பதினான்கு வயதுக்குட்பட்ட குழந்தைகளுக்கு இலவச கல்வி",
        "te": "పద్నాలుగు సంవత్సరాల కంటే తక్కువ వయస్సు గల పిల్లలకు ఉచిత విద్య",
        "mr": "चौदा वर्षांखालील मुलांना मोफत शिक्षण",
        "gu": "ચૌદ વર્ષથી ઓછી ઉંમરના બાળકો માટે મફત શિક્ષણ",
    },
    {
        "en": "Financial assistance for below poverty line families",
        "hi": "गरीबी रेखा से नीचे के परिवारों के लिए आर्थिक सहायता",
        "bn": "দারিদ্র্যসীমার নীচে পরিবারগুলির জন্য আর্থিক সহায়তা",
        "ta": "வறுமைக் கோட்டிற்குக் கீழே உள்ள குடும்பங்களுக்கு நிதி உதவி",
        "te": "దారిద్ర్య రేఖకు దిగువన ఉన్న కుటుంబాలకు ఆర్థిక సహాయం",
        "mr": "दारिद्र्यरेषेखालील कुटुंबांना आर्थिक मदत",
        "gu": "ગરીબી રેખા નીચેના પરિવારો માટે આર્થિક સહાય",
    },
]

LANG_NAMES = {
    "hi": "Hindi", "bn": "Bengali", "ta": "Tamil",
    "te": "Telugu", "mr": "Marathi", "gu": "Gujarati",
}
TARGET_LANGS = ["hi", "bn", "ta", "te", "mr", "gu"]


def _detect_engine() -> str:
    """Detect which translation engine is available."""
    # Try IndicTrans2 first
    try:
        r = client.get(f"{INDICTRANS_URL}/health", timeout=5)
        info = r.json()
        if info.get("ready"):
            # Smoke test an actual translation
            r2 = client.post(f"{INDICTRANS_URL}/translate",
                             json={"text": "hello", "source_lang": "en", "target_lang": "hi"}, timeout=10)
            if r2.status_code == 200:
                return "indictrans"
    except Exception:
        pass
    # Fall back to backend translate endpoint
    try:
        r = client.post(f"{BACKEND_URL}/api/v1/translate",
                        json={"text": "hello", "target_lang": "hi"}, timeout=10)
        if r.status_code == 200:
            translated = r.json().get("translated_text", "")
            if translated and translated != "hello":
                return "backend"
    except Exception:
        pass
    return "none"


def translate(text: str, target_lang: str, engine: str) -> str | None:
    """Translate text using the detected engine."""
    try:
        if engine == "indictrans":
            resp = client.post(f"{INDICTRANS_URL}/translate", json={
                "text": text, "source_lang": "en", "target_lang": target_lang
            }, timeout=15)
            if resp.status_code == 200:
                return resp.json().get("translated_text", "")
        else:
            resp = client.post(f"{BACKEND_URL}/api/v1/translate", json={
                "text": text, "target_lang": target_lang
            }, timeout=15)
            if resp.status_code == 200:
                return resp.json().get("translated_text", resp.json().get("text", ""))
    except Exception as e:
        print(f"    Error: {e}")
    return None


def main():
    print("=" * 65)
    print("  Translation BLEU Score Evaluation")
    print("=" * 65)

    engine = _detect_engine()
    if engine == "indictrans":
        r = client.get(f"{INDICTRANS_URL}/health")
        info = r.json()
        engine_label = "IndicTrans2"
        print(f"  Engine: IndicTrans2")
        print(f"  Model:  {info.get('model')}")
        print(f"  Device: {info.get('device')}")
    elif engine == "backend":
        engine_label = "Backend Translate (Google Translate)"
        print(f"  Engine: {engine_label}")
    else:
        print(f"\n  ERROR: No translation engine available.")
        return
    print(f"  Status: READY\n")

    # ---- Evaluate per-language ----
    lang_results = {}   # lang -> {corpus_bleu, avg_sentence_bleu, individual: [...]}

    for lang in TARGET_LANGS:
        hypotheses = []
        references = []
        individual = []

        for item in REFERENCE_DATA:
            ref = item.get(lang)
            if not ref:
                continue

            start = time.perf_counter()
            hyp = translate(item["en"], lang, engine)
            elapsed = time.perf_counter() - start

            if hyp:
                hypotheses.append(hyp)
                references.append(ref)
                s_bleu = sacrebleu.sentence_bleu(hyp, [ref])
                individual.append({
                    "source": item["en"],
                    "reference": ref,
                    "hypothesis": hyp,
                    "bleu": round(s_bleu.score, 2),
                    "time_ms": round(elapsed * 1000, 1),
                })

        if hypotheses:
            corpus = sacrebleu.corpus_bleu(hypotheses, [references])
            avg_sent = statistics.mean([i["bleu"] for i in individual])
            lang_results[lang] = {
                "corpus_bleu": round(corpus.score, 2),
                "brevity_penalty": round(corpus.bp, 4),
                "avg_sentence_bleu": round(avg_sent, 2),
                "sentences": len(hypotheses),
                "individual": individual,
            }

    # ---- Print results ----
    print(f"\n  {'Language':<12s} {'Corpus BLEU':>12s} {'Avg Sent BLEU':>14s} {'BP':>8s} {'Sentences':>10s}")
    print(f"  {'-'*12} {'-'*12} {'-'*14} {'-'*8} {'-'*10}")
    for lang in TARGET_LANGS:
        if lang not in lang_results:
            continue
        lr = lang_results[lang]
        print(f"  {LANG_NAMES[lang]:<12s} {lr['corpus_bleu']:12.2f} {lr['avg_sentence_bleu']:14.2f} {lr['brevity_penalty']:8.4f} {lr['sentences']:10d}")

    overall_corpus = statistics.mean([lr["corpus_bleu"] for lr in lang_results.values()])
    overall_sent = statistics.mean([lr["avg_sentence_bleu"] for lr in lang_results.values()])
    print(f"  {'-'*12} {'-'*12} {'-'*14} {'-'*8} {'-'*10}")
    print(f"  {'OVERALL':<12s} {overall_corpus:12.2f} {overall_sent:14.2f}")

    # Print per-sentence details for Hindi
    print(f"\n  Per-Sentence Detail (Hindi):")
    print(f"  {'Source':<55s} {'BLEU':>6s}  {'Hypothesis'}")
    print(f"  {'-'*55} {'-'*6}  {'-'*45}")
    for ib in lang_results.get("hi", {}).get("individual", []):
        print(f"  {ib['source'][:55]:<55s} {ib['bleu']:6.1f}  {ib['hypothesis'][:45]}")

    # ================================================================
    #  GRAPH 1: Per-Language Corpus BLEU (main bar chart)
    # ================================================================
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.suptitle(f"{engine_label} — BLEU Score Evaluation", fontsize=16, fontweight="bold", y=1.02)

    # -- Panel 1: Corpus BLEU per language --
    langs = [l for l in TARGET_LANGS if l in lang_results]
    lang_labels = [LANG_NAMES[l] for l in langs]
    corpus_bleus = [lang_results[l]["corpus_bleu"] for l in langs]
    avg_sent_bleus = [lang_results[l]["avg_sentence_bleu"] for l in langs]

    x = np.arange(len(langs))
    w = 0.35
    bars1 = axes[0].bar(x - w/2, corpus_bleus, w, label="Corpus BLEU", color=COLORS[0], edgecolor="white")
    bars2 = axes[0].bar(x + w/2, avg_sent_bleus, w, label="Avg Sentence BLEU", color=COLORS[4], edgecolor="white")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(lang_labels, fontsize=10)
    axes[0].set_ylim(0, 105)
    axes[0].set_ylabel("BLEU Score")
    axes[0].set_title("BLEU by Language", fontsize=13, fontweight="bold")
    axes[0].legend(fontsize=9, loc="lower right")
    for bar, val in zip(bars1, corpus_bleus):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f"{val:.1f}", ha="center", fontsize=9, fontweight="bold")
    for bar, val in zip(bars2, avg_sent_bleus):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f"{val:.1f}", ha="center", fontsize=8)

    # -- Panel 2: Per-sentence BLEU heatmap (Hindi) --
    hi_indiv = lang_results.get("hi", {}).get("individual", [])
    if hi_indiv:
        src_labels = [ib["source"][:30] + "..." if len(ib["source"]) > 30 else ib["source"] for ib in hi_indiv]
        bleus = [ib["bleu"] for ib in hi_indiv]
        bar_colors = ["#06d6a0" if b >= 50 else "#ffd166" if b >= 25 else "#ef476f" for b in bleus]
        bars3 = axes[1].barh(range(len(hi_indiv)), bleus, color=bar_colors, edgecolor="white", height=0.65)
        axes[1].set_yticks(range(len(hi_indiv)))
        axes[1].set_yticklabels(src_labels, fontsize=8)
        axes[1].set_xlabel("BLEU Score")
        axes[1].set_xlim(0, 110)
        axes[1].set_title("Per-Sentence BLEU (Hindi)", fontsize=13, fontweight="bold")
        axes[1].invert_yaxis()
        for bar, val in zip(bars3, bleus):
            axes[1].text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                         f"{val:.1f}", va="center", fontsize=9)

    # -- Panel 3: Overall summary gauge --
    summary_labels = ["Overall\nCorpus BLEU", "Overall\nAvg Sent BLEU"]
    summary_vals = [overall_corpus, overall_sent]
    bar_colors_s = [COLORS[0], COLORS[4]]
    bars4 = axes[2].bar(summary_labels, summary_vals, color=bar_colors_s, edgecolor="white", width=0.5)
    axes[2].set_ylim(0, 105)
    axes[2].set_ylabel("BLEU Score")
    axes[2].set_title(f"Overall {engine_label} Quality", fontsize=13, fontweight="bold")
    for bar, val in zip(bars4, summary_vals):
        axes[2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.5,
                     f"{val:.1f}", ha="center", fontsize=14, fontweight="bold")

    # Quality threshold lines
    for ax in [axes[0], axes[2]]:
        ax.axhline(y=50, color="#ef476f", linestyle="--", alpha=0.5, linewidth=1)
        ax.axhline(y=75, color="#ffd166", linestyle="--", alpha=0.5, linewidth=1)
    axes[1].axvline(x=50, color="#ef476f", linestyle="--", alpha=0.5, linewidth=1)
    axes[1].axvline(x=75, color="#ffd166", linestyle="--", alpha=0.5, linewidth=1)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "indictrans_bleu.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  -> Graph saved: eval_results/indictrans_bleu.png")

    # ================================================================
    #  GRAPH 2: Detailed heatmap — all languages x all sentences
    # ================================================================
    fig2, ax2 = plt.subplots(figsize=(14, 8))

    sentence_labels = [item["en"][:40] + ("..." if len(item["en"]) > 40 else "") for item in REFERENCE_DATA]
    heatmap_data = []
    for lang in langs:
        row = []
        indiv = lang_results[lang]["individual"]
        indiv_map = {ib["source"]: ib["bleu"] for ib in indiv}
        for item in REFERENCE_DATA:
            row.append(indiv_map.get(item["en"], 0))
        heatmap_data.append(row)

    heatmap_arr = np.array(heatmap_data)
    im = ax2.imshow(heatmap_arr, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)

    ax2.set_xticks(range(len(sentence_labels)))
    ax2.set_xticklabels(sentence_labels, rotation=40, ha="right", fontsize=8)
    ax2.set_yticks(range(len(langs)))
    ax2.set_yticklabels([LANG_NAMES[l] for l in langs], fontsize=10)
    ax2.set_title(f"{engine_label} — Sentence-level BLEU Heatmap (All Languages)", fontsize=14, fontweight="bold")

    # Annotate cells
    for i in range(len(langs)):
        for j in range(len(REFERENCE_DATA)):
            val = heatmap_arr[i, j]
            text_color = "white" if val < 40 else "black"
            ax2.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=8, color=text_color, fontweight="bold")

    cbar = fig2.colorbar(im, ax=ax2, shrink=0.8, label="BLEU Score")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "indictrans_bleu_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  -> Graph saved: eval_results/indictrans_bleu_heatmap.png")

    # Save JSON
    report = {
        "engine": engine_label,
        "overall_corpus_bleu": round(overall_corpus, 2),
        "overall_avg_sentence_bleu": round(overall_sent, 2),
        "per_language": {l: {k: v for k, v in lr.items() if k != "individual"} for l, lr in lang_results.items()},
        "per_language_detail": lang_results,
    }
    with open(OUT_DIR / "indictrans_bleu_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  -> Report saved: eval_results/indictrans_bleu_report.json")


if __name__ == "__main__":
    main()
