import unittest
import numpy as np
from thermal_investigator.nonlinear import simulate_quadratic,execute_quadratic,fit_quadratic,QuadraticFit
from thermal_investigator.physical import simulate,ThermalSpec
from thermal_investigator.contracts import schedule
from thermal_investigator.lab import parameters
from thermal_investigator.validation import hidden_trace

class QuadraticTests(unittest.TestCase):
    def setUp(self):
        self.rates=np.array([.012,.012,.008,.008,.3,.25,.0005,.0007])
        self.plan=schedule('test',[(60,60)])
    def test_zero_loss_matches_linear(self):
        rates=self.rates.copy();rates[-2:]=0
        np.testing.assert_allclose(simulate_quadratic(rates,self.plan.commands()),simulate(ThermalSpec(False),rates[:6],self.plan.commands()),atol=1e-7)
    def test_independent_hidden_solver(self):
        p=parameters(919,False)
        rates=[p.loss1/p.c1,p.loss2/p.c2,p.coupling/p.c1,p.coupling/p.c2,p.heater1_w/p.c1,p.heater2_w/p.c2,.004/p.c1,.004/p.c2]
        np.testing.assert_allclose(simulate_quadratic(rates,self.plan.commands()),hidden_trace(self.plan.commands(),p,True),atol=1e-7)
    def test_roundtrip_and_invalid_grammar(self):
        model=QuadraticFit(self.rates,0.,0).executable_model()
        np.testing.assert_array_equal(execute_quadratic(model,self.plan.commands()),simulate_quadratic(self.rates,self.plan.commands()))
        for bad in ({**model,'code':'execute'}, {**model,'specification':{'type':'two_node_quadratic_loss','sensor_lag':True}}):
            with self.assertRaises(ValueError):execute_quadratic(bad,self.plan.commands())
    def test_negative_loss_and_nonfinite_rejected(self):
        for bad in (-.001,float('nan')):
            rates=self.rates.copy();rates[-1]=bad
            with self.assertRaises(ValueError):simulate_quadratic(rates,self.plan.commands())
    def test_registry_validates_full_payload(self):
        from thermal_investigator.model_registry import execute_candidate
        model=QuadraticFit(self.rates,0.,0).executable_model()
        np.testing.assert_array_equal(execute_candidate(model,self.plan.commands()),simulate_quadratic(self.rates,self.plan.commands()))
        with self.assertRaises(ValueError):execute_candidate({'specification':{'type':'python'}},self.plan.commands())
        with self.assertRaises(ValueError):execute_candidate({**model,'code':'anything'},self.plan.commands())
    def test_training_fit_predicts_new_input(self):
        obs=[]
        for p in [schedule('left',[(60,0)]),schedule('right',[(0,60)]),self.plan]:
            obs.append({'commands_fraction':p.commands(),'temperature_c':simulate_quadratic(self.rates,p.commands()).tolist(),'ambient_c':22.,'sample_interval_s':2.})
        fitted=fit_quadratic(obs)
        commands=schedule('new',[(20,50),(50,10),(0,0),(30,30)]).commands()
        self.assertLess(float(np.max(np.abs(fitted.predict(commands)-simulate_quadratic(self.rates,commands)))),.001)
