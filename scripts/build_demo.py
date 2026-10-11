"""Generate reproducible demo artifacts from the application's offline report."""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mealpatch.cli import demo
from mealpatch.report import render

draft = demo(True)
# Stable display IDs make recorded examples reproducible; no user cart is changed.
for index, item in enumerate(draft['items'], 1):
    old_id = item['line_id']
    item['line_id'] = f'demo-{index}'
    for version in draft['history']:
        for previous in version['items']:
            if previous['line_id'] == old_id:
                previous['line_id'] = item['line_id']
from mealpatch.cart import fingerprint
draft['quote']['fingerprint'] = fingerprint(draft)
report = render(draft)
output = ROOT / 'demo'
output.mkdir(exist_ok=True)
(output / 'result.md').write_text(report)
page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>MealPatch · 历史核价演示报告</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#eef1f5;color:#202b3c;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;padding:40px}
main{max-width:1120px;margin:auto;background:white;border-radius:20px;overflow:hidden;box-shadow:0 12px 40px #16264212}
header{padding:28px 36px;background:#15283e;color:white}h1{margin:0 0 12px;font-size:28px}header p{margin:0;color:#d5e0ec;line-height:1.7}
.notice{padding:18px 36px;background:#fff2ce;color:#725016;font-weight:600;line-height:1.6}
pre{margin:0;padding:28px 36px;font-family:"SFMono-Regular","Menlo","PingFang SC",monospace;font-size:17px;line-height:1.85;white-space:pre-wrap;overflow-wrap:anywhere}
footer{padding:18px 36px;border-top:1px solid #e7ecf1;color:#64748b;font-size:14px;line-height:1.7}
</style><main><header><h1>麦麦改单官 · MealPatch</h1><p>只改指定的一份，保留其他人的选择。<br>下面是 CLI 实际输出的只读展示，不是产品交互界面。</p></header>
<div class="notice">历史数据：2026-10-11 17:17（北京时间） · 广州天河智慧城高唐路餐厅<br>离线复现，非实时价格 · 未下单 · 未支付</div>
<pre>REPORT</pre><footer>来源：python3 -m mealpatch demo --offline<br>独立参赛作品，非麦当劳官方产品。价格及供应状态以官方实时返回为准。</footer></main></html>'''
(output / 'report.html').write_text(page.replace('REPORT', html.escape(report)))
print('Generated demo/result.md and demo/report.html (historical data only)')
