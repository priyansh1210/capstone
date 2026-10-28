# Cost model: cheapest policy for a given price of retraining

Reporting only (re-weights the executed results; nothing is tuned). J = MAE / MAE(periodic-28) + kappa x effective cycles per day;
kappa = price of one full retraining cycle in days of the 28-day schedule's average forecast error. Probes are counted at
their measured compute share of a cycle. Regret = J - best J on the same stream, in % of periodic-28's MAE.

## clean real streams (7)

Cheapest policy on average, by kappa:

- kappa 0 .. 1.41 days: **periodic 14 d**
- kappa 1.41 .. 14.1 days: **probe**
- kappa 14.1 .. 20 days: **periodic 56 d**
- kappa 20 .. 100 days: **periodic 91 d**
- kappa >= 100 days: **static**

If probes cost nothing (the price of a cycle is sign-off or deployment risk, not compute; ties go to the first label):

- kappa 0 .. 1.12 days: periodic 14 d
- kappa 1.12 .. 25.1 days: probe
- kappa 25.1 .. 100 days: periodic 91 d
- kappa >= 100 days: static

Mean regret (% of periodic-28 MAE; wins = streams where the policy is cheapest):

| policy | kappa 0 | kappa 0.5 | kappa 1 | kappa 2 | kappa 5 | kappa 10 | kappa 20 | kappa 50 |
|---|---|---|---|---|---|---|---|---|
| static | 135.4 (0) | 132.4 (0) | 130.1 (0) | 127.1 (0) | 119.0 (0) | 107.4 (0) | 92.5 (0) | 54.7 (1) |
| periodic 14 d | 0.0 (7) | 0.1 (6) | 0.9 (2) | 4.1 (0) | 14.7 (0) | 34.1 (0) | 80.8 (0) | 230.2 (0) |
| periodic 28 d | 4.6 (0) | 3.3 (0) | 2.8 (0) | 3.4 (0) | 5.9 (0) | 11.9 (0) | 32.1 (0) | 100.8 (0) |
| periodic 56 d | 16.8 (0) | 14.7 (0) | 13.3 (0) | 12.1 (0) | 9.3 (0) | 6.4 (0) | 9.0 (1) | 24.2 (0) |
| periodic 91 d | 30.0 (0) | 27.5 (0) | 25.8 (0) | 23.9 (0) | 19.0 (0) | 12.7 (0) | 8.2 (2) | 2.4 (3) |
| ADWIN | 33.6 (0) | 31.1 (0) | 29.4 (0) | 27.6 (0) | 23.0 (0) | 17.1 (3) | 13.6 (2) | 10.4 (1) |
| Page-Hinkley | 25.7 (0) | 23.4 (0) | 21.8 (0) | 20.3 (0) | 16.5 (0) | 12.1 (3) | 11.4 (2) | 16.8 (2) |
| KSWIN | 34.5 (0) | 32.2 (0) | 30.6 (0) | 29.1 (0) | 25.4 (0) | 21.0 (0) | 20.5 (0) | 26.4 (0) |
| ADWIN+bias | 4.3 (0) | 2.7 (1) | 1.8 (3) | 1.7 (3) | 2.2 (3) | 4.7 (0) | 17.9 (0) | 65.6 (0) |
| probe | 4.4 (0) | 2.8 (0) | 1.8 (2) | 1.6 (4) | 1.7 (4) | 3.7 (1) | 15.8 (0) | 60.2 (0) |

## generated stationary (5 seeds)

Cheapest policy on average, by kappa:

- kappa 0 .. 0.501 days: **KSWIN**
- kappa >= 0.501 days: **static**

If probes cost nothing (the price of a cycle is sign-off or deployment risk, not compute; ties go to the first label):

- kappa 0 .. 0.501 days: KSWIN
- kappa >= 0.501 days: probe

Mean regret (% of periodic-28 MAE; wins = streams where the policy is cheapest):

| policy | kappa 0 | kappa 0.5 | kappa 1 | kappa 2 | kappa 5 | kappa 10 | kappa 20 | kappa 50 |
|---|---|---|---|---|---|---|---|---|
| static | 0.2 (1) | 0.0 (4) | 0.0 (4) | 0.0 (4) | 0.0 (5) | 0.0 (5) | 0.0 (5) | 0.0 (5) |
| periodic 14 d | 0.6 (1) | 3.9 (0) | 7.4 (0) | 14.2 (0) | 35.1 (0) | 69.7 (0) | 138.7 (0) | 347.8 (0) |
| periodic 28 d | 0.6 (1) | 2.2 (0) | 4.0 (0) | 7.5 (0) | 18.2 (0) | 36.0 (0) | 71.4 (0) | 178.9 (0) |
| periodic 56 d | 0.4 (0) | 1.1 (0) | 2.0 (0) | 3.7 (0) | 9.1 (0) | 18.0 (0) | 35.7 (0) | 89.4 (0) |
| periodic 91 d | 0.7 (1) | 1.1 (0) | 1.6 (0) | 2.7 (0) | 6.0 (0) | 11.5 (0) | 22.4 (0) | 55.4 (0) |
| ADWIN | 0.2 (1) | 0.1 (2) | 0.1 (2) | 0.2 (2) | 0.4 (3) | 0.8 (3) | 1.7 (3) | 4.1 (3) |
| Page-Hinkley | 0.2 (2) | 0.1 (3) | 0.1 (3) | 0.2 (3) | 0.5 (2) | 1.1 (2) | 2.1 (2) | 5.5 (2) |
| KSWIN | 0.2 (2) | 0.1 (4) | 0.1 (4) | 0.1 (4) | 0.4 (3) | 0.8 (3) | 1.6 (3) | 4.1 (3) |
| ADWIN+bias | 0.2 (1) | 0.1 (2) | 0.1 (2) | 0.2 (2) | 0.4 (3) | 0.8 (3) | 1.7 (3) | 4.1 (3) |
| probe | 0.2 (1) | 0.4 (0) | 0.7 (0) | 1.4 (0) | 3.4 (0) | 6.8 (0) | 13.6 (0) | 34.3 (0) |

## generated abrupt (5 seeds)

Cheapest policy on average, by kappa:

- kappa 0 .. 0.0447 days: **periodic 14 d**
- kappa 0.0447 .. 0.562 days: **probe**
- kappa 0.562 .. 1 days: **ADWIN+bias**
- kappa 1 .. 15.8 days: **periodic 91 d**
- kappa 15.8 .. 28.2 days: **KSWIN**
- kappa >= 28.2 days: **static**

If probes cost nothing (the price of a cycle is sign-off or deployment risk, not compute; ties go to the first label):

- kappa 0 .. 0.0447 days: periodic 14 d
- kappa 0.0447 .. 1.12 days: probe
- kappa 1.12 .. 15.8 days: periodic 91 d
- kappa 15.8 .. 28.2 days: KSWIN
- kappa >= 28.2 days: static

Mean regret (% of periodic-28 MAE; wins = streams where the policy is cheapest):

| policy | kappa 0 | kappa 0.5 | kappa 1 | kappa 2 | kappa 5 | kappa 10 | kappa 20 | kappa 50 |
|---|---|---|---|---|---|---|---|---|
| static | 20.8 (0) | 19.2 (0) | 18.0 (0) | 16.5 (0) | 13.2 (0) | 8.0 (0) | 1.7 (1) | 0.4 (4) |
| periodic 14 d | 0.3 (3) | 2.0 (0) | 4.2 (0) | 9.3 (0) | 26.0 (0) | 53.8 (0) | 113.5 (0) | 312.2 (0) |
| periodic 28 d | 0.9 (0) | 1.0 (0) | 1.7 (0) | 3.7 (0) | 11.1 (0) | 23.7 (0) | 52.9 (0) | 158.9 (0) |
| periodic 56 d | 2.3 (0) | 1.6 (1) | 1.3 (1) | 1.5 (0) | 3.6 (0) | 7.3 (0) | 18.7 (0) | 71.1 (0) |
| periodic 91 d | 2.1 (0) | 1.0 (0) | 0.4 (2) | 0.0 (4) | 0.0 (5) | 0.3 (4) | 4.9 (0) | 36.6 (0) |
| ADWIN | 17.5 (0) | 16.0 (0) | 15.0 (0) | 13.7 (0) | 11.1 (0) | 7.1 (0) | 3.3 (0) | 9.4 (0) |
| Page-Hinkley | 16.5 (0) | 15.1 (0) | 14.1 (0) | 12.9 (0) | 10.6 (0) | 7.0 (0) | 4.0 (0) | 12.6 (0) |
| KSWIN | 15.8 (0) | 14.3 (0) | 13.3 (0) | 11.9 (0) | 9.2 (0) | 4.9 (1) | 0.6 (4) | 5.0 (1) |
| ADWIN+bias | 0.6 (1) | 0.3 (2) | 0.4 (1) | 1.5 (1) | 6.0 (0) | 13.6 (0) | 33.0 (0) | 109.3 (0) |
| probe | 0.5 (1) | 0.3 (2) | 0.6 (1) | 1.9 (0) | 7.3 (0) | 16.4 (0) | 38.7 (0) | 124.0 (0) |
