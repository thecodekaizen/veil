# Physical-model calibration development check

Simulation only. Supplied physical families, fitted numerically. No Meta calls.

| Development system | Selected sensor lag | Mean sensor RMSE °C |
|---|---|---:|
| coupled | False | 0.01240 |
| sensor delay | True | 0.01234 |

Selection uses whole-trial validation, before challenge measurements are revealed.
Only two already-used development instances and one challenge schedule were checked.
Physical model families, parameter bounds and equations were supplied by the developer.
This is calibration within a bounded family, not discovery of arbitrary laws or proven real-world mechanisms.
The separately coded exact matrix-exponential predictor is checked against the RK4 environment.
No hardware, industrial savings, held-out superiority or substantive Meta contribution is established.
