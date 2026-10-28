# Post-hoc variant vs frozen benchmark (exploratory)

Variant: reference cap = None, bias trigger = 0.15 (chosen on development scenarios).

| scenario | policy | MAE | RMSE | cycles | train s | promo | reject | rollback | detect d | excess log-err 120 d | recovery d |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bike_abrupt | adaptive | 123.4 | 213.7 | 29.0 | 88.5 | 27.0 | 2.0 | 3.0 | 15.0 | 31 % | 237 |
| bike_abrupt | adaptive+ (post-hoc) | 106.4 | 186.8 | 67.0 | 233.3 | 59.0 | 8.0 | 7.0 | 15.0 | 37 % | 278 |
| bike_abrupt | periodic | 101.2 | 181.6 | 91.0 | 356.2 | 77.0 | 14.0 | 7.0 | - | 31 % | 101 |
| bike_abrupt | static | 184.0 | 353.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 42 % | 269 |
| bike_gradual | adaptive | 116.2 | 201.3 | 29.0 | 90.0 | 27.0 | 2.0 | 1.0 | - | 22 % | 190 |
| bike_gradual | adaptive+ (post-hoc) | 101.1 | 177.5 | 68.0 | 232.8 | 61.0 | 7.0 | 7.0 | - | 17 % | 114 |
| bike_gradual | periodic | 101.6 | 180.9 | 91.0 | 358.5 | 77.0 | 14.0 | 8.0 | - | 22 % | 94 |
| bike_gradual | static | 181.3 | 349.1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 39 % | 116 |
| bike_unmodified | adaptive | 114.7 | 186.3 | 22.0 | 69.5 | 19.0 | 3.0 | 3.0 | - | - | - |
| bike_unmodified | adaptive+ (post-hoc) | 84.5 | 140.2 | 63.0 | 220.2 | 56.0 | 7.0 | 10.0 | - | - | - |
| bike_unmodified | periodic | 81.5 | 136.7 | 91.0 | 361.1 | 65.0 | 26.0 | 10.0 | - | - | - |
| bike_unmodified | static | 136.6 | 228.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - |
| synthetic_abrupt | adaptive | 57.5 | 118.4 | 1.8 | 12.3 | 1.2 | 0.6 | 0.2 | 21.8 | 34 % | - |
| synthetic_abrupt | adaptive+ (post-hoc) | 49.2 | 98.9 | 18.8 | 103.8 | 14.2 | 4.6 | 1.8 | 14.7 | 32 % | 301 |
| synthetic_abrupt | periodic | 49.4 | 99.4 | 26.0 | 189.8 | 13.0 | 13.0 | 1.2 | - | 35 % | 299 |
| synthetic_abrupt | static | 59.2 | 124.5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | - | 35 % | - |
| synthetic_stationary | adaptive | 34.7 | 59.5 | 0.6 | 4.7 | 0.2 | 0.4 | 0.0 | - | - | - |
| synthetic_stationary | adaptive+ (post-hoc) | 34.7 | 59.5 | 0.6 | 5.4 | 0.2 | 0.4 | 0.0 | - | - | - |
| synthetic_stationary | periodic | 34.8 | 60.2 | 26.0 | 207.4 | 3.4 | 22.6 | 0.2 | - | - | - |
| synthetic_stationary | static | 34.7 | 59.4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | - | - | - |