# Fresh simulated-system validation

Ten new seeds per world; three unseen schedules; three shared training trials. Zero Meta calls.

| World | Method | Median RMSE °C | Maximum RMSE °C | Challenges above 0.3°C |
|---|---|---:|---:|---:|
| coupled | physical | 0.0122 | 0.0266 | 0/30 |
| coupled | arx | 0.0344 | 0.0607 | 0/30 |
| sensor-delay | physical | 0.0125 | 0.0276 | 0/30 |
| sensor-delay | arx | 0.2055 | 0.3270 | 1/30 |
| nonlinear-loss-stress | physical | 0.0994 | 0.8262 | 8/30 |
| nonlinear-loss-stress | arx | 0.0920 | 0.7466 | 7/30 |

Each system contributes three correlated challenge scores; these are not 90 independent systems.
The nonlinear stress case uses unsupported quadratic heat loss during both training and challenge.
A validation flag measures held-trial prediction error, not diagnosis of the hidden mechanism.
Source and protocol were saved before execution. No retuning within this run.
This establishes neither hardware performance nor an advantage from Meta.
