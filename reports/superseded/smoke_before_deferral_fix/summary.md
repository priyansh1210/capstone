| scenario | policy | runs | MAE (sd) | RMSE | cycles | fits | train s | promo | reject | rollback | detect delay d | post-change MAE (120 d) | recovery d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bike_abrupt | adaptive | 1 | 114.6 | 226.6 | 4.0 | 24 | 21.6 | 4.0 | 0.0 | 0.0 | 53.0 | 153.8 | 16.0 |
| bike_abrupt | periodic | 1 | 102.6 | 207.5 | 13.0 | 78 | 71.0 | 7.0 | 6.0 | 1.0 | - | 139.3 | 22.0 |
| bike_abrupt | static | 1 | 138.3 | 271.6 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 211.3 | 23.0 |
| bike_gradual | adaptive | 1 | 112.7 | 211.3 | 6.0 | 36 | 29.8 | 4.0 | 2.0 | 0.0 | 50.0 | 132.3 | 21.0 |
| bike_gradual | periodic | 1 | 103.5 | 197.3 | 13.0 | 78 | 70.7 | 10.0 | 3.0 | 1.0 | - | 117.7 | 0.0 |
| bike_gradual | static | 1 | 136.8 | 260.0 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 156.6 | 21.0 |
| bike_unmodified | adaptive | 1 | 72.5 | 123.6 | 3.0 | 18 | 16.5 | 2.0 | 1.0 | 0.0 | - | - | - |
| bike_unmodified | periodic | 1 | 67.9 | 117.7 | 13.0 | 78 | 70.9 | 7.0 | 6.0 | 2.0 | - | - | - |
| bike_unmodified | static | 1 | 82.0 | 133.8 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - |
| synthetic_abrupt | adaptive | 1 | 56.4 | 115.7 | 3.0 | 18 | 13.3 | 1.0 | 2.0 | 0.0 | 15.0 | 69.6 | - |
| synthetic_abrupt | periodic | 1 | 54.9 | 111.4 | 8.0 | 48 | 49.6 | 3.0 | 5.0 | 0.0 | - | 68.0 | - |
| synthetic_abrupt | static | 1 | 57.7 | 119.1 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 71.9 | - |
| synthetic_stationary | adaptive | 1 | 35.7 | 61.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - |
| synthetic_stationary | periodic | 1 | 35.6 | 61.1 | 8.0 | 48 | 51.6 | 1.0 | 7.0 | 0.0 | - | - | - |
| synthetic_stationary | static | 1 | 35.7 | 61.4 | 0.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - |

Missed detections (adaptive, injected-change scenarios, 90-day horizon): 0 run(s).
Recovery '-' means the defined recovery criterion was never met within the replay.