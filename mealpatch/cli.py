import argparse
import copy
import json
import sys
from pathlib import Path
from . import cart as c
from .mcp import Client
from .pricing import attach, quote
from .report import render


def demo(offline, client=None):
    if offline:
        store = '1400828'
        data = json.loads((Path(__file__).parent.parent / 'examples' / 'snapshot.json').read_text())
        products = data['products']
    else:
        client = client or Client()
        stores = client.call('query-nearby-stores', {'beType': 1, 'searchType': 2, 'city': '广州', 'keyword': '天河智慧城'})
        store = next(s['storeCode'] for s in stores if s['businessStatus'])
        products = {code: c.verified_product(client, {'storeCode': store}, code) for code in ('1100', '1440', '4810', '1406', '4437')}
    draft = c.new(store, ['A', 'B', 'C'], 12000)
    for member, code in [('A', '1100'), ('B', '1440'), ('B', '4810'), ('C', '1406')]:
        draft = c.mutate(draft, 'add', member=member, product=products[code])
    for i in list(draft['items']):
        if i['member_id'] in ('A', 'C'):
            draft = c.mutate(draft, 'lock', line=i['line_id'])
    draft = attach(draft, data['before'], c.fingerprint(draft), source='historical') if offline else quote(draft, client)
    line = next(i['line_id'] for i in draft['items'] if i['productCode'] == '4810')
    draft = c.mutate(draft, 'replace', line=line, product=products['4437'])
    draft = attach(draft, data['after'], c.fingerprint(draft), source='historical') if offline else quote(draft, client)
    return draft


def main():
    parser = argparse.ArgumentParser(description='MealPatch：下单前餐单草稿，不下单、不支付')
    parser.add_argument('--cart', default='.mealpatch/cart.json')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('stores'); p.add_argument('city'); p.add_argument('keyword')
    sub.add_parser('menu')
    p = sub.add_parser('detail'); p.add_argument('code')
    p = sub.add_parser('init'); p.add_argument('--store', required=True); p.add_argument('--members', nargs='+', required=True); p.add_argument('--budget', required=True)
    p = sub.add_parser('add'); p.add_argument('member'); p.add_argument('code'); p.add_argument('--quantity', type=int, default=1)
    for action in ('lock', 'unlock', 'remove', 'quantity', 'replace'):
        p = sub.add_parser(action); p.add_argument('line')
        if action == 'quantity': p.add_argument('quantity', type=int)
        if action == 'replace': p.add_argument('code')
    p = sub.add_parser('quote'); p.add_argument('--equal', action='store_true', help='明细无法解释整单时明确同意均分')
    sub.add_parser('report')
    p = sub.add_parser('demo'); mode = p.add_mutually_exclusive_group(required=True); mode.add_argument('--offline', action='store_true'); mode.add_argument('--online', action='store_true')
    args = parser.parse_args()
    try:
        command = args.command
        if command == 'demo':
            print(render(demo(args.offline)), end=''); return
        if command == 'stores':
            print(json.dumps(Client().call('query-nearby-stores', {'beType': 1, 'searchType': 2, 'city': args.city, 'keyword': args.keyword}), ensure_ascii=False, indent=2)); return
        if command == 'init':
            if Path(args.cart).exists():
                raise ValueError('草稿已存在；请用--cart选择新文件，避免覆盖')
            draft = c.new(args.store, args.members, c.cents(args.budget))
        else:
            draft = c.load(args.cart)
            original = copy.deepcopy(draft)
            if command == 'report':
                print(render(draft), end=''); return
            if command in ('menu', 'detail'):
                name = 'query-meals' if command == 'menu' else 'query-meal-detail'
                params = {'storeCode': draft['storeCode'], 'orderType': 1, 'beType': 1}
                if command == 'detail': params['code'] = args.code
                print(json.dumps(Client().call(name, params), ensure_ascii=False, indent=2)); return
            if command == 'quote':
                draft = quote(draft, Client(), args.equal)
            elif command in ('add', 'replace'):
                # Check locked/nonexistent lines before any network activity.
                if command == 'replace':
                    target = next((i for i in draft['items'] if i['line_id'] == args.line), None)
                    if target is None or target['locked']: raise ValueError('餐品行不存在或已锁定')
                product = c.verified_product(Client(), draft, args.code)
                draft = c.mutate(draft, command, line=getattr(args, 'line', None), member=getattr(args, 'member', None), product=product, quantity=getattr(args, 'quantity', 1))
            else:
                draft = c.mutate(draft, command, line=args.line, quantity=getattr(args, 'quantity', 1))
            if c.load(args.cart) != original:
                raise ValueError('磁盘草稿已变化；拒绝覆盖，请串行操作')
        c.save(args.cart, draft)
        print(render(draft), end='')
    except (ValueError, KeyError, TypeError, OSError, StopIteration):
        # Do not print untrusted response bodies, credentials or exception reprs.
        print('操作失败：参数/商品/锁定状态无效，或官方核价、网络、文件校验失败。草稿文件未更新；请检查配置与当前餐单，勿沿用旧价。', file=sys.stderr)
        sys.exit(1)
