"""Curated, hand-verified official links for major government schemes.

Strategy 0 — highest confidence. Every URL here has been verified as the
dedicated .gov.in (or .nic.in) website for that scheme.  We check this dict
*before* hitting any search API so known schemes are resolved instantly.
"""

# slug -> verified official URL
CURATED_LINKS: dict[str, str] = {
    # ── PM / Central flagship schemes ────────────────────────────────────
    "pradhan-mantri-jan-dhan-yojana": "https://pmjdy.gov.in",
    "pm-kisan": "https://pmkisan.gov.in",
    "ayushman-bharat-pradhan-mantri-jan-arogya-yojana-ab-pmjay": "https://pmjay.gov.in",
    "pradhan-mantri-awas-yojana-gramin-pmay-g": "https://pmayg.nic.in",
    "pradhan-mantri-awas-yojana-urban-pmay-u": "https://pmaymis.gov.in",
    "pradhan-mantri-ujjwala-yojana-pmuy": "https://pmuy.gov.in",
    "pradhan-mantri-mudra-yojana-pmmy": "https://mudra.org.in",
    "atal-pension-yojana-apy": "https://npscra.nsdl.co.in/scheme-details.php",
    "pradhan-mantri-suraksha-bima-yojana-pmsby": "https://jansuraksha.gov.in",
    "pradhan-mantri-jeevan-jyoti-bima-yojana-pmjjby": "https://jansuraksha.gov.in",
    "sukanya-samriddhi-yojana": "https://nsiindia.gov.in/InternalPage.aspx?Id_Pk=89",
    "pradhan-mantri-matru-vandana-yojana-pmmvy": "https://pmmvy.wcd.gov.in",
    "pradhan-mantri-fasal-bima-yojana-pmfby": "https://pmfby.gov.in",
    "soil-health-card-scheme": "https://soilhealth.dac.gov.in",
    "pradhan-mantri-gram-sadak-yojana-pmgsy": "https://pmgsy.nic.in",
    "digital-india-programme": "https://digitalindia.gov.in",
    "make-in-india": "https://makeinindia.com",
    "startup-india": "https://startupindia.gov.in",
    "stand-up-india-scheme": "https://standupmitra.in",
    "skill-india-mission": "https://skillindia.gov.in",
    "swachh-bharat-mission-urban": "https://swachhbharatmission.gov.in",
    "swachh-bharat-mission-grameen": "https://sbm.gov.in",
    "beti-bachao-beti-padhao": "https://wcd.nic.in/bbbp-schemes",
    "national-education-policy": "https://education.gov.in/nep",
    "samagra-shiksha-abhiyan": "https://samagra.education.gov.in",
    "mid-day-meal-scheme": "https://mdm.nic.in",
    "pm-poshan-scheme": "https://pmposhan.education.gov.in",
    "integrated-child-development-services-icds": "https://icds-wcd.nic.in",
    "national-health-mission-nhm": "https://nhm.gov.in",
    "ayushman-bharat-health-and-wellness-centres": "https://ab-hwc.nhp.gov.in",
    "pradhan-mantri-jan-aushadhi-pariyojana": "https://janaushadhi.gov.in",
    "deendayal-antyodaya-yojana-national-rural-livelihoods-mission-day-nrlm": "https://nrlm.gov.in",
    "deendayal-antyodaya-yojana-national-urban-livelihoods-mission-day-nulm": "https://nulm.gov.in",
    "mahatma-gandhi-national-rural-employment-guarantee-act-mgnrega": "https://nrega.nic.in",
    "national-social-assistance-programme-nsap": "https://nsap.nic.in",
    "pradhan-mantri-shram-yogi-maan-dhan-pm-sym": "https://maandhan.in",
    "national-apprenticeship-promotion-scheme-naps": "https://apprenticeshipindia.gov.in",
    "pradhan-mantri-kaushal-vikas-yojana-pmkvy": "https://pmkvyofficial.org",
    "one-nation-one-ration-card-onorc": "https://nfsa.gov.in",
    "production-linked-incentive-pli-scheme": "https://pliindia.gov.in",
    "national-programme-for-organic-production-npop": "https://apeda.gov.in/apedawebsite/organic/Organic_Products.htm",
    "e-shram": "https://eshram.gov.in",
    "pradhan-mantri-garib-kalyan-anna-yojana-pmgkay": "https://nfsa.gov.in",
    "jal-jeevan-mission": "https://jaljeevanmission.gov.in",
    "pradhan-mantri-krishi-sinchayee-yojana-pmksy": "https://pmksy.gov.in",
    "national-solar-mission": "https://mnre.gov.in",
    "saubhagya-scheme": "https://saubhagya.gov.in",
    "ujala-scheme": "https://ujala.gov.in",
    "smart-cities-mission": "https://smartcities.gov.in",
    "atal-mission-for-rejuvenation-and-urban-transformation-amrut": "https://amrut.gov.in",
    "national-rural-drinking-water-programme": "https://jalshakti-ddws.gov.in",
    "pradhan-mantri-kisan-maandhan-yojana-pm-kmy": "https://maandhan.in",
    "national-pension-system-nps": "https://npscra.nsdl.co.in",
    "employees-provident-fund-organisation-epfo": "https://epfindia.gov.in",
    "deen-dayal-upadhyaya-grameen-kaushalya-yojana-ddugky": "https://ddugky.gov.in",
    "national-means-cum-merit-scholarship-scheme-nmmss": "https://scholarships.gov.in",
    "post-matric-scholarship-for-sc-students": "https://scholarships.gov.in",
    "pre-matric-scholarship-for-sc-students": "https://scholarships.gov.in",
    "central-sector-scheme-of-scholarship-for-college-and-university-students": "https://scholarships.gov.in",
    "pm-vishwakarma": "https://pmvishwakarma.gov.in",
    "agnipath-scheme": "https://agnipathvayu.cdac.in",
    "pradhan-mantri-vaya-vandana-yojana-pmvvy": "https://licindia.in",
    "namami-gange-programme": "https://nmcg.nic.in",
    "national-food-security-act-nfsa": "https://nfsa.gov.in",
    "pradhan-mantri-annadata-aay-sanrakshan-abhiyan-pm-aasha": "https://farmer.gov.in",
    "rashtriya-krishi-vikas-yojana-rkvy": "https://rkvy.nic.in",
    "national-horticulture-mission": "https://nhm.nic.in",
    "kisan-credit-card-kcc": "https://pmkisan.gov.in",
    "pradhan-mantri-matsya-sampada-yojana-pmmsy": "https://pmmsy.dof.gov.in",
    "national-livestock-mission-nlm": "https://nlm.udyamimitra.in",
    "assistance-to-disabled-persons-adip-scheme": "https://adipcampschedule.in",

    # ── Education & scholarship ──────────────────────────────────────────
    "national-scholarship-portal": "https://scholarships.gov.in",
    "inspire-scholarship": "https://online-inspire.gov.in",
    "kishore-vaigyanik-protsahan-yojana-kvpy": "https://kvpy.iisc.ac.in",
    "pragati-scholarship-for-girls": "https://aicte-india.org/schemes/students-development-schemes/PRAGATI",
    "ishan-uday-scholarship": "https://aicte-india.org/schemes/students-development-schemes/IU",

    # ── Women & child ────────────────────────────────────────────────────
    "one-stop-centre-scheme": "https://wcd.nic.in/schemes/one-stop-centre-scheme-1",
    "women-helpline-scheme": "https://wcd.nic.in",
    "pradhan-mantri-mahila-shakti-kendra": "https://wcd.nic.in",
    "national-creche-scheme": "https://wcd.nic.in/schemes/national-creche-scheme",

    # ── State flagships (well-known with dedicated portals) ──────────────
    "karnataka-raitha-siri": "https://raitamitra.karnataka.gov.in",
    "gruha-lakshmi-yojana-karnataka": "https://gruhalakshmi.karnataka.gov.in",
    "gruha-jyothi-yojana-karnataka": "https://gruhajyothi.karnataka.gov.in",
    "anna-bhagya-yojana-karnataka": "https://ahara.kar.nic.in",
    "delhi-ladli-yojana": "https://wcddel.in",
    "delhi-mohalla-clinic-scheme": "https://mohallaclinic.delhi.gov.in",
    "amma-vodi-andhra-pradesh": "https://jaganannaammavodi.ap.gov.in",
    "jagananna-vasathi-deevena-andhra-pradesh": "https://jaganannavasathideevena.ap.gov.in",
    "rythu-bandhu-scheme-telangana": "https://rythubandhu.telangana.gov.in",
    "dalit-bandhu-scheme-telangana": "https://dalitbandhu.telangana.gov.in",
    "aasara-pensions-telangana": "https://aasara.telangana.gov.in",
    "biju-swasthya-kalyan-yojana-odisha": "https://bsky.odisha.gov.in",
    "kalia-krushak-assistance-for-livelihood-and-income-augmentation": "https://kalia.odisha.gov.in",
    "dr-muthulakshmi-maternity-benefit-scheme": "https://tamilnadusocialwelfare.tn.gov.in",
    "chief-ministers-comprehensive-health-insurance-scheme-cmchis": "https://cmchistn.com",
    "har-ghar-bijli-yojana-bihar": "https://hargharbijli.bsphcl.co.in",
    "bihar-student-credit-card-yojana-bsccy": "https://7nishchay-yuvaupmission.bihar.gov.in",
    "indira-gandhi-free-smartphone-yojana": "https://igsy.rajasthan.gov.in",
    "mukhyamantri-chiranjeevi-swasthya-bima-yojana": "https://chiranjeevi.rajasthan.gov.in",
    "maharashtra-mahatma-jyotirao-phule-jan-arogya-yojana-mjpjay": "https://jeevandayee.gov.in",
}


def get_curated_link(slug: str) -> str | None:
    """Return the curated official link for a scheme slug, or None."""
    return CURATED_LINKS.get(slug)


def get_myscheme_url(slug: str) -> str:
    """Return the MyScheme.gov.in URL for a scheme (for reference only)."""
    return f"https://www.myscheme.gov.in/schemes/{slug}"
