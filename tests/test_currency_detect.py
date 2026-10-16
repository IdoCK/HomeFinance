from modules import agent_parser as ap


def test_shekel_symbol_detected():
    assert ap._detect_currency("₪400.00", "SUPERMARKET", None) == ("ILS", "cell_symbol")

def test_iso_code_in_cell():
    assert ap._detect_currency("400 ILS", "x", None) == ("ILS", "cell_code")

def test_dollar_symbol_detected():
    assert ap._detect_currency("$1,234.50", "x", None) == ("USD", "cell_symbol")

def test_file_default_used_when_no_signal():
    assert ap._detect_currency("400.00", "x", "ILS") == ("ILS", "file_default")

def test_person_default_usd_when_nothing():
    assert ap._detect_currency("400.00", "x", None) == ("USD", "person_default")
