# Feedback

Feedback is explicit preference adjustment, not machine learning.

Supported feedback types:

- `too_expensive`
- `too_far_away`
- `too_risky`
- `wrong_brand`
- `missing_feature`
- `not_my_style`
- `favorite`
- `ignore`

Example:

```bash
opa feedback add car_001 favorite \
  --profile examples/profiles/family_car.yml \
  --reason "worth checking"

opa score --profile examples/profiles/family_car.yml
```

Stored feedback events are applied deterministically during scoring and included
in the score explanation.
