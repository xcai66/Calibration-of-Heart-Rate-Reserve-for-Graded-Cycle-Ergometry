# WEEE implementation decisions

These decisions were made after auditing file names, stage timestamps, and device formats, before calculating agreement or outcome associations.

1. Six five-minute stages are defined from `Study_Information.csv`: sitting, standing, low-intensity cycling, high-intensity cycling, low-intensity running, and high-intensity running. Each stage starts at its recorded timestamp and ends 300 seconds later.
2. `VO2/DataAverage.csv` provides the synchronized indirect-calorimetry outcome and chest-belt heart rate used as the reference signal. Files in `Part1` and `Part2` directories are combined by absolute timestamp and de-duplicated.
3. Zephyr Summary, Empatica E4 HR, and Apple Health `heart_rate` metric records are treated as device signals. Apple timestamps are converted from UTC to Europe/Zurich local time. No device is treated as independent biological replication.
4. The lower anchor is the participant's median reference chest heart rate during the sitting stage. HRmax is `208 - 0.7 x age` because the WEEE protocol was not maximal. The same anchors are applied to every device for that participant.
5. A stage requires at least 80% valid heart-rate temporal coverage after capping intervals at 30 seconds. Valid heart rate is 30–220 beats/min. VO2 values must be positive and cover at least 80% of a stage.
6. Agreement is assessed separately for each device using paired stage scores. Mean bias, MAE, RMSE, and absolute-agreement ICC are reported with participant-cluster bootstrap intervals for bias and MAE.
7. Construct analysis uses leave-one-participant-out prediction of stage mean VO2 in mL/kg/min. The base model includes mean HRR, age, sex, and body mass. The augmented model adds Delta_tilt. Participant-balanced MAE, RMSE, and R-squared are reported. Lambda remains locked at 6.2.
