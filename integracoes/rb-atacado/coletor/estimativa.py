"""Preço estimativo verificado; não aprova pedido, reserva ou compra."""
from datetime import timedelta
from urllib.parse import urlsplit
import re
import orcamento as o
import mega_readonly as mega

def preparar(url, quantidade=None, fetch=o.obter, now=None, politica=None):
    now=now or o.agora()
    u=urlsplit(url)
    if u.scheme!='https' or u.username or u.password or u.port not in (None,443) or u.hostname not in o.MEGA_HOSTS or not re.fullmatch(r'/producto/\d+/[^/]+/?',u.path) or u.query or u.fragment:
        raise o.Recusa('anuncio_invalido')
    if quantidade is not None and (type(quantidade) is not int or not 1<=quantidade<=1000):
        raise o.Recusa('quantidade_invalida')
    document=fetch(url,o.MEGA_HOSTS)
    item=mega.extract(document,url)
    if item['disponibilidade']!='disponivel':
        raise o.Recusa('estoque_indisponivel_ou_nao_confirmado')
    data=mega.primary_data(document,item['codigo'])
    offers=mega.structured_product(document,item['codigo']).get('offers')
    if not isinstance(offers,dict) or offers.get('priceCurrency')!='USD':
        raise o.Recusa('moeda_preco_nao_confirmada')
    cost=o.numero(data.get('price'))
    if cost!=o.numero(str(offers.get('price',''))):
        raise o.Recusa('preco_divergente')
    base=o.cotacao(fetch(o.FX_URL,o.FX_HOSTS),now)
    # One here computes the unit price; it is never a customer quantity.
    unit,_=o.calcular(str(cost),str(base),1,politica=politica)
    return {
        'produto':{k:item.get(k) for k in ('codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url')},
        'quantidade':quantidade,'moeda':'BRL','situacao':'estimativa',
        'preco_unitario_cents':unit,
        'subtotal_cents':None if quantidade is None else unit*quantidade,
        'quantidade_em_estoque':'nao_informada','disponibilidade_na_consulta':'disponivel',
        'compra_reserva_pagamento_confirmados':False,
        'fechamento_pendente_aprovacao':True,
        'consultado_em_utc':now.isoformat(),
        'valido_ate_utc':(now+timedelta(seconds=120)).isoformat(),
    }
