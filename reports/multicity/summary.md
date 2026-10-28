# Multi-city evaluation

MAE in trips/hour. `clean` = never used for design decisions (confirmatory). Compute = measured training + probe seconds. Negative 'vs' = lower error.

## clean: MAE relative to static and to periodic-28

| scenario | policy | MAE | vs static | vs periodic-28 | cycles | compute s | compute vs p28 |
|---|---|---|---|---|---|---|---|
| city_chicago_abrupt | periodic-14 | 132.1 | -55.6% | -5.8% | 141.0 | 650.5 | 1.83x |
| city_chicago_abrupt | adaptive-bias | 136.0 | -54.3% | -3.0% | 61.0 | 316.2 | 0.89x |
| city_chicago_abrupt | periodic-28 | 140.2 | -52.9% | +0.0% | 78.0 | 355.0 | 1.00x |
| city_chicago_abrupt | probe | 141.4 | -52.5% | +0.9% | 34.0 | 244.2 | 0.69x |
| city_chicago_abrupt | periodic-56 | 149.3 | -49.8% | +6.5% | 39.0 | 197.5 | 0.56x |
| city_chicago_abrupt | adaptive-ph | 152.2 | -48.9% | +8.5% | 27.0 | 142.2 | 0.40x |
| city_chicago_abrupt | periodic-91 | 165.3 | -44.4% | +17.9% | 24.0 | 127.0 | 0.36x |
| city_chicago_abrupt | adaptive-kswin | 237.7 | -20.1% | +69.6% | 9.0 | 46.6 | 0.13x |
| city_chicago_abrupt | adaptive | 247.7 | -16.7% | +76.7% | 6.0 | 35.0 | 0.10x |
| city_chicago_abrupt | static | 297.5 | +0.0% | +112.2% | 0.0 | 0.0 | 0.00x |
| city_chicago_abrupt | oracle | 411.2 | +38.2% | +193.3% | 3.0 | 14.7 | 0.04x |
| city_chicago_unmodified | periodic-14 | 112.3 | -46.8% | -4.4% | 140.0 | 638.1 | 1.79x |
| city_chicago_unmodified | probe-no-probation | 115.5 | -45.3% | -1.7% | 39.0 | 278.2 | 0.78x |
| city_chicago_unmodified | probe-no-test | 115.6 | -45.2% | -1.6% | 43.0 | 296.3 | 0.83x |
| city_chicago_unmodified | adaptive-bias | 117.2 | -44.4% | -0.2% | 60.0 | 316.4 | 0.89x |
| city_chicago_unmodified | periodic-28 | 117.5 | -44.3% | +0.0% | 78.0 | 355.5 | 1.00x |
| city_chicago_unmodified | probe | 118.0 | -44.1% | +0.5% | 35.0 | 254.7 | 0.72x |
| city_chicago_unmodified | probe-no-accel | 120.8 | -42.8% | +2.8% | 36.0 | 258.9 | 0.73x |
| city_chicago_unmodified | periodic-56 | 126.6 | -40.0% | +7.8% | 39.0 | 197.5 | 0.56x |
| city_chicago_unmodified | periodic-91 | 150.5 | -28.7% | +28.2% | 24.0 | 128.7 | 0.36x |
| city_chicago_unmodified | adaptive | 194.3 | -7.9% | +65.4% | 12.0 | 64.9 | 0.18x |
| city_chicago_unmodified | adaptive-no-warmstart | 194.3 | -7.9% | +65.4% | 12.0 | 66.0 | 0.19x |
| city_chicago_unmodified | static | 211.0 | +0.0% | +79.7% | 0.0 | 0.0 | 0.00x |
| city_chicago_unmodified | adaptive-ph | 227.6 | +7.9% | +93.8% | 12.0 | 66.7 | 0.19x |
| city_chicago_unmodified | adaptive-kswin | 228.7 | +8.4% | +94.7% | 9.0 | 46.5 | 0.13x |
| city_chicago_unmodified | adaptive-no-seasonal | 251.7 | +19.3% | +114.3% | 10.0 | 52.9 | 0.15x |
| city_dc_unmodified | periodic-14 | 128.3 | -62.2% | -4.9% | 14.0 | 64.0 | 1.77x |
| city_dc_unmodified | probe-no-test | 130.4 | -61.5% | -3.3% | 6.0 | 38.0 | 1.05x |
| city_dc_unmodified | probe | 130.7 | -61.5% | -3.1% | 5.0 | 31.6 | 0.87x |
| city_dc_unmodified | probe-no-accel | 134.6 | -60.3% | -0.2% | 3.0 | 20.2 | 0.56x |
| city_dc_unmodified | periodic-28 | 134.9 | -60.2% | +0.0% | 8.0 | 36.2 | 1.00x |
| city_dc_unmodified | probe-no-probation | 135.3 | -60.1% | +0.4% | 6.0 | 43.5 | 1.20x |
| city_dc_unmodified | adaptive-bias | 140.0 | -58.7% | +3.8% | 6.0 | 29.7 | 0.82x |
| city_dc_unmodified | adaptive-ph | 142.2 | -58.1% | +5.4% | 4.0 | 22.6 | 0.62x |
| city_dc_unmodified | adaptive-no-warmstart | 146.8 | -56.7% | +8.8% | 5.0 | 28.9 | 0.80x |
| city_dc_unmodified | adaptive-kswin | 147.4 | -56.5% | +9.3% | 5.0 | 24.6 | 0.68x |
| city_dc_unmodified | adaptive | 147.6 | -56.5% | +9.4% | 4.0 | 22.5 | 0.62x |
| city_dc_unmodified | periodic-56 | 162.5 | -52.1% | +20.5% | 4.0 | 22.6 | 0.62x |
| city_dc_unmodified | adaptive-no-seasonal | 201.7 | -40.5% | +49.5% | 1.0 | 6.0 | 0.17x |
| city_dc_unmodified | periodic-91 | 207.9 | -38.7% | +54.2% | 2.0 | 10.7 | 0.30x |
| city_dc_unmodified | static | 339.1 | +0.0% | +151.4% | 0.0 | 0.0 | 0.00x |
| city_nyc_abrupt | periodic-14 | 731.4 | -67.1% | -3.9% | 138.0 | 640.4 | 1.72x |
| city_nyc_abrupt | probe | 757.1 | -66.0% | -0.6% | 49.0 | 345.9 | 0.93x |
| city_nyc_abrupt | periodic-28 | 761.3 | -65.8% | +0.0% | 78.0 | 371.3 | 1.00x |
| city_nyc_abrupt | adaptive-bias | 797.0 | -64.2% | +4.7% | 62.0 | 338.6 | 0.91x |
| city_nyc_abrupt | periodic-56 | 833.8 | -62.5% | +9.5% | 39.0 | 203.4 | 0.55x |
| city_nyc_abrupt | periodic-91 | 931.9 | -58.1% | +22.4% | 24.0 | 130.4 | 0.35x |
| city_nyc_abrupt | adaptive-kswin | 1364.9 | -38.7% | +79.3% | 15.0 | 80.7 | 0.22x |
| city_nyc_abrupt | adaptive-ph | 1370.4 | -38.4% | +80.0% | 7.0 | 35.3 | 0.09x |
| city_nyc_abrupt | adaptive | 1371.0 | -38.4% | +80.1% | 8.0 | 42.9 | 0.12x |
| city_nyc_abrupt | static | 2225.3 | +0.0% | +192.3% | 0.0 | 0.0 | 0.00x |
| city_nyc_abrupt | oracle | 2400.7 | +7.9% | +215.3% | 3.0 | 15.9 | 0.04x |
| city_nyc_unmodified | periodic-14 | 591.0 | -63.7% | -3.6% | 138.0 | 653.3 | 1.76x |
| city_nyc_unmodified | probe-no-test | 603.6 | -63.0% | -1.6% | 57.0 | 387.3 | 1.04x |
| city_nyc_unmodified | probe-no-probation | 612.7 | -62.4% | -0.1% | 50.0 | 365.6 | 0.98x |
| city_nyc_unmodified | periodic-28 | 613.1 | -62.4% | +0.0% | 78.0 | 371.2 | 1.00x |
| city_nyc_unmodified | probe-no-accel | 626.2 | -61.6% | +2.1% | 47.0 | 323.5 | 0.87x |
| city_nyc_unmodified | probe | 633.2 | -61.1% | +3.3% | 48.0 | 329.9 | 0.89x |
| city_nyc_unmodified | adaptive-bias | 634.1 | -61.1% | +3.4% | 63.0 | 343.6 | 0.93x |
| city_nyc_unmodified | periodic-56 | 663.7 | -59.3% | +8.2% | 39.0 | 206.5 | 0.56x |
| city_nyc_unmodified | periodic-91 | 768.2 | -52.8% | +25.3% | 24.0 | 126.7 | 0.34x |
| city_nyc_unmodified | adaptive-kswin | 1024.7 | -37.1% | +67.1% | 16.0 | 84.5 | 0.23x |
| city_nyc_unmodified | adaptive-ph | 1030.8 | -36.7% | +68.1% | 13.0 | 67.4 | 0.18x |
| city_nyc_unmodified | adaptive | 1046.3 | -35.8% | +70.6% | 13.0 | 69.5 | 0.19x |
| city_nyc_unmodified | adaptive-no-warmstart | 1047.4 | -35.7% | +70.8% | 11.0 | 60.8 | 0.16x |
| city_nyc_unmodified | adaptive-no-seasonal | 1069.4 | -34.4% | +74.4% | 11.0 | 57.7 | 0.16x |
| city_nyc_unmodified | static | 1629.1 | +0.0% | +165.7% | 0.0 | 0.0 | 0.00x |
| city_sf_abrupt | periodic-14 | 76.4 | -55.5% | -5.4% | 112.0 | 495.1 | 1.70x |
| city_sf_abrupt | adaptive-bias | 78.0 | -54.6% | -3.4% | 53.0 | 282.0 | 0.97x |
| city_sf_abrupt | probe | 79.4 | -53.8% | -1.7% | 51.0 | 326.9 | 1.13x |
| city_sf_abrupt | periodic-28 | 80.8 | -53.0% | +0.0% | 65.0 | 290.5 | 1.00x |
| city_sf_abrupt | adaptive | 86.0 | -49.9% | +6.4% | 31.0 | 160.2 | 0.55x |
| city_sf_abrupt | adaptive-ph | 87.8 | -48.9% | +8.7% | 28.0 | 147.8 | 0.51x |
| city_sf_abrupt | adaptive-kswin | 89.0 | -48.2% | +10.1% | 26.0 | 132.1 | 0.45x |
| city_sf_abrupt | periodic-56 | 93.6 | -45.5% | +15.8% | 32.0 | 156.8 | 0.54x |
| city_sf_abrupt | periodic-91 | 94.1 | -45.2% | +16.5% | 20.0 | 93.9 | 0.32x |
| city_sf_abrupt | static | 171.7 | +0.0% | +112.6% | 0.0 | 0.0 | 0.00x |
| city_sf_abrupt | oracle | 188.6 | +9.8% | +133.5% | 3.0 | 15.2 | 0.05x |
| city_sf_unmodified | periodic-14 | 66.4 | -49.8% | -4.6% | 112.0 | 498.0 | 1.74x |
| city_sf_unmodified | adaptive-bias | 67.1 | -49.3% | -3.6% | 55.0 | 279.6 | 0.98x |
| city_sf_unmodified | probe-no-accel | 67.1 | -49.2% | -3.5% | 53.0 | 322.8 | 1.13x |
| city_sf_unmodified | probe-no-probation | 67.8 | -48.7% | -2.5% | 51.0 | 321.8 | 1.12x |
| city_sf_unmodified | probe-no-test | 68.3 | -48.3% | -1.8% | 64.0 | 385.3 | 1.35x |
| city_sf_unmodified | periodic-28 | 69.6 | -47.4% | +0.0% | 65.0 | 286.1 | 1.00x |
| city_sf_unmodified | probe | 70.5 | -46.7% | +1.3% | 51.0 | 314.1 | 1.10x |
| city_sf_unmodified | adaptive-ph | 75.1 | -43.2% | +8.0% | 33.0 | 161.1 | 0.56x |
| city_sf_unmodified | adaptive-kswin | 76.3 | -42.3% | +9.7% | 26.0 | 128.0 | 0.45x |
| city_sf_unmodified | adaptive-no-warmstart | 77.8 | -41.1% | +11.9% | 24.0 | 118.2 | 0.41x |
| city_sf_unmodified | adaptive | 78.1 | -41.0% | +12.2% | 21.0 | 102.1 | 0.36x |
| city_sf_unmodified | periodic-56 | 80.8 | -38.9% | +16.1% | 32.0 | 155.5 | 0.54x |
| city_sf_unmodified | periodic-91 | 82.8 | -37.4% | +19.0% | 20.0 | 97.1 | 0.34x |
| city_sf_unmodified | adaptive-no-seasonal | 95.9 | -27.5% | +37.8% | 27.0 | 134.1 | 0.47x |
| city_sf_unmodified | static | 132.2 | +0.0% | +90.0% | 0.0 | 0.0 | 0.00x |

Mean over clean scenarios (n = scenarios per policy; ablation variants are compared with their parent below):

| policy | n | vs static | vs periodic-28 | compute vs p28 |
|---|---|---|---|---|
| periodic-14 | 7.0 | -57.2% | -4.7% | 1.76x |
| periodic-28 | 7.0 | -55.1% | +0.0% | 1.00x |
| probe | 7.0 | -55.1% | +0.1% | 0.90x |
| adaptive-bias | 7.0 | -55.2% | +0.2% | 0.91x |
| periodic-56 | 7.0 | -49.7% | +12.1% | 0.56x |
| periodic-91 | 7.0 | -43.6% | +26.2% | 0.34x |
| adaptive-ph | 7.0 | -38.0% | +38.9% | 0.37x |
| adaptive | 7.0 | -35.2% | +45.8% | 0.30x |
| adaptive-kswin | 7.0 | -33.5% | +48.5% | 0.33x |
| static | 7.0 | +0.0% | +129.1% | 0.00x |
| oracle | 3.0 | +18.6% | +180.7% | 0.05x |

## dc_exploratory: MAE relative to static and to periodic-28

| scenario | policy | MAE | vs static | vs periodic-28 | cycles | compute s | compute vs p28 |
|---|---|---|---|---|---|---|---|
| bike_abrupt | periodic-14 | 97.9 | -46.8% | -3.3% | 159.0 | 742.9 | 1.60x |
| bike_abrupt | periodic-28 | 101.2 | -45.0% | +0.0% | 91.0 | 463.4 | 1.00x |
| bike_abrupt | probe | 101.5 | -44.8% | +0.4% | 60.0 | 389.5 | 0.84x |
| bike_abrupt | adaptive-bias | 106.4 | -42.2% | +5.1% | 67.0 | 351.4 | 0.76x |
| bike_abrupt | periodic-56 | 109.6 | -40.4% | +8.3% | 45.0 | 237.6 | 0.51x |
| bike_abrupt | periodic-91 | 121.9 | -33.7% | +20.5% | 28.0 | 155.5 | 0.34x |
| bike_abrupt | adaptive | 123.4 | -32.9% | +22.0% | 29.0 | 157.5 | 0.34x |
| bike_abrupt | adaptive-kswin | 127.4 | -30.7% | +25.9% | 35.0 | 188.4 | 0.41x |
| bike_abrupt | adaptive-ph | 127.5 | -30.7% | +26.0% | 35.0 | 186.4 | 0.40x |
| bike_abrupt | oracle | 169.8 | -7.7% | +67.8% | 3.0 | 16.4 | 0.04x |
| bike_abrupt | static | 184.0 | +0.0% | +81.8% | 0.0 | 0.0 | 0.00x |
| bike_gradual | periodic-14 | 96.7 | -46.7% | -4.8% | 160.0 | 742.7 | 1.54x |
| bike_gradual | probe | 100.6 | -44.5% | -1.0% | 56.0 | 342.0 | 0.71x |
| bike_gradual | adaptive-bias | 101.1 | -44.2% | -0.5% | 68.0 | 336.7 | 0.70x |
| bike_gradual | periodic-28 | 101.6 | -44.0% | +0.0% | 91.0 | 481.4 | 1.00x |
| bike_gradual | periodic-56 | 108.2 | -40.3% | +6.5% | 45.0 | 239.8 | 0.50x |
| bike_gradual | adaptive-kswin | 111.4 | -38.6% | +9.7% | 40.0 | 200.8 | 0.42x |
| bike_gradual | adaptive | 116.2 | -35.9% | +14.4% | 29.0 | 149.1 | 0.31x |
| bike_gradual | periodic-91 | 121.4 | -33.1% | +19.5% | 28.0 | 145.6 | 0.30x |
| bike_gradual | adaptive-ph | 125.8 | -30.6% | +23.9% | 33.0 | 169.6 | 0.35x |
| bike_gradual | oracle | 169.3 | -6.6% | +66.7% | 3.0 | 14.8 | 0.03x |
| bike_gradual | static | 181.3 | +0.0% | +78.5% | 0.0 | 0.0 | 0.00x |
| bike_unmodified | periodic-14 | 78.6 | -42.5% | -3.7% | 162.0 | 755.7 | 1.68x |
| bike_unmodified | periodic-28 | 81.5 | -40.3% | +0.0% | 91.0 | 449.5 | 1.00x |
| bike_unmodified | probe | 82.2 | -39.8% | +0.8% | 50.0 | 357.4 | 0.80x |
| bike_unmodified | adaptive-bias | 84.5 | -38.2% | +3.6% | 63.0 | 340.0 | 0.76x |
| bike_unmodified | periodic-56 | 86.1 | -37.0% | +5.6% | 45.0 | 234.8 | 0.52x |
| bike_unmodified | periodic-91 | 95.9 | -29.7% | +17.7% | 28.0 | 153.1 | 0.34x |
| bike_unmodified | adaptive-ph | 103.3 | -24.4% | +26.6% | 33.0 | 181.0 | 0.40x |
| bike_unmodified | adaptive | 114.7 | -16.0% | +40.6% | 22.0 | 121.3 | 0.27x |
| bike_unmodified | static | 136.6 | +0.0% | +67.5% | 0.0 | 0.0 | 0.00x |
| bike_unmodified | adaptive-kswin | 138.3 | +1.3% | +69.6% | 18.0 | 98.4 | 0.22x |

Mean over dc_exploratory scenarios (n = scenarios per policy; ablation variants are compared with their parent below):

| policy | n | vs static | vs periodic-28 | compute vs p28 |
|---|---|---|---|---|
| periodic-14 | 3.0 | -45.3% | -3.9% | 1.61x |
| periodic-28 | 3.0 | -43.1% | +0.0% | 1.00x |
| probe | 3.0 | -43.0% | +0.1% | 0.78x |
| adaptive-bias | 3.0 | -41.5% | +2.8% | 0.74x |
| periodic-56 | 3.0 | -39.2% | +6.8% | 0.51x |
| periodic-91 | 3.0 | -32.2% | +19.2% | 0.33x |
| adaptive-ph | 3.0 | -28.6% | +25.5% | 0.39x |
| adaptive | 3.0 | -28.3% | +25.7% | 0.31x |
| adaptive-kswin | 3.0 | -22.7% | +35.1% | 0.35x |
| oracle | 2.0 | -7.2% | +67.2% | 0.03x |
| static | 3.0 | +0.0% | +75.9% | 0.00x |

## Paired tests (daily MAE, A - B; block-bootstrap 95 % CI; Diebold-Mariano)

| group | scenario | seed | A | B | days | MAE A | MAE B | diff | 95 % CI | DM p |
|---|---|---|---|---|---|---|---|---|---|---|
| clean | city_chicago_abrupt |  | adaptive-bias | periodic-28 | 2192 | 135.9 | 140.2 | -4.24 | [-13.93, +3.08] | 0.167 |
| clean | city_chicago_abrupt |  | probe | adaptive | 2192 | 141.4 | 247.7 | -106.28 | [-131.29, -86.03] | 0.000 |
| clean | city_chicago_abrupt |  | probe | periodic-14 | 2192 | 141.4 | 132.1 | +9.35 | [+4.48, +15.98] | 0.000 |
| clean | city_chicago_abrupt |  | probe | periodic-28 | 2192 | 141.4 | 140.2 | +1.24 | [-8.23, +10.32] | 0.740 |
| clean | city_chicago_abrupt |  | probe | static | 2192 | 141.4 | 297.5 | -156.04 | [-194.18, -123.65] | 0.000 |
| clean | city_chicago_unmodified |  | adaptive-bias | periodic-28 | 2192 | 117.2 | 117.5 | -0.22 | [-8.25, +6.72] | 0.940 |
| clean | city_chicago_unmodified |  | probe | adaptive | 2192 | 118.0 | 194.3 | -76.32 | [-103.32, -53.90] | 0.000 |
| clean | city_chicago_unmodified |  | probe | periodic-14 | 2192 | 118.0 | 112.3 | +5.70 | [+2.12, +9.79] | 0.000 |
| clean | city_chicago_unmodified |  | probe | periodic-28 | 2192 | 118.0 | 117.5 | +0.53 | [-6.89, +6.83] | 0.851 |
| clean | city_chicago_unmodified |  | probe | static | 2192 | 118.0 | 211.0 | -93.03 | [-114.24, -74.32] | 0.000 |
| clean | city_dc_unmodified |  | adaptive-bias | periodic-28 | 238 | 140.0 | 134.9 | +5.12 | [-10.76, +27.63] | 0.481 |
| clean | city_dc_unmodified |  | probe | adaptive | 238 | 130.6 | 147.6 | -16.95 | [-28.52, -4.76] | 0.004 |
| clean | city_dc_unmodified |  | probe | periodic-14 | 238 | 130.6 | 128.3 | +2.37 | [-6.50, +13.66] | 0.547 |
| clean | city_dc_unmodified |  | probe | periodic-28 | 238 | 130.6 | 134.9 | -4.22 | [-16.17, +7.05] | 0.371 |
| clean | city_dc_unmodified |  | probe | static | 238 | 130.6 | 339.1 | -208.41 | [-260.12, -183.90] | 0.000 |
| clean | city_nyc_abrupt |  | adaptive-bias | periodic-28 | 2192 | 797.0 | 761.3 | +35.71 | [-1.34, +77.07] | 0.013 |
| clean | city_nyc_abrupt |  | probe | adaptive | 2192 | 757.1 | 1370.9 | -613.83 | [-788.49, -470.40] | 0.000 |
| clean | city_nyc_abrupt |  | probe | periodic-14 | 2192 | 757.1 | 731.3 | +25.72 | [+7.95, +45.78] | 0.001 |
| clean | city_nyc_abrupt |  | probe | periodic-28 | 2192 | 757.1 | 761.3 | -4.21 | [-22.50, +18.60] | 0.644 |
| clean | city_nyc_abrupt |  | probe | static | 2192 | 757.1 | 2225.1 | -1468.09 | [-1779.71, -1202.04] | 0.000 |
| clean | city_nyc_unmodified |  | adaptive-bias | periodic-28 | 2192 | 634.1 | 613.1 | +20.96 | [-2.70, +47.82] | 0.027 |
| clean | city_nyc_unmodified |  | probe | adaptive | 2192 | 633.1 | 1046.3 | -413.12 | [-521.27, -325.20] | 0.000 |
| clean | city_nyc_unmodified |  | probe | periodic-14 | 2192 | 633.1 | 590.9 | +42.21 | [+25.04, +66.01] | 0.000 |
| clean | city_nyc_unmodified |  | probe | periodic-28 | 2192 | 633.1 | 613.1 | +20.03 | [-2.94, +49.81] | 0.051 |
| clean | city_nyc_unmodified |  | probe | static | 2192 | 633.1 | 1629.1 | -995.92 | [-1216.34, -804.65] | 0.000 |
| clean | city_sf_abrupt |  | adaptive-bias | periodic-28 | 1827 | 78.0 | 80.8 | -2.73 | [-7.03, +1.86] | 0.117 |
| clean | city_sf_abrupt |  | probe | adaptive | 1827 | 79.4 | 86.0 | -6.55 | [-14.08, +0.63] | 0.016 |
| clean | city_sf_abrupt |  | probe | periodic-14 | 1827 | 79.4 | 76.4 | +3.05 | [-0.82, +7.56] | 0.045 |
| clean | city_sf_abrupt |  | probe | periodic-28 | 1827 | 79.4 | 80.8 | -1.35 | [-6.49, +5.17] | 0.539 |
| clean | city_sf_abrupt |  | probe | static | 1827 | 79.4 | 171.7 | -92.31 | [-114.14, -71.48] | 0.000 |
| clean | city_sf_unmodified |  | adaptive-bias | periodic-28 | 1827 | 67.1 | 69.6 | -2.50 | [-6.28, +1.31] | 0.103 |
| clean | city_sf_unmodified |  | probe | adaptive | 1827 | 70.5 | 78.1 | -7.60 | [-16.12, +0.15] | 0.007 |
| clean | city_sf_unmodified |  | probe | periodic-14 | 1827 | 70.5 | 66.4 | +4.05 | [-0.02, +8.46] | 0.007 |
| clean | city_sf_unmodified |  | probe | periodic-28 | 1827 | 70.5 | 69.6 | +0.88 | [-4.26, +7.27] | 0.679 |
| clean | city_sf_unmodified |  | probe | static | 1827 | 70.5 | 132.2 | -61.74 | [-77.45, -45.78] | 0.000 |
| dc_exploratory | bike_abrupt |  | adaptive-bias | periodic-28 | 2557 | 106.4 | 101.2 | +5.21 | [+1.10, +10.43] | 0.001 |
| dc_exploratory | bike_abrupt |  | probe | adaptive | 2557 | 101.5 | 123.4 | -21.89 | [-27.28, -16.55] | 0.000 |
| dc_exploratory | bike_abrupt |  | probe | periodic-14 | 2557 | 101.5 | 97.9 | +3.67 | [+0.91, +6.61] | 0.002 |
| dc_exploratory | bike_abrupt |  | probe | periodic-28 | 2557 | 101.5 | 101.2 | +0.35 | [-2.02, +3.03] | 0.751 |
| dc_exploratory | bike_abrupt |  | probe | static | 2557 | 101.5 | 184.0 | -82.44 | [-107.34, -58.92] | 0.000 |
| dc_exploratory | bike_gradual |  | adaptive-bias | periodic-28 | 2557 | 101.1 | 101.6 | -0.48 | [-2.92, +2.29] | 0.661 |
| dc_exploratory | bike_gradual |  | probe | adaptive | 2557 | 100.6 | 116.2 | -15.65 | [-20.14, -10.88] | 0.000 |
| dc_exploratory | bike_gradual |  | probe | periodic-14 | 2557 | 100.6 | 96.7 | +3.93 | [+1.38, +6.53] | 0.000 |
| dc_exploratory | bike_gradual |  | probe | periodic-28 | 2557 | 100.6 | 101.6 | -0.99 | [-3.66, +1.85] | 0.361 |
| dc_exploratory | bike_gradual |  | probe | static | 2557 | 100.6 | 181.3 | -80.72 | [-106.03, -56.63] | 0.000 |
| dc_exploratory | bike_unmodified |  | adaptive-bias | periodic-28 | 2557 | 84.5 | 81.5 | +2.92 | [+0.50, +5.93] | 0.006 |
| dc_exploratory | bike_unmodified |  | probe | adaptive | 2557 | 82.2 | 114.7 | -32.47 | [-44.61, -22.83] | 0.000 |
| dc_exploratory | bike_unmodified |  | probe | periodic-14 | 2557 | 82.2 | 78.6 | +3.64 | [+1.82, +5.67] | 0.000 |
| dc_exploratory | bike_unmodified |  | probe | periodic-28 | 2557 | 82.2 | 81.5 | +0.66 | [-1.33, +2.91] | 0.465 |
| dc_exploratory | bike_unmodified |  | probe | static | 2557 | 82.2 | 136.6 | -54.36 | [-70.74, -39.70] | 0.000 |
| generated | synthetic_abrupt | 1 | adaptive-bias | periodic-28 | 730 | 46.1 | 46.0 | +0.08 | [-0.48, +0.56] | 0.737 |
| generated | synthetic_abrupt | 2 | adaptive-bias | periodic-28 | 730 | 49.7 | 49.5 | +0.20 | [-0.51, +0.98] | 0.475 |
| generated | synthetic_abrupt | 3 | adaptive-bias | periodic-28 | 730 | 52.4 | 52.6 | -0.13 | [-1.23, +1.00] | 0.763 |
| generated | synthetic_abrupt | 4 | adaptive-bias | periodic-28 | 730 | 47.4 | 47.7 | -0.31 | [-0.75, +0.16] | 0.144 |
| generated | synthetic_abrupt | 5 | adaptive-bias | periodic-28 | 730 | 50.6 | 51.0 | -0.41 | [-1.36, +0.42] | 0.290 |
| generated | synthetic_abrupt | 1 | probe | adaptive | 730 | 46.0 | 55.0 | -9.03 | [-12.64, -5.03] | 0.000 |
| generated | synthetic_abrupt | 2 | probe | adaptive | 730 | 49.7 | 58.9 | -9.19 | [-12.80, -5.24] | 0.000 |
| generated | synthetic_abrupt | 3 | probe | adaptive | 730 | 51.9 | 58.1 | -6.20 | [-8.65, -3.39] | 0.000 |
| generated | synthetic_abrupt | 4 | probe | adaptive | 730 | 47.6 | 55.7 | -8.09 | [-11.40, -4.50] | 0.000 |
| generated | synthetic_abrupt | 5 | probe | adaptive | 730 | 50.5 | 59.7 | -9.21 | [-13.26, -5.04] | 0.000 |
| generated | synthetic_abrupt | 1 | probe | periodic-14 | 730 | 46.0 | 45.7 | +0.27 | [-0.21, +0.79] | 0.233 |
| generated | synthetic_abrupt | 2 | probe | periodic-14 | 730 | 49.7 | 49.3 | +0.47 | [-0.14, +1.22] | 0.113 |
| generated | synthetic_abrupt | 3 | probe | periodic-14 | 730 | 51.9 | 51.8 | +0.15 | [-0.44, +0.75] | 0.540 |
| generated | synthetic_abrupt | 4 | probe | periodic-14 | 730 | 47.6 | 47.6 | +0.08 | [-0.69, +0.65] | 0.773 |
| generated | synthetic_abrupt | 5 | probe | periodic-14 | 730 | 50.5 | 51.1 | -0.61 | [-1.52, +0.17] | 0.103 |
| generated | synthetic_abrupt | 1 | probe | periodic-28 | 730 | 46.0 | 46.0 | -0.04 | [-0.74, +0.60] | 0.885 |
| generated | synthetic_abrupt | 2 | probe | periodic-28 | 730 | 49.7 | 49.5 | +0.25 | [-0.46, +1.02] | 0.404 |
| generated | synthetic_abrupt | 3 | probe | periodic-28 | 730 | 51.9 | 52.6 | -0.64 | [-1.86, +0.30] | 0.125 |
| generated | synthetic_abrupt | 4 | probe | periodic-28 | 730 | 47.6 | 47.7 | -0.06 | [-0.51, +0.46] | 0.801 |
| generated | synthetic_abrupt | 5 | probe | periodic-28 | 730 | 50.5 | 51.0 | -0.50 | [-1.08, -0.03] | 0.071 |
| generated | synthetic_abrupt | 1 | probe | static | 730 | 46.0 | 55.9 | -9.95 | [-13.86, -5.63] | 0.000 |
| generated | synthetic_abrupt | 2 | probe | static | 730 | 49.7 | 59.6 | -9.85 | [-13.91, -5.56] | 0.000 |
| generated | synthetic_abrupt | 3 | probe | static | 730 | 51.9 | 62.2 | -10.24 | [-14.41, -5.60] | 0.000 |
| generated | synthetic_abrupt | 4 | probe | static | 730 | 47.6 | 56.9 | -9.29 | [-12.97, -5.43] | 0.000 |
| generated | synthetic_abrupt | 5 | probe | static | 730 | 50.5 | 61.2 | -10.75 | [-15.58, -6.07] | 0.000 |
| generated | synthetic_stationary | 1 | adaptive-bias | periodic-28 | 730 | 32.8 | 32.8 | +0.06 | [-0.21, +0.30] | 0.658 |
| generated | synthetic_stationary | 2 | adaptive-bias | periodic-28 | 730 | 35.4 | 35.8 | -0.42 | [-1.39, +0.25] | 0.316 |
| generated | synthetic_stationary | 3 | adaptive-bias | periodic-28 | 730 | 36.6 | 36.7 | -0.03 | [-0.35, +0.36] | 0.877 |
| generated | synthetic_stationary | 4 | adaptive-bias | periodic-28 | 730 | 33.4 | 33.4 | +0.04 | [-0.06, +0.14] | 0.588 |
| generated | synthetic_stationary | 5 | adaptive-bias | periodic-28 | 730 | 35.1 | 35.3 | -0.28 | [-0.81, +0.27] | 0.327 |
| generated | synthetic_stationary | 1 | probe | adaptive | 730 | 32.8 | 32.8 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 2 | probe | adaptive | 730 | 35.4 | 35.4 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 3 | probe | adaptive | 730 | 36.6 | 36.6 | -0.04 | [-0.44, +0.34] | 0.790 |
| generated | synthetic_stationary | 4 | probe | adaptive | 730 | 33.4 | 33.4 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 5 | probe | adaptive | 730 | 35.1 | 35.1 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 1 | probe | periodic-14 | 730 | 32.8 | 33.0 | -0.16 | [-0.52, +0.22] | 0.408 |
| generated | synthetic_stationary | 2 | probe | periodic-14 | 730 | 35.4 | 35.5 | -0.15 | [-0.99, +0.41] | 0.699 |
| generated | synthetic_stationary | 3 | probe | periodic-14 | 730 | 36.6 | 36.5 | +0.08 | [-0.18, +0.47] | 0.620 |
| generated | synthetic_stationary | 4 | probe | periodic-14 | 730 | 33.4 | 33.5 | -0.06 | [-0.38, +0.17] | 0.749 |
| generated | synthetic_stationary | 5 | probe | periodic-14 | 730 | 35.1 | 35.5 | -0.40 | [-0.96, +0.18] | 0.176 |
| generated | synthetic_stationary | 1 | probe | periodic-28 | 730 | 32.8 | 32.8 | +0.06 | [-0.21, +0.30] | 0.658 |
| generated | synthetic_stationary | 2 | probe | periodic-28 | 730 | 35.4 | 35.8 | -0.42 | [-1.39, +0.25] | 0.316 |
| generated | synthetic_stationary | 3 | probe | periodic-28 | 730 | 36.6 | 36.7 | -0.07 | [-0.26, +0.15] | 0.539 |
| generated | synthetic_stationary | 4 | probe | periodic-28 | 730 | 33.4 | 33.4 | +0.04 | [-0.06, +0.14] | 0.588 |
| generated | synthetic_stationary | 5 | probe | periodic-28 | 730 | 35.1 | 35.3 | -0.28 | [-0.81, +0.27] | 0.327 |
| generated | synthetic_stationary | 1 | probe | static | 730 | 32.8 | 32.8 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 2 | probe | static | 730 | 35.4 | 35.4 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 3 | probe | static | 730 | 36.6 | 36.6 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 4 | probe | static | 730 | 33.4 | 33.4 | +0.00 | [+0.00, +0.00] | - |
| generated | synthetic_stationary | 5 | probe | static | 730 | 35.1 | 35.1 | +0.00 | [+0.00, +0.00] | - |

## Ablations (clean unmodified)

| scenario | variant | MAE | cycles | compute s | probes | rollbacks |
|---|---|---|---|---|---|---|
| city_chicago_unmodified | adaptive | 194.3 | 12.0 | 64.9 | 0 | 1.0 |
| city_chicago_unmodified | adaptive-no-seasonal | 251.7 | 10.0 | 52.9 | 0 | 0.0 |
| city_chicago_unmodified | adaptive-no-warmstart | 194.3 | 12.0 | 66.0 | 0 | 1.0 |
| city_chicago_unmodified | probe | 118.0 | 35.0 | 254.7 | 158 | 4.0 |
| city_chicago_unmodified | probe-no-accel | 120.8 | 36.0 | 258.9 | 151 | 6.0 |
| city_chicago_unmodified | probe-no-probation | 115.5 | 39.0 | 278.2 | 165 | 0.0 |
| city_chicago_unmodified | probe-no-test | 115.6 | 43.0 | 296.3 | 152 | 9.0 |
| city_dc_unmodified | adaptive | 147.6 | 4.0 | 22.5 | 0 | 1.0 |
| city_dc_unmodified | adaptive-no-seasonal | 201.7 | 1.0 | 6.0 | 0 | 0.0 |
| city_dc_unmodified | adaptive-no-warmstart | 146.8 | 5.0 | 28.9 | 0 | 0.0 |
| city_dc_unmodified | probe | 130.7 | 5.0 | 31.6 | 15 | 1.0 |
| city_dc_unmodified | probe-no-accel | 134.6 | 3.0 | 20.2 | 16 | 0.0 |
| city_dc_unmodified | probe-no-probation | 135.3 | 6.0 | 43.5 | 17 | 0.0 |
| city_dc_unmodified | probe-no-test | 130.4 | 6.0 | 38.0 | 15 | 1.0 |
| city_nyc_unmodified | adaptive | 1046.3 | 13.0 | 69.5 | 0 | 1.0 |
| city_nyc_unmodified | adaptive-no-seasonal | 1069.4 | 11.0 | 57.7 | 0 | 3.0 |
| city_nyc_unmodified | adaptive-no-warmstart | 1047.4 | 11.0 | 60.8 | 0 | 1.0 |
| city_nyc_unmodified | probe | 633.2 | 48.0 | 329.9 | 160 | 7.0 |
| city_nyc_unmodified | probe-no-accel | 626.2 | 47.0 | 323.5 | 147 | 6.0 |
| city_nyc_unmodified | probe-no-probation | 612.7 | 50.0 | 365.6 | 167 | 0.0 |
| city_nyc_unmodified | probe-no-test | 603.6 | 57.0 | 387.3 | 158 | 6.0 |
| city_sf_unmodified | adaptive | 78.1 | 21.0 | 102.1 | 0 | 1.0 |
| city_sf_unmodified | adaptive-no-seasonal | 95.9 | 27.0 | 134.1 | 0 | 4.0 |
| city_sf_unmodified | adaptive-no-warmstart | 77.8 | 24.0 | 118.2 | 0 | 1.0 |
| city_sf_unmodified | probe | 70.5 | 51.0 | 314.1 | 123 | 10.0 |
| city_sf_unmodified | probe-no-accel | 67.1 | 53.0 | 322.8 | 116 | 11.0 |
| city_sf_unmodified | probe-no-probation | 67.8 | 51.0 | 321.8 | 137 | 0.0 |
| city_sf_unmodified | probe-no-test | 68.3 | 64.0 | 385.3 | 122 | 7.0 |

Matched means (each variant and its parent on the same scenarios):

| variant | n | vs parent | vs periodic-28 | cycles | compute vs p28 |
|---|---|---|---|---|---|
| probe-no-accel | 4 | -0.1% | +0.3% | 34.8 | 0.82x |
| probe-no-test | 4 | -2.5% | -2.1% | 42.5 | 1.07x |
| probe-no-probation | 4 | -1.4% | -1.0% | 36.5 | 1.02x |
| adaptive-no-seasonal | 4 | +22.8% | +69.0% | 12.2 | 0.23x |
| adaptive-no-warmstart | 4 | -0.2% | +39.2% | 13.0 | 0.39x |

## Generated scenarios (mean over seeds)

| scenario | policy | MAE (sd) | cycles | compute s | detect d | first retrain d |
|---|---|---|---|---|---|---|
| synthetic_abrupt | periodic-14 | 49.1 (2.5) | 48.4 | 291.6 | - | 8.4 |
| synthetic_abrupt | probe | 49.2 (2.4) | 18.6 | 117.6 | - | 26.4 |
| synthetic_abrupt | adaptive-bias | 49.2 (2.5) | 18.8 | 113.0 | 14.7 | 10.0 |
| synthetic_abrupt | periodic-28 | 49.4 (2.6) | 26.0 | 157.2 | - | 12.0 |
| synthetic_abrupt | periodic-91 | 50.0 (2.5) | 8.0 | 59.5 | - | 33.0 |
| synthetic_abrupt | periodic-56 | 50.0 (2.4) | 13.0 | 91.9 | - | 40.0 |
| synthetic_abrupt | oracle | 56.5 (3.1) | 3.0 | 17.9 | - | 15.0 |
| synthetic_abrupt | adaptive-kswin | 56.7 (2.5) | 1.4 | 11.5 | 37.8 | 37.8 |
| synthetic_abrupt | adaptive-ph | 57.0 (2.7) | 2.4 | 17.8 | 17.6 | 17.6 |
| synthetic_abrupt | adaptive | 57.5 (2.0) | 1.8 | 12.5 | 21.8 | 21.8 |
| synthetic_abrupt | static | 59.2 (2.7) | 0.0 | 0.0 | - | - |
| synthetic_stationary | adaptive-kswin | 34.6 (1.5) | 0.6 | 5.4 | - | - |
| synthetic_stationary | adaptive-ph | 34.6 (1.5) | 0.8 | 6.8 | - | - |
| synthetic_stationary | probe | 34.7 (1.5) | 0.0 | 33.8 | - | - |
| synthetic_stationary | static | 34.7 (1.5) | 0.0 | 0.0 | - | - |
| synthetic_stationary | adaptive | 34.7 (1.5) | 0.6 | 4.8 | - | - |
| synthetic_stationary | adaptive-bias | 34.7 (1.5) | 0.6 | 4.9 | - | - |
| synthetic_stationary | periodic-56 | 34.7 (1.6) | 13.0 | 84.8 | - | - |
| synthetic_stationary | periodic-28 | 34.8 (1.6) | 26.0 | 154.9 | - | - |
| synthetic_stationary | periodic-14 | 34.8 (1.5) | 50.6 | 309.9 | - | - |
| synthetic_stationary | periodic-91 | 34.8 (1.6) | 8.0 | 57.4 | - | - |
