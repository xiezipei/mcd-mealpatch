from .cart import fingerprint


def money(value):
    return f'{value / 100:.2f}'


def render(cart):
    q = cart['quote']
    valid = q and q['fingerprint'] == fingerprint(cart)
    lines = ['# MealPatch 餐单报告 · 未下单', '', f'版本：{cart["version"]}；门店：{cart["storeCode"]}', '']
    for i in cart['items']:
        lines.append(f'- {i["member_id"]} | {i["line_id"]} | {i["name"]} × {i["quantity"]}' + (' [锁定]' if i['locked'] else ''))
    if not valid:
        lines.extend(['', '当前版本待核价；历史报价不可作为当前实价。'])
        return '\n'.join(lines) + '\n'
    lines.extend(['', '历史快照演示，非实时报价。' if q['source'] != 'live' else '本次官方核价；价格可能随时间变化。',
                  f'合计：{money(q["total"])} 元；预算：{money(cart["budget_cents"])} 元', q['method']])
    if q['total'] > cart['budget_cents']:
        lines.append(f'超预算 {money(q["total"] - cart["budget_cents"])} 元；未自动改餐。')
    previous = cart['history'][-1] if cart['history'] else None
    lines.extend(['', '| 成员 | 当前（元） | 相比上次核价（元） |', '| --- | ---: | ---: |'])
    for member, amount in q['shares'].items():
        delta = amount - previous['quote']['shares'].get(member, 0) if previous else 0
        lines.append(f'| {member} | {money(amount)} | {money(delta) if previous else "—"} |')
    if previous:
        lines.extend(['', f'整单变化：{money(q["total"] - previous["quote"]["total"])} 元', '', '## 餐品变化'])
        old = {i['line_id']: i for i in previous['items']}
        new = {i['line_id']: i for i in cart['items']}
        for key in sorted(old.keys() | new.keys()):
            a, b = old.get(key), new.get(key)
            if a != b:
                describe = lambda i: f'{i["member_id"]} {i["name"]} × {i["quantity"]}' if i else '无'
                lines.append(f'- {describe(a)} → {describe(b)}')
        lines.append('\n锁定保护餐品配置与份数，不保证优惠变化后的分摊金额不变。')
    return '\n'.join(lines) + '\n'
