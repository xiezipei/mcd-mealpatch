import copy
import hashlib
import json
import os
import tempfile
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path


def cents(value):
    try:
        amount = Decimal(str(value)) * 100
        if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
            raise ValueError('金额必须非负且最多两位小数')
        return int(amount)
    except InvalidOperation:
        raise ValueError('金额格式无效') from None


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('需要有效整数金额或正整数数量')
    return value


def fingerprint(cart):
    payload = {k: cart[k] for k in ('cart_id', 'version', 'storeCode', 'members', 'budget_cents', 'items')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def new(store, members, budget):
    if not 2 <= len(members) <= 6 or len(set(members)) != len(members) or any(not m.strip() for m in members):
        raise ValueError('需要2～6个不重复的非空成员ID')
    return {'cart_id': uuid.uuid4().hex, 'version': 1, 'storeCode': store, 'members': members,
            'budget_cents': integer(budget), 'items': [], 'quote': None, 'history': [], 'baseline': None}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load(path):
    return json.loads(Path(path).read_text())


def verified_product(client, cart, code):
    args = {'storeCode': cart['storeCode'], 'orderType': 1, 'beType': 1}
    menu = client.call('query-meals', args)['meals']
    if code not in menu:
        raise ValueError('商品不在当前门店菜单')
    item = menu[code]
    if item.get('canWithOrder') or item.get('withOrder'):
        raise ValueError('首版不支持随单购商品')
    detail = client.call('query-meal-detail', {**args, 'code': code})
    if detail.get('code') != code or detail.get('rounds'):
        raise ValueError('首版不支持套餐选配')
    values = []
    for group in detail.get('modification', {}).get('items', []):
        for value in group['values']:
            qty = integer(value.get('selectedQuantity', 0))
            key = value.get('selectedKey') if qty else value.get('unselectedKey')
            if key:
                values.append({'code': value['code'], 'key': key, 'quantity': qty if qty else 1})
            elif qty:
                raise ValueError('默认配置缺少有效编码')
    return {'productCode': code, 'name': detail['name'], 'baseline_cents': cents(item['currentPrice']),
            'modification': {'values': values} if values else None}


def mutate(cart, action, line=None, member=None, product=None, quantity=1):
    result = copy.deepcopy(cart)
    target = next((i for i in result['items'] if i['line_id'] == line), None)
    if action != 'add' and target is None:
        raise ValueError('餐品行不存在')
    if action not in ('add', 'lock', 'unlock') and target['locked']:
        raise ValueError('餐品已锁定，请先明确解锁')
    if action == 'add':
        if member not in result['members'] or product is None:
            raise ValueError('成员或已核验商品无效')
        result['items'].append({**product, 'line_id': uuid.uuid4().hex[:12], 'member_id': member,
                                'quantity': integer(quantity, 1), 'locked': False})
    elif action in ('lock', 'unlock'):
        target['locked'] = action == 'lock'
    elif action == 'replace':
        if product is None:
            raise ValueError('需要已核验商品')
        target.update(product)
    elif action == 'quantity':
        target['quantity'] = integer(quantity, 1)
    elif action == 'remove':
        result['items'].remove(target)
    else:
        raise ValueError('未知修改动作')
    if result['quote']:
        result['history'].append({'items': copy.deepcopy(cart['items']), 'quote': result['quote']})
    result.update(version=cart['version'] + 1, quote=None, baseline=None)
    return result
