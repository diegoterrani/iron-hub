"""Synthetic Brazilian identity generator for account factory.

Produces plausible names, emails, phone numbers, CPFs, and addresses
suitable for bulk registration against Brazilian iGaming platforms.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Data pools (Brazilian)
# ---------------------------------------------------------------------------

FIRST_NAMES_M = [
    "João", "Pedro", "Lucas", "Mateus", "Gabriel", "Rafael", "Bruno", "Felipe",
    "Diego", "Carlos", "André", "Marcelo", "Renato", "Thiago", "Vinícius",
    "Gustavo", "Rodrigo", "Alexandre", "Eduardo", "Fábio", "Ricardo", "Paulo",
    "Sérgio", "Marcos", "Daniel", "Ailton", "Jorge", "Vitor", "Henrique", "Otávio",
]

FIRST_NAMES_F = [
    "Maria", "Ana", "Julia", "Larissa", "Camila", "Fernanda", "Patrícia", "Carla",
    "Amanda", "Larissa", "Bianca", "Aline", "Sofia", "Isabela", "Mariana",
    "Renata", "Vanessa", "Adriana", "Cláudia", "Simone", "Rosana", "Tatiane",
    "Débora", "Elaine", "Sandra", "Mônica", "Regina", "Flávia", "Gisele", "Yasmin",
]

LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves",
    "Pereira", "Lima", "Gomes", "Costa", "Martins", "Araújo", "Ribeiro", "Carvalho",
    "Rocha", "Barbosa", "Nascimento", "Moreira", "Mendes", "Freitas", "Azevedo",
    "Gonçalves", "Correia", "Teixeira", "Cardoso", "Castro", "Dias", "Moura", "Farias",
    "Vieira", "Cavalcanti", "Monteiro", "Pinto", "Campos", "Machado", "Ramos",
    "Sales", "Andrade", "Farias", "Nunes", "Melo", "Rocha", "Dias", "Peixoto",
]

# DDD ranges: (ddd, state)
DDD_STATE = [
    (11, "SP"), (12, "SP"), (13, "SP"), (14, "SP"), (15, "SP"),
    (16, "SP"), (17, "SP"), (18, "SP"), (19, "SP"), (34, "MG"),
    (31, "MG"), (32, "MG"), (33, "MG"), (47, "SC"), (48, "SC"),
    (49, "RS"), (51, "RS"), (53, "RS"), (54, "RS"), (55, "RS"),
    (61, "DF"), (62, "GO"), (64, "GO"), (65, "MT"), (66, "MT"),
    (71, "BA"), (73, "BA"), (74, "BA"), (75, "BA"), (77, "BA"),
    (81, "PE"), (82, "PE"), (83, "PB"), (84, "RN"), (85, "CE"),
    (86, "PI"), (87, "SE"), (88, "SE"), (89, "AL"), (91, "PA"),
    (92, "AM"), (93, "PA"), (94, "MA"), (95, "MA"), (96, "MA"),
    (98, "MA"), (99, "MA"),
]

CITIES = [
    "São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Curitiba",
    "Belo Horizonte", "Uberlândia", "Lavras", "Florianópolis", "Joinville",
    "Porto Alegre", "Caxias do Sul", "Pelotas", "Brasília", "Goiânia",
    "Salvador", "Feira de Santana", "Recife", "Olinda", "Fortaleza",
    "Teresina", "Natal", "Maceió", "São Luís", "Manaus", "Belém",
    "Vitória", "Cuiabá", "Campo Grande", "João Pessoa",
]

STREETS = [
    "Rua das Flores", "Av. Brasil", "Rua Sete de Setembro", "Av. Paulista",
    "Rua XV de Novembro", "Av. Getúlio Vargas", "Rua da Paz", "Av. Independência",
    "Rua do Comércio", "Av. Beira Mar", "Rua São José", "Av. Central",
    "Rua das Acácias", "Av. das Nações", "Rua do Sol", "Av. Atlântica",
    "Rua dos Ipês", "Av. Liberdade", "Rua do Comércio", "Av. 25 de Agosto",
]


# ---------------------------------------------------------------------------
# CPF validation helpers
# ---------------------------------------------------------------------------

def _cpf_digit(check: str) -> str:
    """Compute one CPF check digit."""
    weight = [10 - i for i in range(len(check))]
    total = sum(int(d) * w for d, w in zip(check, weight))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def generate_cpf(rng: random.Random) -> str:
    """Generate a valid-format Brazilian CPF (passes the standard check-digit test)."""
    digits = "".join(str(rng.randint(0, 9)) for _ in range(9))
    d1 = _cpf_digit(digits)
    d2 = _cpf_digit(digits + d1)
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{d1}{d2}"


def _cnh_digit(value: int) -> int:
    """Compute CNH check digit (mod 11, 10→0)."""
    remainder = value % 11
    return 0 if remainder >= 10 else remainder


def generate_cnh(rng: random.Random) -> str:
    """Generate a valid-format CNH: 8 digits + 1 letter."""
    digits = [str(rng.randint(0, 9)) for _ in range(8)]
    # check digit using weights 1..8
    weight_sum = sum(int(d) * w for d, w in zip(digits, range(1, 9)))
    cd = _cnh_digit(weight_sum)
    letters = "ABCDEFGHIJKLMNOPQRSTUVXZ"
    letter = letters[rng.randrange(len(letters))]
    return "".join(digits) + letter


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Identity:
    """A synthetic Brazilian identity ready for registration."""
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str            # (DD) 9XXXX-XXXX
    cpf: str              # XXX.XXX.XXX-XX
    cnh: str              # 8 digits + letter
    birth_date: str       # YYYY-MM-DD
    address: str
    city: str
    state: str
    password: str         # generated password
    gender: str           # "M" or "F"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class IdentityGenerator:
    """Generates random Brazilian identities with valid CPF/CNH.

    Deterministic when given a seed (useful for reproducible test batches).
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _random_birth_date(self) -> str:
        year = self.rng.randint(1970, 2000)
        month = self.rng.randint(1, 12)
        day = self.rng.randint(1, 28)
        return f"{year:04d}-{month:02d}-{day:02d}"

    def _random_password(self) -> str:
        """Generate a password that meets common requirements (upper, lower, digit, special)."""
        lower = "abcdefghijkmnpqrstuvwxyz"
        upper = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        digits = "23456789"
        specials = "!@#$%&*"
        pw = (
            self.rng.choice(upper)
            + self.rng.choice(lower)
            + self.rng.choice(digits)
            + self.rng.choice(specials)
        )
        for _ in range(12):
            pool = lower + upper + digits + specials
            pw += self.rng.choice(pool)
        # shuffle
        pw_list = list(pw)
        self.rng.shuffle(pw_list)
        return "".join(pw_list)

    def _random_email(self, first: str, last: str) -> str:
        """Generate a plausible email address."""
        first_l = first.lower()
        last_l = last.lower()
        # strip accents
        import unicodedata
        first_l = unicodedata.normalize("NFKD", first_l).encode("ascii", "ignore").decode()
        last_l = unicodedata.normalize("NFKD", last_l).encode("ascii", "ignore").decode()

        style = self.rng.choice([
            lambda f, l: f"{f}.{l}",
            lambda f, l: f"{f}{l}",
            lambda f, l: f"{f}_{l}",
            lambda f, l: f"{f}{self.rng.randint(1, 99)}",
            lambda f, l: f"{f[0]}{l}{self.rng.randint(1, 999)}",
        ])
        local = style(first_l, last_l)
        domain = self.rng.choice([
            "gmail.com", "gmail.com", "gmail.com", "hotmail.com",
            "outlook.com", "yahoo.com.br", "yahoo.com", "bol.com.br",
            "terra.com.br", "ig.com.br",
        ])
        return f"{local}@{domain}"

    def _random_phone(self) -> tuple[str, str]:
        """Return (phone, state)."""
        ddd, state = self.rng.choice(DDD_STATE)
        # mobile: 9 + 4 digits + 4 digits
        p1 = self.rng.randint(6000, 9999)
        p2 = self.rng.randint(1000, 9999)
        phone = f"({ddd}) 9{p1}-{p2}"
        return phone, state

    def generate(self) -> Identity:
        """Generate a single synthetic identity."""
        gender = self.rng.choice(["M", "F"])
        if gender == "M":
            first = self.rng.choice(FIRST_NAMES_M)
        else:
            first = self.rng.choice(FIRST_NAMES_F)
        last = self.rng.choice(LAST_NAMES)
        # occasional middle name
        if self.rng.random() < 0.2:
            middle = self.rng.choice(LAST_NAMES)
            full_name = f"{first} {middle} {last}"
        else:
            full_name = f"{first} {last}"

        phone, state = self._random_phone()
        email = self._random_email(first, last)
        cpf = generate_cpf(self.rng)
        cnh = generate_cnh(self.rng)
        birth_date = self._random_birth_date()
        street = self.rng.choice(STREETS)
        number = self.rng.randint(10, 9999)
        city = self.rng.choice(CITIES)
        address = f"{street}, {number}"
        password = self._random_password()

        return Identity(
            first_name=first,
            last_name=last,
            full_name=full_name,
            email=email,
            phone=phone,
            cpf=cpf,
            cnh=cnh,
            birth_date=birth_date,
            address=address,
            city=city,
            state=state,
            password=password,
            gender=gender,
        )

    def generate_batch(self, count: int) -> list[Identity]:
        """Generate a batch of unique identities."""
        seen_emails = set()
        identities = []
        attempts = 0
        while len(identities) < count and attempts < count * 10:
            attempts += 1
            ident = self.generate()
            if ident.email not in seen_emails:
                seen_emails.add(ident.email)
                identities.append(ident)
        return identities
