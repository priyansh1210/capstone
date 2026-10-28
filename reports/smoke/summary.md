| scenario | policy | runs | MAE (sd) | RMSE | cycles | fits | train s | promo | reject | rollback | detect delay d | post-change MAE (120 d) | excess log-error vs no-change (120 d) | recovery d (runs met) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bike_abrupt | adaptive | 1 | 118.1 | 227.5 | 5.0 | 30 | 15.1 | 4.0 | 1.0 | 0.0 | 9.0 | 166.4 | 48 % | - (0/1) |
| bike_abrupt | periodic | 1 | 102.6 | 207.5 | 13.0 | 78 | 41.9 | 7.0 | 6.0 | 1.0 | - | 139.3 | 30 % | 53 (1/1) |
| bike_abrupt | static | 1 | 138.3 | 271.6 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 211.3 | 39 % | - (0/1) |
| bike_gradual | adaptive | 1 | 112.7 | 211.3 | 6.0 | 36 | 18.3 | 4.0 | 2.0 | 0.0 | 50.0 | 132.3 | 34 % | 54 (1/1) |
| bike_gradual | periodic | 1 | 103.5 | 197.3 | 13.0 | 78 | 42.0 | 10.0 | 3.0 | 1.0 | - | 117.7 | 24 % | 54 (1/1) |
| bike_gradual | static | 1 | 136.8 | 260.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 156.6 | 40 % | - (0/1) |
| bike_unmodified | adaptive | 1 | 72.5 | 123.6 | 3.0 | 18 | 9.6 | 2.0 | 1.0 | 0.0 | - | - | - | n/a |
| bike_unmodified | periodic | 1 | 67.9 | 117.7 | 13.0 | 78 | 41.5 | 7.0 | 6.0 | 2.0 | - | - | - | n/a |
| bike_unmodified | static | 1 | 82.0 | 133.8 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | n/a |
| synthetic_abrupt | adaptive | 1 | 56.4 | 115.7 | 3.0 | 18 | 11.5 | 1.0 | 2.0 | 0.0 | 15.0 | 69.6 | 31 % | - (0/1) |
| synthetic_abrupt | periodic | 1 | 54.9 | 111.4 | 8.0 | 48 | 33.3 | 3.0 | 5.0 | 0.0 | - | 68.0 | 28 % | - (0/1) |
| synthetic_abrupt | static | 1 | 57.7 | 119.1 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 71.9 | 34 % | - (0/1) |
| synthetic_stationary | adaptive | 1 | 35.7 | 61.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | n/a |
| synthetic_stationary | periodic | 1 | 35.6 | 61.1 | 8.0 | 48 | 32.1 | 1.0 | 7.0 | 0.0 | - | - | - | n/a |
| synthetic_stationary | static | 1 | 35.7 | 61.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | n/a |

Missed detections (adaptive, injected-change scenarios, 90-day horizon): 0 run(s).
Recovery: days after the change is complete until the 14-day rolling log-error is within 10 % of the same policy on the no-change counterfactual stream for 14 consecutive days; '-' = never met (count of runs that met it in brackets; mean over those).