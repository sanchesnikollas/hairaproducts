from src.core.allergen_detector import allergen_summary, detect_allergens


class TestDetectAllergens:
    def test_detects_eu26_fragrance_allergens(self):
        inci = ["Aqua", "Glycerin", "Parfum", "Limonene", "Linalool", "Citronellol"]
        found = detect_allergens(inci)
        classes = {a["allergen_class"] for a in found}
        ingredients = {a["ingredient"] for a in found}
        assert classes == {"fragrance_allergen"}
        assert {"Limonene", "Linalool", "Citronellol"} <= ingredients

    def test_detects_pt_spellings(self):
        found = detect_allergens(["Água", "Linalol", "Limoneno"])
        assert len(found) == 2
        assert all(a["allergen_class"] == "fragrance_allergen" for a in found)

    def test_drying_alcohol_exact_match_only(self):
        # "Alcohol" (drying) is flagged; "Cetyl Alcohol" (fatty) is NOT
        found = detect_allergens(["Alcohol Denat.", "Cetyl Alcohol", "Cetearyl Alcohol"])
        flagged = {a["ingredient"] for a in found}
        assert "Alcohol Denat." in flagged
        assert "Cetyl Alcohol" not in flagged
        assert "Cetearyl Alcohol" not in flagged

    def test_high_severity_isothiazolinone_and_formaldehyde(self):
        found = detect_allergens(["Methylisothiazolinone", "DMDM Hydantoin"])
        sev = {a["allergen_class"]: a["severity"] for a in found}
        assert sev["mci_mit_preservative"] == "high"
        assert sev["formaldehyde_releaser"] == "high"

    def test_sulfate_flagged_as_caution(self):
        found = detect_allergens(["Sodium Laureth Sulfate"])
        assert found and found[0]["allergen_class"] == "sulfate_harsh"
        assert found[0]["severity"] == "caution"

    def test_clean_list_returns_empty(self):
        assert detect_allergens(["Aqua", "Glycerin", "Cetearyl Alcohol", "Behentrimonium Chloride"]) == []

    def test_none_and_empty(self):
        assert detect_allergens(None) == []
        assert detect_allergens([]) == []


class TestAllergenSummary:
    def test_summary_worst_severity_and_classes(self):
        s = allergen_summary(["Limonene", "Sodium Lauryl Sulfate", "Methylisothiazolinone"])
        assert s["count"] == 3
        assert s["worst_severity"] == "high"
        assert set(s["classes"]) == {"fragrance_allergen", "sulfate_harsh", "mci_mit_preservative"}

    def test_summary_empty(self):
        s = allergen_summary(["Aqua", "Glycerin"])
        assert s == {"count": 0, "worst_severity": None, "classes": [], "items": []}
