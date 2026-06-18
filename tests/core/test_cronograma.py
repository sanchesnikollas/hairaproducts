from src.core.cronograma import derive_routine_role


class TestDeriveRoutineRole:
    def test_sulfate_is_intensa(self):
        r = derive_routine_role(["Aqua", "Sodium Lauryl Sulfate", "Cocamidopropyl Betaine"], "limpar")
        assert r["cleansing_strength"] == "intensa"
        assert r["step"] == "lavar"

    def test_mild_surfactant_is_suave(self):
        r = derive_routine_role(["Aqua", "Coco Glucoside", "Sodium Cocoyl Isethionate"], "limpar")
        assert r["cleansing_strength"] == "suave"

    def test_no_surfactant_none(self):
        r = derive_routine_role(["Aqua", "Cetearyl Alcohol", "Glycerin"], "hidratar")
        assert r["cleansing_strength"] is None
        assert r["step"] == "tratar"

    def test_insoluble_silicone_flagged(self):
        r = derive_routine_role(["Aqua", "Dimethicone", "Amodimethicone"], "condicionar")
        assert r["has_insoluble_silicone"] is True
        assert r["step"] == "condicionar"

    def test_water_soluble_silicone_not_flagged(self):
        r = derive_routine_role(["Aqua", "PEG-12 Dimethicone"], None)
        assert r["has_insoluble_silicone"] is False

    def test_drying_alcohol_flagged(self):
        r = derive_routine_role(["Aqua", "Alcohol Denat.", "Cetyl Alcohol"], "finalizar")
        assert r["has_drying_alcohol"] is True
        assert r["step"] == "finalizar"

    def test_function_steps(self):
        assert derive_routine_role([], "definir")["step"] == "finalizar"
        assert derive_routine_role([], "colorir")["step"] == "transformar"
        assert derive_routine_role([], "reconstruir")["step"] == "tratar"
        assert derive_routine_role([], None)["step"] is None

    def test_empty_inci_safe(self):
        r = derive_routine_role(None, "limpar")
        assert r == {"step": "lavar", "cleansing_strength": None,
                     "has_insoluble_silicone": False, "has_drying_alcohol": False}
