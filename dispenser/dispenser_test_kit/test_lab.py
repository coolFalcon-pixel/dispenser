import unittest
import lab_run as lab
from unittest.mock import patch
class LabTests(unittest.TestCase):
 def setUp(self):
  lab.MODE='raw';lab.EARLY_G=0;lab.LOG=None
  self.now=100.;self.stopped=[]
  self.c=lab.LabController(lambda:self.stopped.append(True),clock=lambda:self.now)
  self.c.request('tare');_,t=self.c.take_action();self.c.finish_tare([1000]*30,t)
 def dose(self):
  self.c.sample(1000,100);self.c.request(20);self.c.take_action()
 def test_baseline(self):
  self.dose();self.assertEqual(self.c.target,20);self.c.sample(3000,100)
  self.assertEqual(self.c.mode,'idle')
 def test_compensation(self):
  lab.MODE='median3_early';lab.EARLY_G=1.5;self.dose()
  self.assertEqual(self.c.target,18.5)
 def test_median_is_causal(self):
  lab.MODE='median3';self.dose();self.c.sample(11000,100)
  self.assertEqual(self.c.mode,'running');self.assertEqual(self.c.weight,0)
 def test_negative_not_hidden(self):
  lab.MODE='median3';self.dose();self.c.sample(0,100)
  self.assertEqual(self.c.mode,'fault');self.assertTrue(self.stopped)
 def test_stop_and_stale(self):
  self.dose();self.c.press_stop();self.assertEqual(self.c.mode,'idle')
  self.c.release_stop();self.c.sample(1000,100);self.c.request(20);self.c.take_action()
  self.now+=1.1;self.c.watchdog();self.assertEqual(self.c.mode,'fault')
 def test_reject_excess_compensation(self):
  lab.EARLY_G=20;self.c.request(20);self.c.take_action()
  self.assertEqual(self.c.mode,'idle')
 def test_tare_clears_history(self):
  lab.MODE='median3';self.c.sample(1500,100)
  self.c.request('tare');_,t=self.c.take_action();self.c.finish_tare([2000]*30,t)
  self.assertEqual(list(self.c.history),[2000]*3)
if __name__=='__main__':unittest.main()
