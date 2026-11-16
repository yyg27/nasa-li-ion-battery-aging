# 3.2 Data Preprocessing

The raw data used in this project is the NASA Li-ion Battery Aging Dataset, originally published by the NASA Ames Prognostics Center of Excellence (Saha & Goebel, 2007) and redistributed on Kaggle in tabular CSV form (Mantarain, 2026). The original release stores each battery as a nested MATLAB structure. The Kaggle version flattens these structures into four CSV files, which makes the data easy to load with standard Python tools but also carries over measurement errors and aborted test runs from the original experiments. This section describes the structure of the files, the loading procedure, the cleaning rules that were applied, and the `cycles_left` target variable. All steps are implemented in the script `preprocessing.py`, so the results can be reproduced.

## 3.2.1 Structure of the Dataset

The dataset covers **34 commercial 18650 Li-ion cells** (IDs B0005–B0056, nominal capacity 2 Ah). These cells were repeatedly charged, discharged and characterized with electrochemical impedance spectroscopy (EIS) at ambient temperatures of 4 °C, 22 °C, 24 °C, 43 °C and 44 °C. Each test run is called a *cycle* and is identified by the pair (`battery_id`, `cycle_id`). This pair is the common key that links the four files.

**Table 3.1.** Files of the dataset (raw form).

| File | Rows | Cycles | Content |
|---|---|---|---|
| `meta.csv` | 7,565 | 7,565 | One row per cycle: cycle type, ambient temperature, start time, measured capacity, estimated resistances, completion flag |
| `charge.csv` | 6,512,876 | 2,815 | Time series recorded during charging |
| `discharge.csv` | 770,070 | 2,794 | Time series recorded during discharging |
| `impedance.csv` | 93,888 | 1,956 | EIS spectra, 48 frequency points per cycle |

**Table 3.2.** Columns of the files.

| File | Column | Description |
|---|---|---|
| all | `battery_id`, `cycle_id` | Battery identifier and position of the cycle in the battery's full test sequence (all cycle types) |
| charge, discharge, impedance | `cycle_number` | Counter of charge–discharge cycles of the battery |
| meta | `cycle_type` | `charge`, `discharge` or `impedance` |
| meta | `ambient_temperature` | Ambient temperature of the test chamber (°C) |
| meta | `start_time` | Start date and time of the cycle (ISO 8601) |
| meta | `capacity_ah` | Discharge capacity (Ah); only for discharge cycles |
| meta | `est_electrolyte_res`, `est_charge_trans_res` | Estimated electrolyte resistance R<sub>e</sub> and charge-transfer resistance R<sub>ct</sub> (Ω); only for impedance cycles |
| meta | `complete` | Whether the cycle was completed without interruption |
| charge, discharge | `elapsed_seconds` | Time since the start of the cycle (s) |
| charge, discharge | `voltage_measured`, `current_measured`, `temperature_measured` | Terminal voltage (V), current (A) and cell temperature (°C) |
| charge | `voltage_charge`, `current_charge` | Voltage and current set by the charger |
| discharge | `voltage_load`, `current_load` | Voltage and current measured at the load |
| charge, discharge | `cycles_left` | Number of discharge cycles remaining until the end of the test (see 3.2.4) |
| impedance | `sense_current`, `battery_current`, `Current_ratio`, `Battery_impedance` | Complex-valued EIS quantities stored as text, e.g. `(0.159-0.143j)` |

Testing is not uniform across the cells. The number of discharge cycles per battery varies between 25 and 197, and six cells (B0038–B0040 and B0042–B0044) were tested at two different ambient temperatures.

## 3.2.2 Data Loading

The files were loaded with pandas (McKinney, 2010) and NumPy (Harris et al., 2020). `charge.csv` is about 600 MB, so the PyArrow CSV engine was used to keep loading times short. During loading, three conversions were made:

1. `start_time` was parsed into a datetime type. The source mixes timestamps with and without fractional seconds, so the ISO 8601 parser had to be used.
2. Each complex number in `impedance.csv` was parsed from its text form and split into a real part and an imaginary part. For the battery impedance Z, the magnitude |Z| was also computed. This conversion is needed because machine learning libraries cannot use complex numbers stored as strings.
3. A data profile was produced before any data was removed: missing values, duplicate rows, value ranges, number of samples per cycle and whether time increased within each cycle. The profile found no duplicate rows and no cycle in which time ran backwards. It also confirmed that every cycle in the time-series files has a matching entry in `meta.csv`.

## 3.2.3 Data Cleaning

The profile revealed several types of invalid records. Each was handled with a simple rule chosen from the physical limits of the cells (Table 3.3). Whole cycles were removed from `meta.csv` first. The removed cycles were then removed from the time-series files by an inner join on (`battery_id`, `cycle_id`). Cycles removed later because of their time-series content (steps 6, 9 and 11) were also removed from the metadata. The script ends by checking that every output file lists exactly the same cycles, and it stops with an error if they do not.

**Table 3.3.** Cleaning steps and their effect.

| Step | Rule | Reason | Removed |
|---|---|---|---|
| 1 | Drop cycles with `complete = False` | Interrupted runs; all 25 such discharge cycles also have no capacity value | 34 cycles (25 discharge, 9 impedance) |
| 2 | Drop discharge cycles with `capacity_ah ≤ 0` | A capacity of 0 Ah is physically impossible for a cell that still works and points to a logging failure | 19 cycles |
| 3 | Set R<sub>e</sub> or R<sub>ct</sub> values ≤ 0 Ω or > 10 Ω to missing | Typical values are 0.05–0.3 Ω; the invalid values reach magnitudes of 10<sup>15</sup> Ω or are negative, which shows the impedance model fit failed. They belong to the same 14 cycles that are removed in step 11 | 14 values each |
| 4 | Drop discharge time-series rows of cycles removed in steps 1–2 | Keeps the files consistent | 8,255 rows |
| 5 | Drop discharge rows with `voltage_load` > 10 V | Load voltages up to 97 V are logging glitches. All 4 such rows belonged to cycles already removed in step 4 | 0 rows (after step 4) |
| 6 | Drop discharge cycles with fewer than 10 samples, from both the time series and the metadata | Aborted runs; each of these cycles contains only 9 measurements and a capacity of only about 0.05–0.06 Ah | 12 cycles (108 rows) |
| 7 | Drop charge rows with missing voltage, current or temperature | Sensor dropouts; too few rows to justify interpolation | 257 rows |
| 8 | Drop charge rows with `voltage_measured` > 5 V | Single-sample sensor spikes of 8.1–8.4 V at the start of `cycle_id` 84 of B0005–B0007; a cell never exceeds about 4.2 V in normal use, and the highest remaining readings are short peaks of about 4.98 V in B0050 and B0052 | 3 rows |
| 9 | Drop charge cycles with fewer than 10 samples, from both the time series and the metadata | Same rule as step 6; the final charge cycle of B0005–B0007 was aborted after 5 measurements | 3 cycles (15 rows) |
| 10 | Drop impedance rows of incomplete cycles | Consistency with step 1 | 432 rows |
| 11 | Drop impedance spectrum points with \|Z\| > 10 Ω | Typical \|Z\| is about 0.2 Ω; the extreme values come from measurement artifacts. All 48 points of 14 cycles were invalid, so these cycles were also removed from the metadata | 672 rows (14 cycles) |

After cleaning, the dataset contains **34 batteries, 2,738 valid discharge cycles, 2,812 charge cycles and 1,933 impedance cycles**. A few capacity values above the 2 Ah nominal rating (at most 2.64 Ah, cells B0006, B0036 and B0049–B0051) were kept. They are most likely real measurements rather than logging errors. The most extreme case, B0050, shows an abuse event: in `cycle_id` 10 the cell was discharged down to 0.35 V (capacity 0.03 Ah, the lowest value in the dataset), in the following charge cycle (`cycle_id` 12) it was overcharged (median voltage 4.54 V), and the next discharge delivered 2.64 Ah. These points do not reflect normal aging, so the machine learning stage (Section 3.4) should consider excluding them.

The first discharge of a battery also needs care. In 23 batteries the discharge with `cycle_number` 0 was carried out before the first charge (charge cycles start at `cycle_number` 1). It therefore measures the charge the cell had when it arrived, not its full capacity, and in 19 of these 23 batteries it is lower than the next cycle (for example 0.07 Ah versus 0.69 Ah for B0033). These cycles were kept in the cleaned data because they are valid measurements, but they should be left out when capacity is used as an aging indicator.

## 3.2.4 The `cycles_left` Column

`cycles_left` is the target variable that the Kaggle version provides for remaining useful life (RUL) estimation. It is not documented in the original NASA release, so its definition was reconstructed from the data and then checked against every row:

$$\text{cycles\_left} = \max_{\text{discharge}}(\text{cycle\_number}) - \text{cycle\_number}$$

In other words, `cycles_left` is the number of discharge cycles remaining until the **last discharge cycle that was recorded** for that battery. It reaches 0 at the final discharge. The formula held for every row of both files. In `charge.csv`, 41,061 rows (the final charge cycle of 28 of the 34 batteries) have `cycles_left = −1`, because the test ended with a charge after the last discharge. These rows were kept for completeness but should not be used as RUL training data.

This definition has an important limitation. The NASA documentation defines end of life (EOL) as a 30% fade in rated capacity, from 2 Ah to 1.4 Ah, and states that the experiments were stopped at this point (Saha & Goebel, 2007). The cleaned data does not match this description in either direction. Some cells were cycled well **past** EOL: B0005, for example, first fell below 1.4 Ah at cycle 126 but was tested until cycle 169, so `cycles_left` is still 43 at the cycle where the cell had already reached EOL (59 for B0006, 35 for B0018). Other cells were stopped **before** EOL: B0025–B0032 ended with capacities between 1.56 and 1.77 Ah. `cycles_left` therefore counts down to the point where the experiment was **stopped**, not to the end of the cell's useful life. `cycles_left` is therefore a valid target for the RUL models in Section 3.4, but its values cannot be compared directly between batteries. A threshold-based RUL computed from `capacity_ah` could be used as an alternative target.

## 3.2.5 Output of the Preprocessing Stage

The script writes the cleaned data to the `processed/` folder. The data visualization (Section 3.3) and machine learning (Section 3.4) stages use these files as their input:

| File | Granularity | Use |
|---|---|---|
| `discharge_cycles.csv` | One row per valid discharge cycle: capacity, `cycles_left`, ambient temperature, duration, minimum voltage, maximum temperature | Capacity-fade plots, SOH/RUL models |
| `impedance_cycles.csv` | One row per impedance cycle with R<sub>e</sub> and R<sub>ct</sub> | Plots of R<sub>e</sub>/R<sub>ct</sub> against cycle number |
| `meta_clean.csv` | Cleaned metadata | Joins |
| `discharge_clean.parquet`, `charge_clean.parquet`, `impedance_clean.parquet` | Cleaned raw time series | Voltage–time and temperature plots, feature extraction |

The large time-series files are stored in the Parquet format. Parquet is compressed and stores column types, so the files are smaller on disk and much faster to load than CSV.

---

## About the Authors (paragraph draft)

> **Yusuf Yiğit Gültekin** is a senior student in the Department of Computer Engineering at Çukurova University. In this project, Gültekin was responsible for data preprocessing. This work included analysing the structure of the NASA Li-ion Battery Aging Dataset, developing the Python pipeline that loads, validates and cleans the charge, discharge, impedance and metadata files, and verifying the definition of the `cycles_left` target variable used for remaining useful life estimation.

## References (APA 7)

Harris, C. R., Millman, K. J., van der Walt, S. J., Gommers, R., Virtanen, P., Cournapeau, D., Wieser, E., Taylor, J., Berg, S., Smith, N. J., Kern, R., Picus, M., Hoyer, S., van Kerkwijk, M. H., Brett, M., Haldane, A., del Río, J. F., Wiebe, M., Peterson, P., … Oliphant, T. E. (2020). Array programming with NumPy. *Nature, 585*(7825), 357–362. https://doi.org/10.1038/s41586-020-2649-2

Mantarain. (2026). *NASA Li-ion battery aging datasets* (Version 2) [Data set]. Kaggle. https://www.kaggle.com/datasets/mantarain/nasa-li-ion-battery-aging-datasets

McKinney, W. (2010). Data structures for statistical computing in Python. In S. van der Walt & J. Millman (Eds.), *Proceedings of the 9th Python in Science Conference* (pp. 56–61). https://doi.org/10.25080/Majora-92bf1922-00a

Saha, B., & Goebel, K. (2007). *Battery data set* [Data set]. NASA Prognostics Data Repository, NASA Ames Research Center. https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
## Abbreviations (to send to the editor)

| Abbreviation | Meaning |
|---|---|
| Ah | Ampere-hour |
| CSV | Comma-Separated Values |
| EIS | Electrochemical Impedance Spectroscopy |
| EOL | End of Life |
| ISO | International Organization for Standardization |
| Li-ion | Lithium-ion |
| R<sub>ct</sub> | Charge-transfer resistance |
| R<sub>e</sub> | Electrolyte resistance |
| RUL | Remaining Useful Life |
| SOH | State of Health |
| Z | (Complex) impedance |
