"""Validacoes de campos que precisam de mais do que limites de tamanho."""
import re


def validate_cnpj(value: str) -> str:
    """Valida os dois digitos e devolve o CNPJ sem mascara e em maiusculas."""
    value = value.strip()
    # Aceita somente a mascara completa ou os 14 caracteres sem pontuacao.
    pattern = r"(?:[A-Za-z0-9]{12}[0-9]{2}|[A-Za-z0-9]{2}\.[A-Za-z0-9]{3}\.[A-Za-z0-9]{3}/[A-Za-z0-9]{4}-[0-9]{2})"
    if not re.fullmatch(pattern, value):
        raise ValueError("CNPJ deve conter 14 caracteres, com ou sem a mascara padrao.")
    cnpj = value.translate(str.maketrans("", "", "./-")).upper()
    if len(set(cnpj)) == 1:
        raise ValueError("CNPJ invalido.")

    base = cnpj[:12]
    for weights in ((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2),
                    (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)):
        # ASCII - 48 tambem funciona para CNPJs numericos (ex.: '0' vira 0).
        total = sum((ord(char) - 48) * weight for char, weight in zip(base, weights))
        remainder = total % 11
        base += str(0 if remainder < 2 else 11 - remainder)
    if base != cnpj:
        raise ValueError("Digitos verificadores do CNPJ invalidos.")
    return cnpj


def validate_phone(value: str) -> str:
    """Preserva a formatacao; exige 8 a 15 digitos e pontuacao telefonica comum."""
    if not re.fullmatch(r"\+?[0-9() .-]+", value):
        raise ValueError("Telefone deve conter numeros e pontuacao telefonica valida.")
    digits = re.sub(r"[^0-9]", "", value)
    if not 8 <= len(digits) <= 15:
        raise ValueError("Telefone deve conter entre 8 e 15 digitos.")
    return value
