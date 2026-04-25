def compute_risk_score(grid_data):
    line = grid_data["max_line_loading"]
    voltage = grid_data["min_voltage"]
    load = grid_data["total_load"]

    line_risk = min(line / 100, 1)
    voltage_risk = min(abs(1.0 - voltage) / 0.1, 1)
    load_risk = min(load / 250, 1)

    return round((line_risk + voltage_risk + load_risk) / 3, 3)


def get_risk_level(score):
    if score >= 0.7:
        return "HIGH"
    elif score >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


def get_brain1_output(grid_data):
    score = compute_risk_score(grid_data)
    level = get_risk_level(score)

    return {
        "risk_score": score,
        "risk_level": level
    }