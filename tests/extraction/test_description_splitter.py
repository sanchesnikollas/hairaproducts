from src.extraction.description_splitter import split_description_blob


class TestSplitDescriptionBlob:
    def test_splits_usage_and_composition_out_of_description(self):
        blob = (
            "Shampoo nutritivo para cabelos secos e danificados, com óleo de argan. "
            "Modo de uso: Aplique no cabelo úmido, massageie e enxágue. "
            "Composição: Aqua, Sodium Laureth Sulfate, Glycerin, Parfum."
        )
        r = split_description_blob(blob)
        assert r["description"].startswith("Shampoo nutritivo")
        assert "Modo de uso" not in r["description"]
        assert r["care_usage"].startswith("Aplique no cabelo")
        assert r["composition"].startswith("Aqua")

    def test_newline_headers(self):
        blob = (
            "Creme para pentear.\n"
            "Modo de uso: Aplique mecha a mecha.\n"
            "Ingredientes: Aqua, Cetearyl Alcohol, Behentrimonium Chloride."
        )
        r = split_description_blob(blob)
        assert r["care_usage"].startswith("Aplique mecha")
        assert r["ingredients_inci"].startswith("Aqua")

    def test_no_markers_returns_empty(self):
        assert split_description_blob("Um shampoo incrível para todos os tipos de cabelo.") == {}

    def test_marketing_use_phrase_is_not_a_false_marker(self):
        # "como usar" appears in prose without a separator -> must NOT split
        assert split_description_blob("Aprenda como usar o produto no dia a dia.") == {}

    def test_care_and_benefits(self):
        r = split_description_blob("Como usar: Aplique. Benefícios: Brilho e maciez.")
        assert r["care_usage"] == "Aplique"
        assert r["benefits"] == "Brilho e maciez."

    def test_none_and_empty(self):
        assert split_description_blob(None) == {}
        assert split_description_blob("") == {}
