"""Prototype: public Mega product reads. No CRM, WhatsApp, orders or payments."""
import argparse
import html
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://www.megaeletronicos.com"
ALLOWED = {"www.megaeletronicos.com", "megaeletronicos.com"}
IMAGE_HOSTS = ALLOWED | {"resource.megaeletronicos.com"}

def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c))

def read_public(url):
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED:
        raise ValueError("fonte_nao_permitida")
    req = Request(url, headers={"User-Agent": "RBAtacado-ReadOnlyPrototype/0.1"})
    with urlopen(req, timeout=20) as response:
        if urlparse(response.url).hostname not in ALLOWED:
            raise ValueError("redirecionamento_nao_permitido")
        if "html" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("conteudo_nao_html")
        raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError("pagina_acima_do_limite")
        return raw.decode(response.headers.get_content_charset() or "utf-8")

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        url = urljoin(BASE, dict(attrs).get("href", ""))
        if urlparse(url).hostname in ALLOWED and re.match(r"^/producto/\d+/", urlparse(url).path):
            self.urls.add(url)

def primary_data(document, code):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\b(?:const|let|var)\s+data\s*=\s*", document):
        try:
            item, _ = decoder.raw_decode(document[match.end():].lstrip())
        except (ValueError, TypeError):
            continue
        if isinstance(item, dict) and str(item.get("code")) == code:
            return item
    raise ValueError("produto_principal_nao_confirmado")

def structured_product(document, code):
    for match in re.finditer(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                             document, re.I | re.S):
        try:
            item = json.loads(match.group(1))
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("@type") == "Product":
            if str(item.get("productID") or item.get("sku")) == code:
                return item
    return {}

def presentation(name):
    text = normalized(name)
    flags = [label for pattern, label in [
        (r"\bkit\b", "kit"), (r"\btester\b", "tester"),
        (r"\brefill\b|\brefil\b|\brecarga", "refil")] if re.search(pattern, text)]
    return flags[0] if len(flags) == 1 else ("ambigua" if flags else "não confirmada")

def identity(name):
    text = normalized(name)
    # More specific concentrations before Parfum. Do not equate versions.
    concentration = None
    for pattern, label in [
        (r"\belixir\b", "Elixir"),
        (r"\bextrait(?: de parfum)?\b", "Extrait de Parfum"),
        (r"\bedp\b|\beau de parfum\b", "EDP"),
        (r"\bedt\b|\beau de toilette\b", "EDT"),
        (r"\bparfum\b", "Parfum"),
        (r"\bedc\b|\beau de cologne\b", "EDC")]:
        if re.search(pattern, text):
            concentration = label
            break
    volumes = sorted(set(int(x) for x in re.findall(r"(\d+)\s*ml\b", text)))
    return concentration, volumes[0] if len(volumes) == 1 else None, volumes

def extract(document, url):
    m = re.match(r"^/producto/(\d+)/", urlparse(url).path)
    if not m:
        raise ValueError("anuncio_invalido")
    code = m.group(1)
    data = primary_data(document, code)
    schema = structured_product(document, code)
    lang = data.get("product_lang") or {}
    name = html.unescape(lang.get("name_web") or "").strip()
    if not name:
        raise ValueError("nome_nao_confirmado")
    available = data.get("in_stock")
    state = ("disponivel" if available is True else
             "indisponivel" if available is False else "nao_confirmado")
    version, volume, volumes = identity(name)
    image = schema.get("image")
    if not isinstance(image, str) or urlparse(image).scheme != "https" or urlparse(image).hostname not in IMAGE_HOSTS:
        image = None
    schema_state = (schema.get("offers") or {}).get("availability")
    disagreement = bool(schema_state and available is not None and
                        ((schema_state.endswith("/InStock") and available is False) or
                         (schema_state.endswith("/OutOfStock") and available is True)))
    return {
        "fornecedor": "Mega Eletrônicos", "codigo": code, "nome": name,
        "marca": (data.get("brand") or {}).get("name"),
        "versao": version, "variante": "Eau Forte" if "eau forte" in normalized(name) else None, "volume_ml": volume, "volumes_citados_ml": volumes,
        "apresentacao": presentation(name), "imagem_url": image,
        "fonte": url, "consultado_em_utc": datetime.now(timezone.utc).isoformat(),
        "disponibilidade": state, "fonte_estoque": "anuncio.data.in_stock",
        "json_ld_divergente": disagreement,
        "quantidade_disponivel": None,
        "preco_final_aprovado_brl": None, "situacao_preco": "pendente_de_consulta_e_aprovacao"
    }

def relevant(url, query):
    slug = normalized(urlparse(url).path)
    words = re.findall(r"[a-z0-9]+", normalized(query))
    words = [w for w in words if w not in {"perfume", "quero", "um", "uma", "ml", "de", "do"}]
    slug_tokens = set(re.findall(r"[a-z]+|\d+", slug))
    return all(w in slug_tokens for w in words) if words else False

def search(query):
    document = read_public(BASE + "/producto/buscar/?search=" + quote(query))
    parser = Links()
    parser.feed(document)
    urls = sorted(u for u in parser.urls if relevant(u, query))
    # Safety resource cap is not a customer-facing number of choices.
    complete = len(urls) <= 20
    found, excluded, failures = [], 0, 0
    for url in urls[:20]:
        time.sleep(0.5)
        try:
            item = extract(read_public(url), url)
            if item["disponibilidade"] == "disponivel":
                found.append(item)
            elif item["disponibilidade"] == "indisponivel":
                excluded += 1
            else:
                failures += 1
        except Exception:
            failures += 1
    if not found and urls and complete and not failures and excluded == len(urls):
        result = "sem_estoque_nos_anuncios_verificados"
    elif not found:
        result = "nao_foi_possivel_confirmar"
    else:
        result = "opcoes_disponiveis"
    return {"status": result, "busca_completa": complete,
            "anuncios_relevantes_encontrados": len(urls), "excluidos_sem_estoque": excluded,
            "consultas_nao_confirmadas": failures, "opcoes": found,
            "observacao": "Protótipo de leitura; não comprova cobertura integral do catálogo. Não altera CRM."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--busca", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(search(args.busca), ensure_ascii=False, indent=2))
    except Exception:
        print(json.dumps({"status": "consulta_nao_confirmada", "opcoes": []}, ensure_ascii=False))
        raise SystemExit(1)