| scenario | policy | runs | MAE (sd) | RMSE | cycles | fits | train s | promo | reject | rollback | detect delay d | post-change MAE (120 d) | excess log-error vs no-change (120 d) | recovery d (runs met) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bike_abrupt | adaptive | 1 | 123.4 | 213.7 | 29.0 | 174 | 88.5 | 27.0 | 2.0 | 3.0 | 15.0 | 169.7 | 31 % | 237 (1/1) |
| bike_abrupt | periodic | 1 | 101.2 | 181.6 | 91.0 | 546 | 356.2 | 77.0 | 14.0 | 7.0 | - | 144.3 | 31 % | 101 (1/1) |
| bike_abrupt | static | 1 | 184.0 | 353.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 167.1 | 42 % | 269 (1/1) |
| bike_gradual | adaptive | 1 | 116.2 | 201.3 | 29.0 | 174 | 90.0 | 27.0 | 2.0 | 1.0 | - | 99.0 | 22 % | 190 (1/1) |
| bike_gradual | periodic | 1 | 101.6 | 180.9 | 91.0 | 546 | 358.5 | 77.0 | 14.0 | 8.0 | - | 101.0 | 22 % | 94 (1/1) |
| bike_gradual | static | 1 | 181.3 | 349.1 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 98.2 | 39 % | 116 (1/1) |
| bike_unmodified | adaptive | 1 | 114.7 | 186.3 | 22.0 | 132 | 69.5 | 19.0 | 3.0 | 3.0 | - | - | - | n/a |
| bike_unmodified | periodic | 1 | 81.5 | 136.7 | 91.0 | 546 | 361.1 | 65.0 | 26.0 | 10.0 | - | - | - | n/a |
| bike_unmodified | static | 1 | 136.6 | 228.9 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | n/a |
| synthetic_abrupt | adaptive | 5 | 57.5 (2.0) | 118.4 | 1.8 | 11 | 12.3 | 1.2 | 0.6 | 0.2 | 21.8 | 70.2 | 34 % | - (0/5) |
| synthetic_abrupt | periodic | 5 | 49.4 (2.6) | 99.4 | 26.0 | 156 | 189.8 | 13.0 | 13.0 | 1.2 | - | 70.2 | 35 % | 299 (5/5) |
| synthetic_abrupt | static | 5 | 59.2 (2.7) | 124.5 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 71.0 | 35 % | - (0/5) |
| synthetic_stationary | adaptive | 5 | 34.7 (1.5) | 59.6 | 0.6 | 4 | 4.7 | 0.2 | 0.4 | 0.0 | - | - | - | n/a |
| synthetic_stationary | periodic | 5 | 34.8 (1.6) | 60.2 | 26.0 | 156 | 207.4 | 3.4 | 22.6 | 0.2 | - | - | - | n/a |
| synthetic_stationary | static | 5 | 34.7 (1.5) | 59.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - | n/a |

Missed detections (adaptive, injected-change scenarios, 90-day horizon): 1 run(s).
Recovery: days after the change is complete until the 14-day rolling log-error is within 10 % of the same policy on the no-change counterfactual stream for 14 consecutive days; '-' = never met (count of runs that met it in brackets; mean over those).