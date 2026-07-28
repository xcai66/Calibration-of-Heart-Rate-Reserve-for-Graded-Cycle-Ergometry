Use the reviewer_revision_* files with the revised manuscripts.

The legacy sample_flow.json field hr_qc_pass=281 counts all tracker-linked records passing heart-rate quality control before bidirectional uniqueness is enforced. The revised, sequential manuscript flow is 783 RPE rows -> 469 tracker-linked rows -> 447 bidirectionally unique matches -> 267 unique matches passing heart-rate quality control -> 255 primary sessions. See reviewer_revision_attrition_audit.csv and reviewer_revision_analysis.json.

Reviewer-revision bootstrap intervals condition on realized held-out predictions and do not repeat formula-family selection or the complete development pipeline. The RPE>=8 ROC analysis is post hoc and exploratory, not a clinical or exercise-prescription threshold.
