# Interpretation

The 30 simulated systems use ten fresh seeds per world, each with three correlated challenge schedules. Physical-family calibration generalizes within its supplied families: median challenge errors are 0.0122°C without sensor delay and 0.0125°C with delay.

The unsupported quadratic-loss world exposes failure. Physical calibration exceeds the preregistered diagnostic 0.3°C threshold on 8/30 challenges (maximum 0.8262°C). Only 1/8 failures has whole-trial training validation above that threshold. ARX exceeds it on 8/90 total challenges; only 2/8 have validation flags. Training validation therefore does not reliably certify generalization to new excitation schedules. The threshold is diagnostic, not a physical safety tolerance.

Do not claim the investigator can reliably recognize model inadequacy yet. Next work should address prospective model adequacy and experiment selection, with predictions frozen before new measurements. Conventional calibration is established in simulation; substantive Meta contribution and hardware transfer remain unestablished.

No API calls occurred. An initial harness invocation failed before fitting/scoring because public observations omitted sample_interval_s. That metadata field was added before the completed run; no scientific parameters or thresholds were adjusted after seeing results.
