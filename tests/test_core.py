import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from mealpatch import cart as c
from mealpatch.cli import demo
from mealpatch.pricing import allocate, attach, quote
from mealpatch.report import render
from mealpatch.mcp import Client, MCPError


class Core(unittest.TestCase):
    def setUp(self):
        self.cart = c.new('test', ['A', 'B'], 100)
        self.product = {'productCode': 'p', 'name': '单品', 'baseline_cents': 100}
        self.cart = c.mutate(self.cart, 'add', member='A', product=self.product)
        self.line = self.cart['items'][0]['line_id']

    def test_locked_reject_preserves(self):
        draft = c.mutate(self.cart, 'lock', line=self.line)
        original = copy.deepcopy(draft)
        for action in ('replace', 'quantity', 'remove'):
            with self.assertRaises(ValueError): c.mutate(draft, action, line=self.line, product=self.product)
            self.assertEqual(draft, original)

    def test_local_replace_and_invalidation(self):
        d = c.mutate(self.cart, 'add', member='B', product=self.product)
        attach(d, {'price':200,'productList':[{'productCode':'p','quantity':2,'subtotal':200}]}, c.fingerprint(d))
        changed = c.mutate(d, 'replace', line=self.line, product={**self.product, 'productCode':'q'})
        self.assertEqual(changed['items'][1], d['items'][1])
        self.assertIsNone(changed['quote'])
        self.assertEqual(len(changed['history']), 1)
        self.assertIn('待核价', render(changed))

    def test_invalid_quantity(self):
        for value in (0, -1, True, 1.2):
            with self.assertRaises(ValueError): c.mutate(self.cart, 'quantity', line=self.line, quantity=value)

    def test_cents(self):
        self.assertEqual(c.cents('14.50'), 1450)
        for v in ('NaN', 'Infinity', '-1', '0.001'):
            with self.assertRaises(ValueError): c.cents(v)

    def test_allocation_conservation(self):
        for total in range(100):
            for weights in ({'B':1,'A':1,'C':1}, {'A':0,'B':3}, {'A':17,'B':19,'C':2}):
                result = allocate(total, weights)
                self.assertEqual(sum(result.values()), total)
                self.assertEqual(result, allocate(total, dict(reversed(list(weights.items())))))
        self.assertEqual(allocate(1, {'B':1,'A':1}), {'B':0,'A':1})

    def test_duplicate_product(self):
        d = c.mutate(self.cart, 'add', member='B', product=self.product)
        attach(d, {'price':101,'productList':[{'productCode':'p','quantity':1,'subtotal':50},{'productCode':'p','quantity':1,'subtotal':51}]}, c.fingerprint(d))
        self.assertEqual(d['quote']['shares'], {'A':51,'B':50})

    def test_fallback_and_equal(self):
        attach(self.cart, {'price':150}, c.fingerprint(self.cart))
        self.assertIn('约定', self.cart['quote']['method'])
        self.cart['items'][0].pop('baseline_cents')
        with self.assertRaises(ValueError): attach(self.cart, {'price':150}, c.fingerprint(self.cart))
        attach(self.cart, {'price':151}, c.fingerprint(self.cart), equal=True)
        self.assertEqual(self.cart['quote']['shares'], {'A':76,'B':75})

    def test_stale_and_bad_price(self):
        old = c.fingerprint(self.cart)
        changed = c.mutate(self.cart, 'lock', line=self.line)
        with self.assertRaises(ValueError): attach(changed, {'price':100}, old)
        for value in (-1, True, '100', None):
            with self.assertRaises(ValueError): attach(self.cart, {'price':value}, old)

    def test_budget_and_snapshot(self):
        draft = demo(True)
        self.assertEqual(draft['quote']['total'], 8500)
        self.assertEqual(draft['quote']['shares'], {'A':2600,'B':3550,'C':2350})
        self.assertEqual(draft['history'][-1]['quote']['total'], 8650)
        draft['budget_cents'] = 1
        draft['quote']['fingerprint'] = c.fingerprint(draft)
        self.assertIn('超预算', render(draft))
        self.assertIn('历史快照', render(draft))

    def test_business_error(self):
        client = object.__new__(Client)
        client.request = lambda *a: {'structuredContent':{'success':False}}
        with self.assertRaises(MCPError): client.call('query-meals', {})
        with self.assertRaises(MCPError): client.call('create-order', {})

    def test_network_and_protocol(self):
        client = object.__new__(Client); client.counter = 0; client.headers = {}
        for error in (TimeoutError(), OSError()):
            with patch('urllib.request.urlopen', side_effect=error):
                with self.assertRaises(MCPError): client.request('tools/list')
        class Response:
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"id":999,"result":{}}'
        with patch('urllib.request.urlopen', return_value=Response()):
            with self.assertRaises(MCPError): client.request('tools/list')

    def test_product_restrictions(self):
        class Fake:
            def call(self, name, args):
                return {'meals':{'p':{'currentPrice':'1'}}} if name == 'query-meals' else {'code':'p','name':'套餐','rounds':[{}]}
        with self.assertRaises(ValueError): c.verified_product(Fake(), self.cart, 'p')

    def test_default_modifications(self):
        class Fake:
            def call(self, name, args):
                if name == 'query-meals': return {'meals':{'p':{'currentPrice':'1'}}}
                return {'code':'p','name':'汉堡','rounds':[], 'supportModify':True,
                        'modification':{'items':[{'values':[
                            {'code':'sauce','selectedQuantity':1,'selectedKey':'yes','unselectedKey':'no'},
                            {'code':'extra','selectedQuantity':0,'selectedKey':'yes','unselectedKey':'no'}]}]}}
        p = c.verified_product(Fake(), self.cart, 'p')
        self.assertEqual(p['modification']['values'], [{'code':'sauce','key':'yes','quantity':1},{'code':'extra','key':'no','quantity':1}])

    def test_wrong_official_quantity(self):
        with self.assertRaises(ValueError):
            attach(self.cart, {'price':100,'productList':[{'productCode':'p','quantity':2,'subtotal':100}]}, c.fingerprint(self.cart))

    def test_cli_failure_keeps_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + '/cart.json'
            c.save(path, self.cart)
            with open(path) as stream: before = stream.read()
            result = subprocess.run([sys.executable,'-m','mealpatch','--cart',path,'quantity',self.line,'0'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            with open(path) as f: self.assertEqual(f.read(), before)


if __name__ == '__main__':
    unittest.main()
