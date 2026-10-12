import unittest,tempfile,json,os
from pathlib import Path
from decimal import Decimal
import orcamento as o
class Test(unittest.TestCase):
 def test_round_unit_before_quantity(self):
  self.assertEqual(o.calcular('4.75','6.21',3,politica=(Decimal('1.02'),Decimal('1.20'))),(3610,10830))
 def test_no_private_policy_no_quote(self):
  with self.assertRaises(Exception):o.politica_privada(Path('/fixture-missing-pricing.json'))
 def test_policy_private_permissions(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'pricing.json';p.write_text(json.dumps({'fx_multiplier':'1.02','sale_multiplier':'1.20'}));p.chmod(0o600)
   self.assertEqual(o.politica_privada(p),(Decimal('1.02'),Decimal('1.20')))
   p.chmod(0o644)
   with self.assertRaises(Exception):o.politica_privada(p)
 def test_rejects_symlink(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'pricing.json';p.write_text('{}');p.chmod(0o600)
   link=Path(d)/'link';link.symlink_to(p)
   with self.assertRaises(Exception):o.politica_privada(link)
 def test_invalid_factor(self):
  with self.assertRaises(Exception):o.calcular('10','5',2,politica=(Decimal('NaN'),Decimal('1.20')))
if __name__=='__main__':unittest.main()
