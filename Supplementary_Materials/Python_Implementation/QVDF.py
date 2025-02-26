import numpy as np
import math

# Constants (example values, adjust as needed)
MAX_TIMEINTERVAL_PerDay = 300  # 12 5-min intervals *24
MAX_TIMEPERIODS = 10
MAX_MODETYPES = 5


def calculate_travel_time_based_on_QVDF(vf, v_congestion_cutoff, FFTT, vdf_type, at, volume, mode_hourly_capacity, peak_load_factor,
                                        link_type, tau, starting_time_in_hour, ending_time_in_hour, nlanes, alpha, beta,
                                        Q_alpha, Q_beta, Q_n, Q_s, model_speed,
                                        emissions_co2_matrix, emissions_nox_matrix,
                                        link_avg_co2_emit_per_mode_per_tau_per_at, link_avg_nox_emit_per_mode_per_tau_per_at,
                                        Q_cd, Q_cp, L, t2):
    time_period_in_min = max(0.1, (ending_time_in_hour - starting_time_in_hour) * 60)
    time_period_in_hour = max(0.1, (ending_time_in_hour - starting_time_in_hour))
    # initialization 
    avg_travel_time = 0
    dc_transition_ratio = 1

    # Step 1: Calculate lane_based D
    lane_based_D = max(0.0, volume) / time_period_in_hour / max(0.000001, nlanes) / peak_load_factor

    # Step 2: D/C ratio
    DOC = lane_based_D / max(0.00001, mode_hourly_capacity)  # mode can be driving, bike, pedestrian

    if nlanes < 0.6:
        lane_based_D = max(0.0, volume) / time_period_in_hour / peak_load_factor
        DOC = lane_based_D / max(0.00001, mode_hourly_capacity * nlanes)

    DOC = min(DOC, 9.99)  # Regulation

    # Step 3.1: Fetch vf and v_congestion_cutoff based on FFTT, VCTT
    # (To be compatible with transit data, such as waiting time)
    # We could have a period based FFTT, so we need to convert FFTT to vfree
    # If we only have one period, then we can directly use vf and v_congestion_cutoff.

    # Step 3.2: Calculate speed from VDF based on D/C ratio
    avg_queue_speed = v_congestion_cutoff / (1.0 + Q_alpha * np.power(DOC, Q_beta))
    link_length_in_1km = 1.0
    RTT = link_length_in_1km / v_congestion_cutoff  # RTT is reference link travel time
    Q_n_current_value = Q_n

    if DOC < dc_transition_ratio:  # Free flow regime
        vf_alpha = (1.0 + Q_alpha) * vf / max(0.0001, v_congestion_cutoff) - 1.0
        vf_beta = beta
        vf_avg_speed = vf / (1.0 + vf_alpha * np.power(DOC, vf_beta))
        avg_queue_speed = vf_avg_speed
        Q_n_current_value = beta
        RTT = link_length_in_1km / max(0.01, vf)

    # BPR (Bureau of Public Roads) function as default
    avg_speed_BPR = vf / (1.0 + alpha * np.power(DOC, beta))
    avg_travel_time = FFTT * (1 + alpha * np.power(DOC, beta))  # Note: FFTT should be VCTT ( Crtical Speed based Travel Time)

    # Calculate average waiting time
    avg_waiting_time = avg_travel_time - FFTT

    # Assuming the necessary variables and constants are defined elsewhere in your code
    # For example: Q_cd, DOC, Q_n_current_value, Q_cp, Q_s, v_congestion_cutoff, volume,
    # peak_load_factor, nlanes, L, mode_hourly_capacity, vf, t2, lane_based_D,
    # link_length_in_1km, RTT, etc.

    # P applied for both uncongested and congested conditions
    P = Q_cd * np.power(DOC, Q_n_current_value)

    # Calculate base
    base = Q_cp * np.power(P, Q_s) + 1.0
    vt2 = v_congestion_cutoff / max(0.001, base)

    # Compute nonpeak hourly flow
    nonpeak_hourly_flow = 0
    if L - P >= 10.0 / 60.0:
        nonpeak_hourly_flow = (volume * (1 - peak_load_factor)) / max(0.001, nlanes) / max(0.1, min(L - 1, L - P - 5.0 / 60.0))

    # Set up the upper bound on nonpeak flow rates
    nonpeak_hourly_flow = min(nonpeak_hourly_flow, mode_hourly_capacity)

    # Calculate nonpeak average speed
    nonpeak_avg_speed = (vf + v_congestion_cutoff) / 2.0

    # Calculate t0 and t3 for congestion duration
    t0 = t2 - 0.5 * P
    t3 = t2 + 0.5 * P

    # Work on congested condition
    # Step 4.3: Compute mu
    Q_mu = min(mode_hourly_capacity, lane_based_D / P)

    # Calculate wt2
    wt2 = link_length_in_1km / vt2 - RTT  # in hour

    # Step 5: Compute gamma parameter
    Q_gamma = wt2 * 64 * Q_mu / np.power(P, 4)  # because q_tw = w*mu = 1/4 * gamma * (P/2)^4

    # Calculating test values for QL(t2) and wt2
    test_QL_t2 = Q_gamma / 64.0 * np.power(P, 4)
    test_wt2 = test_QL_t2 / Q_mu

    # Calculate test_vt2
    test_vt2 = link_length_in_1km / (test_wt2 + RTT)

    # Assuming necessary variables and constants are defined elsewhere in your code
    # For example, starting_time_in_hour, ending_time_in_hour, t0, t3, Q_gamma, Q_mu,
    # link_length_in_1km, RTT, vf, v_congestion_cutoff, avg_queue_speed, model_speed, est_volume_per_hour_per_lane, etc.

    # Ensure diff_v_t2 = 0
    diff = test_vt2 - vt2
    td_w = 0
    Severe_Congestion_P = 0

    # Scan the entire analysis period
    for t_in_min in range(int(starting_time_in_hour * 60), int(ending_time_in_hour * 60 + 1), 5):
        t = t_in_min / 60.0  # t in hour
        td_queue = 0
        td_speed = 0

    if t0 <= t <= t3:  # within congestion duration P
        # 1/4*gamma*(t-t0)^2(t-t3)^2
        td_queue = 0.25 * Q_gamma * (t - t0) ** 2 * (t - t3) ** 2
        td_w = td_queue / max(0.001, Q_mu)
        # L/[(w(t)+RTT_in_hour]
        td_speed = link_length_in_1km / (td_w + RTT)
    elif t < t0:  # outside
        factor = (t - starting_time_in_hour) / max(0.001, t0 - starting_time_in_hour)
        td_speed = (1 - factor) * vf + factor * max(v_congestion_cutoff, avg_queue_speed)
    else:  # t > t3
        factor = (t - t3) / max(0.001, ending_time_in_hour - t3)
        td_speed = (1 - factor) * max(v_congestion_cutoff, avg_queue_speed) + factor * vf

    # Uncomment below lines if you want to print or log the queue and speed
    # print("td_queue t", t, " = ", td_queue, ", speed =", td_speed)
    # logging.info("td_queue t" + str(t) + " = " + str(td_queue) + ", speed =" + str(td_speed))

    t_interval = t_in_min // 5

    if t_in_min <= 410:
        idebug = 1  # Set a breakpoint or print statement for debugging

    model_speed[t_interval] = td_speed

    if td_speed < vf * 0.5:
        Severe_Congestion_P += 5.0 / 60  # 5 min interval

    # Apply final travel time range constraints
    avg_travel_time = max(avg_travel_time, max(15.0, time_period_in_min * 1.5))

    # Convert vf from km/h to mph
    vf_mph = vf / 1.609

    # Calculate vq (speed in mph)
    vq = vf_mph / max(0.00001, avg_travel_time / FFTT) / 1.609

    # Calculate the difference between vf and vq
    vf_minus_vq = vf_mph - vq

    # Calculate waiting time
    waiting_time_w = avg_travel_time - FFTT

    # Set speed v to be equal to vq
    v = vq

    # Calculate CO2 emission rate using a quadratic function of speed v
    lambda_emission = v * v * emissions_co2_matrix[1] + v * emissions_co2_matrix[2] + emissions_co2_matrix[3]
    ratio = 0.0

    # Adjust ratio if the absolute difference between vf and vq is greater than 1
    if abs(vf_mph - vq) > 1:
        ratio = (lambda_emission * vf_mph - vq) / (vf_mph - vq)

    # Compute the CO2 emission rate
    emission_rate = emissions_co2_matrix[at][0] * (FFTT / 60.0 + waiting_time_w / 60.0 * ratio)

    # Store the computed total CO2 emissions
    link_avg_co2_emit_per_mode_per_tau_per_at = link_avg_co2_emit_per_mode_per_tau_per_at + emission_rate / 1000.0  # Convert to kg

    # NOx emissions calculation
    lambda_emission = v * v * emissions_nox_matrix[1] + v * emissions_nox_matrix[2] + emissions_nox_matrix[3]
    ratio = 0.0

    # Adjust ratio for NOx emission
    if abs(vf_mph - vq) > 1:
        ratio = (lambda_emission * vf_mph - vq) / (vf_mph - vq)

    # Compute the NOx emission rate
    emission_rate = emissions_nox_matrix[0] * (FFTT / 60.0 + waiting_time_w / 60.0 * ratio)

    # Store the computed total NOx emissions
    link_avg_nox_emit_per_mode_per_tau_per_at = link_avg_nox_emit_per_mode_per_tau_per_at + emission_rate / 1000.0  # Convert to kg

    return avg_waiting_time, link_avg_nox_emit_per_mode_per_tau_per_at
