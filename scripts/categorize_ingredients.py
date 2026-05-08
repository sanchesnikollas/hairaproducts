"""Categorize ingredients by function — foundation for Moon AI scoring.

Categories (functional taxonomy, hair-care focused):
  - surfactant_anionic    : sulfates, sulfonates (cleansing, can be drying)
  - surfactant_amphoteric : betaines (mild cleansing)
  - surfactant_nonionic   : polysorbates, glucosides (emulsifying)
  - surfactant_cationic   : quats (conditioning)
  - silicone_volatile     : cyclomethicone, dimethicone (low MW)
  - silicone_amine        : amodimethicone (curl-friendly)
  - silicone_water_soluble: PEG-modified silicones
  - silicone_insoluble    : dimethicone, phenyl trimethicone (build-up risk)
  - oil_natural           : argan, coconut, jojoba, etc.
  - oil_mineral           : petrolatum, paraffin
  - butter_natural        : shea, cocoa, mango
  - fatty_alcohol         : cetyl, stearyl, cetearyl (emollient, good)
  - alcohol_drying        : ethanol, isopropyl alcohol denat (drying)
  - humectant             : glycerin, propylene glycol, urea
  - protein               : hydrolyzed keratin, silk, wheat, collagen
  - polymer_film          : pvp, polyquaternium, acrylates (film-forming)
  - preservative          : phenoxyethanol, parabens, isothiazolinones
  - chelator              : edta, etidronate
  - antioxidant           : tocopherol, bht, bha, ascorbic acid
  - ph_adjuster           : citric acid, sodium hydroxide, lactic acid
  - fragrance             : parfum/perfume + fragrance allergens (linalool, limonene, etc.)
  - colorant              : ci numbers, dyes
  - active                : vitamins (B5, biotin), peptides, hyaluronic acid
  - solvent               : water, glycols (when not humectant role)
  - thickener             : carbomer, xanthan, cellulose derivatives
  - exfoliant             : aha, bha, salicylic acid (rare in hair)
  - other / unknown
"""
from __future__ import annotations
import argparse
import re
import sqlite3
import unicodedata

DB_PATH = "haira.db"


def normalize(name: str) -> str:
    if not name:
        return ""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return n.lower().strip()


# Rule order matters: more specific first
RULES: list[tuple[re.Pattern, str]] = [
    # FRAGRANCE (very common)
    (re.compile(r"^(parfum|perfume|fragrance|fragrancia)$"), "fragrance"),
    (re.compile(r"^(linalool|limonene|geraniol|citronellol|citral|coumarin|hexyl cinnamal|benzyl salicylate|benzyl alcohol|hydroxycitronellal|alpha-isomethyl ionone|eugenol|farnesol|cinnamal|isoeugenol|amyl cinnamal|amylcinnamyl alcohol)$"), "fragrance_allergen"),

    # COLORANT
    (re.compile(r"^ci ?\d{4,5}$"), "colorant"),
    (re.compile(r"^d&c\b|^fd&c\b"), "colorant"),
    (re.compile(r"oxido de ferro|iron oxide"), "colorant"),

    # PRESERVATIVE
    (re.compile(r"^phenoxyethanol$|^fenoxietanol$"), "preservative"),
    (re.compile(r"isothiazolinone|isotiazolinona"), "preservative"),
    (re.compile(r"^(methyl|ethyl|propyl|butyl|isobutyl)paraben$"), "preservative"),
    (re.compile(r"\b(parabeno|paraben)\b"), "preservative"),
    (re.compile(r"^(sodium benzoate|benzoato de sodio)$"), "preservative"),
    (re.compile(r"^(potassium sorbate|sorbato de potassio)$"), "preservative"),
    (re.compile(r"^(caprylyl glycol|caprililglicol)$"), "preservative"),
    (re.compile(r"^benzoic acid|^acido benzoico|^sorbic acid|^acido sorbico$"), "preservative"),
    (re.compile(r"dehydroacetic|dha\b"), "preservative"),
    (re.compile(r"\bdmdm hydantoin\b|imidazolidinyl urea|diazolidinyl"), "preservative"),
    (re.compile(r"^chlorphenesin$|^iodopropynyl"), "preservative"),

    # CHELATOR
    (re.compile(r"\bedta\b|edetato"), "chelator"),
    (re.compile(r"etidronic|etidronate|fitate|phytate"), "chelator"),

    # ANTIOXIDANT
    (re.compile(r"^bht$|^bha$"), "antioxidant"),
    (re.compile(r"^tocopher(ol|yl acetate)$|^tocoferol$|acetato de tocoferila"), "antioxidant"),
    (re.compile(r"^ascorbic acid$|^acido ascorbico$|^ascorbyl"), "antioxidant"),
    (re.compile(r"butylated hydroxy"), "antioxidant"),

    # PH ADJUSTER
    (re.compile(r"^citric acid$|^acido citrico$"), "ph_adjuster"),
    (re.compile(r"^lactic acid$|^acido lactico$"), "ph_adjuster"),
    (re.compile(r"^sodium hydroxide$|^hidroxido de sodio$"), "ph_adjuster"),
    (re.compile(r"^triethanolamine$|^trietanolamina$"), "ph_adjuster"),
    (re.compile(r"^aminomethyl propanol$|^amp$"), "ph_adjuster"),

    # SURFACTANT - anionic (sulfates)
    (re.compile(r"\bsulfate\b|\bsulfato\b"), "surfactant_anionic"),
    (re.compile(r"\bsulfonate\b|\bsulfonato\b"), "surfactant_anionic"),

    # SURFACTANT - amphoteric
    (re.compile(r"\bbetaine\b|\bbetaina\b"), "surfactant_amphoteric"),
    (re.compile(r"sultaine|hidroxisultaina"), "surfactant_amphoteric"),

    # SURFACTANT - cationic (also conditioning agent)
    (re.compile(r"\bquaternium-?\d+\b|polyquaternium-?\d+"), "polymer_cationic"),
    (re.compile(r"\bquaternio\b|polyquaternio"), "polymer_cationic"),
    (re.compile(r"cetrimonium|cetrimonio|behentrimonium|behenetrimonium|stearalkonium|cloreto de cetrimonio"), "surfactant_cationic"),

    # SILICONES
    (re.compile(r"amodimethicone|amodimeticone|amodimeticona"), "silicone_amine"),
    (re.compile(r"peg-\d+ dimethicone|peg-\d+/ppg"), "silicone_water_soluble"),
    (re.compile(r"cyclopentasiloxane|cyclomethicone|cyclohexasiloxane|ciclopentasiloxano"), "silicone_volatile"),
    (re.compile(r"dimethicone|dimeticone|dimeticona|trimethicone|phenyl trimethicone|trimetilsiloxissilicato"), "silicone_insoluble"),
    (re.compile(r"-cone$|-siloxane$|-silicone$"), "silicone_insoluble"),

    # FATTY ALCOHOLS (good)
    (re.compile(r"^cetyl alcohol$|^alcool cetilico$"), "fatty_alcohol"),
    (re.compile(r"^stearyl alcohol$|^alcool estearilico$"), "fatty_alcohol"),
    (re.compile(r"^cetearyl alcohol$|^alcool cetoestearilico$"), "fatty_alcohol"),
    (re.compile(r"^behenyl alcohol$|^myristyl alcohol$"), "fatty_alcohol"),

    # DRYING ALCOHOLS
    (re.compile(r"^alcohol$|^alcool$|^ethanol$|^etanol$|^ethyl alcohol$"), "alcohol_drying"),
    (re.compile(r"^isopropyl alcohol$|^propan-2-ol$|^alcool denat$|^alcohol denat\.?$|^sd alcohol"), "alcohol_drying"),

    # OILS - natural (specific)
    (re.compile(r"\b(argan|jojoba|coco oil|coconut|olea europaea|olive oil|abacate|avocado|ricino|castor|prunus amygdalus|sweet almond|amendoa|macadamia|abacaxi|babassu|murumuru|cupuacu|buriti|andiroba|copaiba|baobab|monoi|moringa|chia|inca inchi|rosa mosqueta|rosehip|simmondsia|ucuuba|tucuma|hortela|menta|tea tree|lavanda|alecrim|sesame|gergelim)\b"), "oil_natural"),
    (re.compile(r"\boil$|\boleo\b"), "oil_natural"),
    (re.compile(r"\bbutter$|\bmanteiga\b|^butyrospermum|cocoa butter|shea butter|cupuacu butter"), "butter_natural"),

    # MINERAL OILS / petrolatum
    (re.compile(r"^petrolatum$|^vaselina$|^paraffinum"), "oil_mineral"),
    (re.compile(r"mineral oil|oleo mineral"), "oil_mineral"),

    # HUMECTANTS
    (re.compile(r"^glycerin$|^glycerine$|^glicerina$|^glicerol$"), "humectant"),
    (re.compile(r"^propylene glycol$|^propilenoglicol$"), "humectant"),
    (re.compile(r"^butylene glycol$|^pentylene glycol$|^hexylene glycol$"), "humectant"),
    (re.compile(r"^urea$|^ureia$"), "humectant"),
    (re.compile(r"^panthenol$|^pantenol$|provitamina b5"), "humectant"),
    (re.compile(r"^sorbitol$|^xylitol$"), "humectant"),
    (re.compile(r"sodium pca|^pca\b"), "humectant"),
    (re.compile(r"^honey$|^mel\b"), "humectant"),

    # PROTEINS
    (re.compile(r"hydrolyzed|hidrolisado"), "protein"),
    (re.compile(r"\bkeratin\b|\bqueratina\b"), "protein"),
    (re.compile(r"\bcollagen\b|\bcolageno\b"), "protein"),
    (re.compile(r"\bsilk\b|\bseda\b"), "protein"),
    (re.compile(r"\bwheat\b protein|trigo proteina"), "protein"),
    (re.compile(r"\bsoy protein\b|\bsoja proteina\b"), "protein"),
    (re.compile(r"\belastin\b|\belastina\b"), "protein"),

    # ACTIVES
    (re.compile(r"hyaluronic|hialuronico|sodium hyaluronate"), "active"),
    (re.compile(r"\bbiotin\b|\bbiotina\b"), "active"),
    (re.compile(r"\bniacinamide\b|\bniacinamida\b"), "active"),
    (re.compile(r"^retinol\b|^retinyl"), "active"),
    (re.compile(r"caffeine|cafeina"), "active"),

    # POLYMERS / FILM-FORMING
    (re.compile(r"^pvp$|^polyvinylpyrrolidone$"), "polymer_film"),
    (re.compile(r"acrylate copolymer|acrylates|crospolymer|carbomer"), "polymer_film"),

    # THICKENERS
    (re.compile(r"^xanthan gum$|goma xantana"), "thickener"),
    (re.compile(r"hydroxyethylcellulose|hidroxietilcelulose|cellulose|guar"), "thickener"),
    (re.compile(r"^carbomer$|^acrylates copolymer"), "thickener"),

    # EMULSIFIERS / FATTY ESTERS (detergent-free emulsifiers)
    (re.compile(r"-glucoside$|-glucosido$"), "surfactant_nonionic"),
    (re.compile(r"^polysorbate \d+|^tween"), "surfactant_nonionic"),
    (re.compile(r"^lecithin$|^lecitina$"), "surfactant_nonionic"),
    (re.compile(r"glyceryl stearate|estearato de glicerila|peg-100 stearate"), "surfactant_nonionic"),
    (re.compile(r"caprylic/capric triglyceride|triglicerideo caprilico"), "emulsifier"),

    # MISC SOLVENTS
    (re.compile(r"^aqua$|^water$|^agua$"), "solvent"),
    (re.compile(r"^sodium chloride$|^cloreto de sodio$"), "thickener"),
    (re.compile(r"^silica$|^dioxido de silicio$"), "absorbent"),
    (re.compile(r"^talc$|^talco\b"), "absorbent"),
    (re.compile(r"^mica\b|^kaolin\b|^caulim\b"), "absorbent"),

    # === Extended rules (round 2) ===
    # Drying alcohols (broader)
    (re.compile(r"alcool etilico|ethyl alcohol|alcool etilic"), "alcohol_drying"),
    (re.compile(r"^denatured alcohol$"), "alcohol_drying"),
    # Carbonato de propileno (polar solvent)
    (re.compile(r"^propylene carbonate$|^carbonato de propileno$"), "solvent"),
    # Sodium gluconate / gliconato (chelator)
    (re.compile(r"sodium gluconate|gliconato de sodio"), "chelator"),
    # Magnesium salts (electrolytes/thickeners)
    (re.compile(r"^magnesium chloride$|^cloreto de magnesio$|^magnesium nitrate$"), "electrolyte"),
    # Ceteareth-N, Steareth-N (nonionic surfactant)
    (re.compile(r"^(cete|stea|olea|laure|cetolea|cetea)reth-?\d+"), "surfactant_nonionic"),
    # Isododecano / Isohexadecane (volatile emollients)
    (re.compile(r"^isododecane$|^isododecano$|^isohexadecane$"), "emollient_synthetic"),
    # Cocamide DEA / MEA (amides)
    (re.compile(r"cocamide (dea|mea|monoethanolamine)|cocamida"), "surfactant_nonionic"),
    # Common colorants by Portuguese name
    (re.compile(r"azul brilhante|brilliant blue"), "colorant"),
    (re.compile(r"amarelo (de )?tartrazina|tartrazine"), "colorant"),
    (re.compile(r"verde rapido|fast green"), "colorant"),
    (re.compile(r"^carmim$|carmine|cochineal"), "colorant"),
    (re.compile(r"^dioxido de titanio$|^titanium dioxide$"), "colorant"),
    # Alkyl esters (emollients)
    (re.compile(r"^c?\d+-?\d+ alkyl benzoate$|^benzoato de alquila"), "emollient_synthetic"),
    (re.compile(r"^isopropyl (myristate|palmitate)$|^palmitato de isopropila"), "emollient_synthetic"),
    (re.compile(r"^ethylhexyl (palmitate|stearate)|^etilhexil"), "emollient_synthetic"),
    # PEG polymers
    (re.compile(r"^peg-?\d+(\.|m|h)?$"), "polymer_film"),
    (re.compile(r"^peg-?\d+ "), "surfactant_nonionic"),
    # Polyquaternium prefix (already caught polyquaternium-N, but generic)
    (re.compile(r"^polyquaternium\b"), "polymer_cationic"),
    # Sodium hyaluronate / acid forms
    (re.compile(r"^pca\b"), "humectant"),
    # Sucrose, glucose
    (re.compile(r"^sucrose$|^sacarose$|^glucose$|^glicose$"), "humectant"),
    # Sodium lactate
    (re.compile(r"^sodium lactate$|^lactato de sodio$"), "humectant"),
    # Allantoin
    (re.compile(r"^allantoin$|^alantoina$"), "active"),
    # Salicylic acid
    (re.compile(r"^salicylic acid$|^acido salicilico$"), "exfoliant"),
    # Glycolic / lactic / mandelic acids (AHAs)
    (re.compile(r"^glycolic acid$|^acido glicolico$|^mandelic"), "exfoliant"),
    # Niacinamide / ascorbic — already caught above; add more vitamins
    (re.compile(r"^vitamin e\b|^vitamina e\b"), "antioxidant"),
    (re.compile(r"^vitamin c\b|^vitamina c\b"), "antioxidant"),
    (re.compile(r"^vitamin a\b|^vitamina a\b"), "active"),
    # Caffeine, etc
    (re.compile(r"^kojic\b|^arbutin\b"), "active"),
    # Specific extracts (oil_natural extension)
    (re.compile(r"\b(extract|extrato)\b"), "extract_botanical"),
    # Fatty acids
    (re.compile(r"^stearic acid$|^acido estearico$|^palmitic acid$|^acido palmitico$|^myristic acid$|^lauric acid$|^oleic acid$|^acido oleico$"), "fatty_acid"),
    # Cetearyl glucoside (eco surfactant)
    (re.compile(r"cetearyl glucoside|coco-glucoside|decyl glucoside|lauryl glucoside"), "surfactant_nonionic"),
    # Sorbitan esters (emulsifier)
    (re.compile(r"^sorbitan (oleate|stearate|laurate|sesquioleate)"), "surfactant_nonionic"),
    # Diatomaceous earth, zeolite
    (re.compile(r"^diatomaceous|^zeolite$"), "absorbent"),
]


def categorize(name: str) -> str | None:
    n = normalize(name)
    if not n:
        return None
    for pat, cat in RULES:
        if pat.search(n):
            return cat
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.apply and not args.dry_run:
        print("Pass --dry-run or --apply")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rows = list(c.execute("""
        SELECT i.id, i.canonical_name, COUNT(pi.id) as usage
        FROM ingredients i
        LEFT JOIN product_ingredients pi ON pi.ingredient_id = i.id
        GROUP BY i.id
    """))
    print(f"Total ingredients: {len(rows)}")

    categorized: dict[str, int] = {}
    uncategorized = 0
    uncat_top = []
    updates = []
    for r in rows:
        cat = categorize(r["canonical_name"])
        if cat:
            categorized[cat] = categorized.get(cat, 0) + 1
            updates.append((cat, r["id"]))
        else:
            uncategorized += 1
            uncat_top.append((r["canonical_name"], r["usage"]))

    total = len(rows)
    print(f"\nCategorized: {len(updates)} ({100*len(updates)/total:.1f}%)")
    print(f"Uncategorized: {uncategorized} ({100*uncategorized/total:.1f}%)")

    print("\nBy category:")
    for cat, n in sorted(categorized.items(), key=lambda x: -x[1]):
        print(f"  {cat:<30} {n:>5}")

    print("\nTop 15 uncategorized (by usage):")
    uncat_top.sort(key=lambda x: -x[1])
    for name, usage in uncat_top[:15]:
        print(f"  {usage:>5}  {name}")

    if args.dry_run:
        return

    # Apply categorization
    for cat, ing_id in updates:
        c.execute("UPDATE ingredients SET category = ? WHERE id = ?", (cat, ing_id))
    conn.commit()
    conn.close()
    print(f"\n✅ Updated {len(updates)} ingredient categories")


if __name__ == "__main__":
    main()
