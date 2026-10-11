from collections import defaultdict
from .cart import fingerprint, integer


def allocate(total, weights):
    integer(total)
    if not weights or any(type(v) is not int or v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError('分摊基准缺失；请明确确认均分')
    denominator = sum(weights.values())
    result = {k: total * v // denominator for k, v in weights.items()}
    order = sorted(weights, key=lambda k: (-(total * weights[k] % denominator), k))
    for k in order[:total - sum(result.values())]:
        result[k] += 1
    return result


def attach(cart, data, expected, equal=False, source='live'):
    if fingerprint(cart) != expected:
        raise ValueError('草稿已变化，拒绝旧版本报价')
    total = integer(data.get('price'))
    expected_qty = defaultdict(int)
    for item in cart['items']:
        expected_qty[item['productCode']] += item['quantity']
    actual_qty, subtotals = defaultdict(int), defaultdict(int)
    for item in data.get('productList', []):
        code = item['productCode']
        actual_qty[code] += integer(item.get('quantity'), 1)
        subtotals[code] += integer(item.get('subtotal'))
    shares = dict.fromkeys(cart['members'], 0)
    if data.get('productList') and actual_qty != expected_qty:
        raise ValueError('官方返回商品数量与草稿不一致，拒绝分账')
    if actual_qty == expected_qty and sum(subtotals.values()) == total:
        for code, subtotal in subtotals.items():
            weights = defaultdict(int)
            for item in cart['items']:
                if item['productCode'] == code:
                    weights[item['member_id']] += item['quantity']
            for member, amount in allocate(subtotal, weights).items():
                shares[member] += amount
        method = '官方商品小计按归属汇总（重复商品按数量本地分配）'
    else:
        weights = dict.fromkeys(cart['members'], 0)
        for item in cart['items']:
            baseline = item.get('baseline_cents')
            if baseline is None or type(baseline) is not int or baseline < 0:
                weights = {}
                break
            weights[item['member_id']] += baseline * item['quantity']
        if equal:
            weights = dict.fromkeys(cart['members'], 1)
        shares = allocate(total, weights)
        method = '约定分摊：用户明确均分' if equal else '约定分摊：按已核验菜单基准金额占比'
    assert sum(shares.values()) == total
    cart['quote'] = {'version': cart['version'], 'fingerprint': expected, 'total': total,
                     'shares': shares, 'method': method, 'source': source}
    return cart


def quote(cart, client, equal=False):
    if not cart['items']:
        raise ValueError('空餐单不能核价')
    expected = fingerprint(cart)
    # Refresh product availability and baseline prices before every real quote.
    from .cart import verified_product
    for item in cart['items']:
        product = verified_product(client, cart, item['productCode'])
        if product.get('modification') != item.get('modification'):
            raise ValueError('官方默认配置已变化，请重新确认商品后更新草稿')
        item['baseline_cents'] = product['baseline_cents']
        item['name'] = product['name']
    expected = fingerprint(cart)
    data = client.call('calculate-price', {'storeCode': cart['storeCode'], 'orderType': 1, 'beType': 1,
                       'items': [{**{'productCode': i['productCode'], 'quantity': i['quantity']},
                                  **({'modification': i['modification']} if i.get('modification') else {})} for i in cart['items']]})
    return attach(cart, data, expected, equal)
